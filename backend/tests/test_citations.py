from app.rag.citation_manager import CitationManager
from app.rag.context_builder import Evidence
from app.services.hallucination_checker import HallucinationChecker


def make_evidence():
    return [
        Evidence(
            citation_id="CIT-001",
            document_id="doc-1",
            document_name="PM_KISAN_Guidelines.pdf",
            scheme_name="PM-KISAN",
            page_number=12,
            chunk_id="chunk-1",
            content="The documented benefit is ₹6,000 per year.",
        )
    ]


def test_citation_metadata_comes_from_retrieved_evidence():
    evidence = make_evidence()
    answer = "The document states ₹6,000 per year. [CIT-001]"
    citations = CitationManager.citations(evidence, answer)
    assert citations[0].page_number == 12
    assert citations[0].document_name == "PM_KISAN_Guidelines.pdf"
    assert citations[0].pdf_url.endswith("#page=12")
    assert CitationManager.valid(answer, citations, evidence)


def test_unknown_citation_is_rejected():
    evidence = make_evidence()
    answer = "Claim [CIT-999]"
    citations = CitationManager.citations(evidence, answer)
    assert not CitationManager.valid(answer, citations, evidence)


def test_numeric_claim_without_evidence_fails_verification():
    evidence = make_evidence()
    answer = "The amount is ₹8,000 per year. [CIT-001]"
    citations = CitationManager.citations(evidence, answer)
    check = HallucinationChecker().verify(answer, citations, evidence)
    assert not check.safe
    assert check.grounding.verification_status == "verification_failed"


def test_numeric_claim_with_exact_citation_passes():
    evidence = make_evidence()
    answer = "The documented amount is ₹6,000 per year. [CIT-001]"
    citations = CitationManager.citations(evidence, answer)
    check = HallucinationChecker().verify(answer, citations, evidence)
    assert check.safe
    assert check.grounding.verification_status == "verified"


def test_page_number_is_not_mistaken_for_a_scheme_fact():
    evidence = make_evidence()
    answer = "The benefit is 12. [CIT-001]"
    citations = CitationManager.citations(evidence, answer)
    check = HallucinationChecker().verify(answer, citations, evidence)
    assert not check.safe
    assert "12" in check.grounding.unsupported_claims


def test_repeated_user_age_is_not_confused_with_a_scheme_rule():
    evidence = make_evidence()
    answer = "You said your age is 24. [CIT-001]"
    citations = CitationManager.citations(evidence, answer)
    check = HallucinationChecker().verify(answer, citations, evidence, "I am 24 years old")
    assert check.safe


def test_financial_period_must_match_cited_passage():
    evidence = make_evidence()
    answer = "The documented amount is ₹6,000 per month. [CIT-001]"
    citations = CitationManager.citations(evidence, answer)
    check = HallucinationChecker().verify(answer, citations, evidence)
    assert not check.safe
    assert check.grounding.unsupported_claims
