from app.models.schemas import EligibilityProfile
from app.rag.context_builder import Evidence
from app.services.eligibility_service import EligibilityService


class EmptyRetriever:
    def retrieve(self, *args, **kwargs):
        return []


class AgeRuleRetriever:
    def retrieve(self, *args, **kwargs):
        return [
            {
                "id": "chunk-1",
                "document": "Eligibility criteria: Applicants must be between 18 and 40 years of age.",
                "metadata": {
                    "document_id": "doc-1",
                    "document_name": "Scheme.pdf",
                    "scheme_name": "Scheme",
                    "page_number": 2,
                    "chunk_id": "chunk-1",
                    "content_hash": "hash-1",
                },
                "similarity_score": 0.9,
            }
        ]


def test_eligibility_without_indexed_rules_is_insufficient():
    service = EligibilityService(EmptyRetriever())
    result = service.evaluate("unknown-scheme", EligibilityProfile(age=24))
    assert result.status == "INSUFFICIENT_INFORMATION"
    assert result.missing_information
    assert "not official approval" in result.disclaimer


def test_clear_documented_age_mismatch_is_not_eligible():
    service = EligibilityService(AgeRuleRetriever())
    result = service.evaluate("scheme", EligibilityProfile(age=17))
    assert result.status == "LIKELY_NOT_ELIGIBLE"
    assert result.unmatched_criteria
    assert result.citations[0].page_number == 2
