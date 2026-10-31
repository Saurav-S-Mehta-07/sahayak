from app.utils.language import detect_language, expand_query


class TranslationService:
    """Conservative query expansion; this does not translate legal source text."""

    @staticmethod
    def language(text: str, requested: str = "auto") -> str:
        return detect_language(text, requested)

    @staticmethod
    def retrieval_variants(text: str) -> list[str]:
        return expand_query(text)
