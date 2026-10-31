import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BookOpenText,
  ChevronDown,
  CircleHelp,
  CircleUserRound,
  Check,
  Leaf,
  LogOut,
  Menu,
  MessageSquareText,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { checkHealth } from "../services/api.js";
import { useChat } from "../context/ChatContext.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { getDisplayLocale } from "../utils/language.js";

const copy = {
  en: {
    newChat: "New conversation",
    recent: "Recent conversations",
    explore: "Explore documents",
    about: "About Yojana Sahayak",
    online: "Backend online",
    offline: "Backend offline",
    noRecent: "Your conversations will appear here.",
    subtitle: "Government scheme assistant",
    help: "Answers are grounded in your scheme documents.",
  },
  hi: {
    newChat: "नई बातचीत",
    recent: "हाल की बातचीत",
    explore: "दस्तावेज़ देखें",
    about: "योजना सहायक के बारे में",
    online: "बैकएंड ऑनलाइन",
    offline: "बैकएंड ऑफ़लाइन",
    noRecent: "आपकी बातचीत यहाँ दिखाई देगी।",
    subtitle: "सरकारी योजना सहायक",
    help: "जवाब आपके योजना दस्तावेज़ों पर आधारित हैं।",
  },
};

function relativeTime(value, language) {
  const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
  const locale = getDisplayLocale(language);
  const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (seconds < 60) return relative.format(0, "second");
  if (seconds < 3600) return relative.format(-Math.floor(seconds / 60), "minute");
  if (seconds < 86400) return relative.format(-Math.floor(seconds / 3600), "hour");
  return relative.format(-Math.floor(seconds / 86400), "day");
}

