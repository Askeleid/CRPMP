from abc import ABC, abstractmethod
import re


class CitationStrategy(ABC):
    """Abstract base strategy for formatting a research paper citation."""

    @abstractmethod
    def format(self, paper) -> str:
        """Return a formatted citation string for the given paper."""


class BibTeXStrategy(CitationStrategy):
    """Format paper citations as BibTeX @article entries."""

    @staticmethod
    def _extract_first_author_last_name(authors: str) -> str:
        first_author = (authors or "").split(",")[0].strip()
        if not first_author:
            return "unknown"
        last_token = first_author.split()[-1]
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", last_token).lower()
        return cleaned or "unknown"

    def format(self, paper) -> str:
        last_name = self._extract_first_author_last_name(paper.authors)
        cite_key = f"{last_name}{paper.year}"
        fields = [
            f"  title={{{paper.title}}}",
            f"  author={{{paper.authors}}}",
            f"  year={{{paper.year}}}",
        ]
        doi = getattr(paper, "doi", "")
        if doi:
            fields.append(f"  doi={{{doi}}}")
        body = ",\n".join(fields)
        return f"@article{{{cite_key},\n{body}\n}}"


class APAStrategy(CitationStrategy):
    """Format paper citations in APA style."""

    def format(self, paper) -> str:
        base = f"{paper.authors} ({paper.year}). {paper.title}."
        doi = getattr(paper, "doi", "")
        url = getattr(paper, "url", "")
        if doi:
            return f"{base} https://doi.org/{doi}"
        if url:
            return f"{base} {url}"
        return base


class IEEEStrategy(CitationStrategy):
    """Format paper citations in IEEE style."""

    def format(self, paper) -> str:
        base = f'{paper.authors}, "{paper.title}," {paper.year}.'
        doi = getattr(paper, "doi", "")
        if doi:
            return f"{base} doi: {doi}."
        return base


class CitationExporter:
    """Context class that exports paper citations using a configurable strategy."""

    def __init__(self, strategy: CitationStrategy | None = None) -> None:
        self._strategy: CitationStrategy = strategy or BibTeXStrategy()

    def set_strategy(self, strategy: CitationStrategy) -> None:
        """Replace the active citation formatting strategy at runtime."""
        self._strategy = strategy

    def export(self, paper) -> str:
        """Format and return the paper citation using the active strategy."""
        return self._strategy.format(paper)


CITATION_FORMATS: tuple[tuple[str, str], ...] = (
    ("bibtex", "BibTeX"),
    ("apa", "APA"),
    ("ieee", "IEEE"),
)

_STRATEGY_REGISTRY: dict[str, type[CitationStrategy]] = {
    "bibtex": BibTeXStrategy,
    "apa": APAStrategy,
    "ieee": IEEEStrategy,
}


def get_citation_strategy(format_name: str) -> CitationStrategy:
    """Return the CitationStrategy matching format_name or raise ValueError."""
    normalized = (format_name or "").strip().lower()
    strategy_cls = _STRATEGY_REGISTRY.get(normalized)
    if strategy_cls is None:
        supported = ", ".join(_STRATEGY_REGISTRY.keys())
        raise ValueError(
            f"Unsupported citation format '{format_name}'. Supported: {supported}."
        )
    return strategy_cls()
