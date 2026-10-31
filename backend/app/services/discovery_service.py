"""Configured official RSS discovery; discoveries remain review-only signals."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

from ..database import connect
if __package__ and __package__.startswith("backend."):
    from backend.src.config import settings
else:
    from src.config import settings

logger = logging.getLogger(__name__)
MAX_FEED_BYTES = 1_000_000
FEED_TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class DiscoverySignal:
    title: str
    source_url: str
    source_organization: str
    published_at: str | None
    excerpt: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _official_host(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not (host.endswith(".gov.in") or host == "gov.in" or host.endswith(".nic.in"))
    ):
        raise ValueError("Discovery feeds and links must use an official HTTPS government domain.")
    return host


def _validate_public_host(host: str) -> None:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("The configured feed host did not resolve.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("The configured feed host resolved to a non-public address.")


def _clean_excerpt(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    text = " ".join(parser.parts)
    return re.sub(r"\s+([,.;:!?])", r"\1", text)[:1000]


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        result = parsedate_to_datetime(value)
        return result.isoformat()
    except (TypeError, ValueError, OverflowError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return None


def parse_feed(content: bytes, feed_url: str) -> list[DiscoverySignal]:
    feed_host = _official_host(feed_url)
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", content, flags=re.IGNORECASE):
        raise ValueError("Discovery feed XML must not declare entities or a document type.")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("The configured discovery feed is not valid XML.") from exc

    signals: list[DiscoverySignal] = []
    for item in root.iter():
        local_name = item.tag.rsplit("}", 1)[-1].lower()
        if local_name not in {"item", "entry"}:
            continue
        values: dict[str, str] = {}
        for child in list(item):
            key = child.tag.rsplit("}", 1)[-1].lower()
            if key == "link" and not (child.text or "").strip():
                candidate = child.attrib.get("href", "")
            else:
                candidate = child.text or ""
            values.setdefault(key, candidate.strip())
        title = _clean_excerpt(values.get("title", ""))
        link = values.get("link", "")
        if not title or not link:
            continue
        try:
            link_host = _official_host(link)
        except ValueError:
            logger.info("Skipped non-official link in discovery feed %s", feed_host)
            continue
        excerpt = _clean_excerpt(
            values.get("description", "")
            or values.get("summary", "")
            or values.get("content", "")
        )
        signals.append(
            DiscoverySignal(
                title=title[:300],
                source_url=link,
                source_organization=link_host,
                published_at=_normalize_date(
                    values.get("pubdate")
                    or values.get("published")
                    or values.get("updated")
                ),
                excerpt=excerpt,
            )
        )
    return signals


def _fetch_feed(feed_url: str) -> bytes:
    host = _official_host(feed_url)
    _validate_public_host(host)
    request = urllib.request.Request(
        feed_url,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            "User-Agent": "YojanaSahayakSchemeDiscovery/1.0",
        },
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=FEED_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ValueError(f"Feed returned HTTP {response.status}.")
            final_host = _official_host(response.geturl())
            if final_host != host:
                raise ValueError("Discovery feed redirected to a different host.")
            content_type = response.headers.get_content_type()
            if content_type not in {
                "application/rss+xml",
                "application/atom+xml",
                "application/xml",
                "text/xml",
            }:
                raise ValueError("Feed response was not an XML document.")
            content = response.read(MAX_FEED_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Feed returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not retrieve the configured feed: {exc.reason}.") from exc
    if len(content) > MAX_FEED_BYTES:
        raise ValueError("The configured feed exceeds the 1 MB limit.")
    return content


def discover_configured_feeds() -> dict:
    """Fetch configured feeds and persist unique review-only discovery signals."""
    feeds = settings.scheme_discovery_feed_urls
    if not feeds:
        raise ValueError("No SCHEME_DISCOVERY_FEEDS are configured.")

    new_count = 0
    errors: list[str] = []
    checked = 0
    for feed_url in feeds:
        try:
            _official_host(feed_url)
            signals = parse_feed(_fetch_feed(feed_url), feed_url)
            checked += 1
            with connect() as connection:
                for signal in signals:
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO scheme_discoveries
                            (title, source_url, feed_url, source_organization,
                             published_at, excerpt)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            signal.title,
                            signal.source_url,
                            feed_url,
                            signal.source_organization,
                            signal.published_at,
                            signal.excerpt,
                        ),
                    )
                    new_count += cursor.rowcount
        except Exception as exc:
            logger.exception("Scheme discovery feed failed")
            errors.append(f"{urlparse(feed_url).hostname or 'configured feed'}: {exc}")

    return {
        "feeds_checked": checked,
        "new_discoveries": new_count,
        "errors": errors,
    }