function Sidebar({ mobileOpen, closeMobile }) {
  const { chats, activeId, createChat, selectChat, deleteChat, renameChat, language } =
    useChat();
  const text = copy[language === "hi" ? "hi" : "en"];
  const navigate = useNavigate();
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [actionError, setActionError] = useState("");
  const shownChats = chats.filter((chat) =>
    `${chat.title} ${chat.messages.map((message) => message.content).join(" ")}`
      .toLocaleLowerCase()
      .includes(query.trim().toLocaleLowerCase()),
  );

  async function saveTitle(event, id) {
    event.preventDefault();
    const result = await renameChat(id, editingTitle);
    if (!result.ok) {
      setActionError(result.error);
      return;
    }
    setEditingId(null);
    setActionError("");
  }

  return (
    <>
      {mobileOpen && (
        <button
          className="drawer-scrim"
          aria-label="Close navigation"
          onClick={closeMobile}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Leaf size={19} strokeWidth={2.2} /></div>
          <div>
            <Link to="/" className="brand-name" onClick={closeMobile}>Yojana Sahayak</Link>
            <span className="brand-caption">{text.subtitle}</span>
          </div>
          <button className="icon-button sidebar-close" onClick={closeMobile} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <button
          className="new-chat-button"
          onClick={() => {
            createChat();
            closeMobile();
            navigate("/chat");
          }}
        >
          <Plus size={17} />
          <span>{text.newChat}</span>
          <span className="shortcut">Ctrl/⌘ K</span>
        </button>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <NavLink
            to="/chat"
            end
            onClick={closeMobile}
            className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
          >
            <MessageSquareText size={17} /><span>{text.newChat}</span>
          </NavLink>
          <NavLink
            to="/documents"
            onClick={closeMobile}
            className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
          >
            <BookOpenText size={17} /><span>{text.explore}</span>
          </NavLink>
        </nav>
        <nav className="sidebar-nav secondary-nav" aria-label="More">
          <NavLink to="/schemes" onClick={closeMobile} className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}>
            <BookOpenText size={17} /><span>Scheme directory</span>
          </NavLink>
          {user?.role === "admin" && <NavLink to="/admin" onClick={closeMobile} className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}>
            <ShieldCheck size={17} /><span>Administration</span>
          </NavLink>}
        </nav>

        <div className="recent-header">
          <span>{text.recent}</span>
          <span className="recent-count">{chats.length || ""}</span>
        </div>
        <label className="conversation-search">
          <Search size={14} />
          <span className="sr-only">Search conversations</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search conversations"
          />
        </label>
        <div className="conversation-list">
          {chats.length === 0 ? (
            <p className="sidebar-empty">{text.noRecent}</p>
          ) : shownChats.length === 0 ? (
            <p className="sidebar-empty">No conversations match your search.</p>
          ) : shownChats.map((chat) => (
            <div className={`conversation-row ${activeId === chat.id ? "conversation-active" : ""}`} key={chat.id}>
              {editingId === chat.id ? (
                <form className="conversation-rename" onSubmit={(event) => saveTitle(event, chat.id)}>
                  <label className="sr-only" htmlFor={`rename-${chat.id}`}>Rename conversation</label>
                  <input
                    id={`rename-${chat.id}`}
                    value={editingTitle}
                    maxLength={80}
                    autoFocus
                    onChange={(event) => setEditingTitle(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") setEditingId(null);
                    }}
                  />
                  <button type="submit" className="conversation-action" aria-label="Save conversation title"><Check size={14} /></button>
                </form>
              ) : (
                <button
                  className="conversation-select"
                  onClick={() => {
                    selectChat(chat.id);
                    closeMobile();
                  }}
                  title={chat.title}
                >
                  <MessageSquareText size={15} /><span>{chat.title}</span>
                </button>
              )}
              <span className="conversation-time">{relativeTime(chat.updatedAt, language)}</span>
              <button
                className="conversation-action"
                aria-label={`Rename ${chat.title}`}
                title="Rename conversation"
                onClick={() => {
                  setEditingId(chat.id);
                  setEditingTitle(chat.title);
                }}
              >
                <Pencil size={13} />
              </button>
              <button
                className="conversation-delete"
                aria-label={`Delete ${chat.title}`}
                onClick={() => {
                  if (window.confirm(`Delete “${chat.title}” and its saved messages?`)) {
                    deleteChat(chat.id);
                  }
                }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        {actionError && <p className="sidebar-action-error" role="alert">{actionError}</p>}

        <div className="sidebar-bottom">
          <div className="sidebar-assurance">
            <div className="assurance-icon"><ShieldCheck size={16} /></div>
            <p>{text.help}</p>
          </div>
          <NavLink
            to="/about"
            onClick={closeMobile}
            className={({ isActive }) => `nav-link sidebar-about ${isActive ? "nav-link-active" : ""}`}
          >
            <CircleHelp size={17} /><span>{text.about}</span>
          </NavLink>
          <span className="version-label">YOJANA SAHAYAK · v1.0</span>
        </div>
      </aside>
    </>
  );
}

function Topbar({ title, onMenu }) {
  const { language, setLanguage } = useChat();
  const { user, signOut } = useAuth();
  const [signOutError, setSignOutError] = useState("");
  const [health, setHealth] = useState({ status: "checking" });
  const location = useLocation();

  useEffect(() => {
    let active = true;
    const update = async () => {
      const response = await checkHealth();
      if (active) setHealth(response);
    };
    update();
    const interval = window.setInterval(update, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-button mobile-menu-button" onClick={onMenu} aria-label="Open navigation">
          <Menu size={19} />
        </button>
        <div className="breadcrumbs">
          <span className="breadcrumb-root">Sahayak</span>
          <span className="breadcrumb-divider">/</span>
          <span className="breadcrumb-current">{title}</span>
        </div>
      </div>
      <div className="topbar-right">
        <div
          className={`connection-pill ${health.status === "ok" ? "connection-online" : ""}`}
          title={health.error || `API ${health.status}`}
          aria-live="polite"
        >
          <span className="status-dot" />
          <span>{health.status === "ok" ? copy[language === "hi" ? "hi" : "en"].online : health.status === "checking" ? "Connecting" : copy[language === "hi" ? "hi" : "en"].offline}</span>
        </div>
        <label className="language-select-wrap">
          <span className="sr-only">Preferred response language</span>
          <select className="language-select" value={language} onChange={(event) => setLanguage(event.target.value)} aria-label="Response language">
            <option value="auto">Auto</option>
            <option value="en">English</option>
            <option value="hi">हिंदी</option>
            <option value="ur">اردو</option>
            <option value="bn">বাংলা</option>
            <option value="ta">தமிழ்</option>
            <option value="te">తెలుగు</option>
            <option value="mr">मराठी</option>
            <option value="gu">ગુજરાતી</option>
            <option value="kn">ಕನ್ನಡ</option>
            <option value="ml">മലയാളം</option>
            <option value="pa">ਪੰਜਾਬੀ</option>
            <option value="hinglish">Hinglish</option>
            <option value="roman_hindi">Roman Hindi</option>
            <option value="roman_urdu">Roman Urdu</option>
          </select>
          <ChevronDown size={13} />
        </label>
        <span className="theme-indicator" title="Dark theme"><span /></span>
        {user ? (
          <button className="topbar-account" title={user.email} onClick={async () => {
            setSignOutError("");
            try {
              await signOut();
            } catch (error) {
              setSignOutError(error.message);
            }
          }}><CircleUserRound size={15} /><span>Sign out</span><LogOut size={14} /></button>
        ) : <Link className="topbar-account" to="/login">Sign in</Link>}
      </div>
      {signOutError && <span className="signout-error" role="alert">{signOutError}</span>}
      <span className="sr-only" aria-live="polite">{location.pathname === "/documents" ? "Documents page" : title}</span>
    </header>
  );
}

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { activeChat } = useChat();
  const title = location.pathname === "/documents"
    ? "Explore documents"
    : location.pathname === "/about"
      ? "About Yojana Sahayak"
      : location.pathname === "/admin"
        ? "Document management"
        : location.pathname === "/schemes"
          ? "Scheme directory"
      : activeChat?.title || "New conversation";

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const { createChat } = useChat();
  const navigate = useNavigate();
  useEffect(() => {
    function onShortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        const target = event.target;
        if (
          target instanceof HTMLElement
          && (target.isContentEditable || target.matches("input, textarea, select"))
        ) return;
        event.preventDefault();
        createChat();
        navigate("/chat");
      }
    }
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, [createChat, navigate]);

  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileOpen} closeMobile={() => setMobileOpen(false)} />
      <main className="main-shell">
        <Topbar title={title} onMenu={() => setMobileOpen(true)} />
        <AnimatePresence mode="wait">
          <motion.div
            className="route-stage"
            key={location.pathname}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -3 }}
            transition={{ duration: 0.18 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
