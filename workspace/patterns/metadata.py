from abc import ABC, abstractmethod
import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET


class MetadataProvider(ABC):
    """Abstract target interface for external academic paper metadata providers."""

    @abstractmethod
    def fetch(self, identifier: str) -> dict:
        """Fetch metadata for identifier and return a normalized metadata dict."""


def _clean_whitespace(text: str | None) -> str:
    return " ".join((text or "").split())


class ArxivAdapter(MetadataProvider):
    """Adapter querying the arXiv Atom API and normalizing metadata."""

    ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    def fetch(self, identifier: str) -> dict:
        cleaned_id = (identifier or "").strip()
        if not cleaned_id:
            raise ValueError("arXiv identifier must not be empty.")

        query_url = (
            f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(cleaned_id)}"
        )
        try:
            with urllib.request.urlopen(query_url, timeout=10) as response:
                raw_xml = response.read()
        except (URLError, HTTPError, OSError) as exc:
            raise ValueError(f"Failed to fetch arXiv metadata: {exc}") from exc

        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid XML returned by arXiv: {exc}") from exc

        entry = root.find("atom:entry", self.ATOM_NS)
        if entry is None:
            raise ValueError(f"No arXiv entry found for '{cleaned_id}'.")

        title = _clean_whitespace(entry.findtext("atom:title", default="", namespaces=self.ATOM_NS))
        if not title or title.lower() == "error":
            raise ValueError(f"Invalid or missing arXiv paper for '{cleaned_id}'.")

        published = entry.findtext("atom:published", default="", namespaces=self.ATOM_NS).strip()
        try:
            year = int(published[:4])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Missing or invalid publication year for '{cleaned_id}'.") from exc

        author_names = [
            _clean_whitespace(name_el.text)
            for name_el in entry.findall("atom:author/atom:name", self.ATOM_NS)
            if _clean_whitespace(name_el.text)
        ]
        abstract = _clean_whitespace(
            entry.findtext("atom:summary", default="", namespaces=self.ATOM_NS)
        )
        doi = _clean_whitespace(
            entry.findtext("arxiv:doi", default="", namespaces=self.ATOM_NS)
        )

        alt_link = ""
        for link_el in entry.findall("atom:link", self.ATOM_NS):
            if link_el.attrib.get("rel") == "alternate" and link_el.attrib.get("href"):
                alt_link = link_el.attrib["href"].strip()
                break
        entry_id = _clean_whitespace(
            entry.findtext("atom:id", default="", namespaces=self.ATOM_NS)
        )
        url = alt_link or entry_id

        return {
            "title": title,
            "authors": ", ".join(author_names),
            "year": year,
            "doi": doi,
            "arxiv_id": cleaned_id,
            "url": url,
            "abstract": abstract,
        }


class CrossRefAdapter(MetadataProvider):
    """Adapter querying the CrossRef REST API and normalizing metadata."""

    def fetch(self, identifier: str) -> dict:
        cleaned_doi = (identifier or "").strip()
        if not cleaned_doi:
            raise ValueError("DOI identifier must not be empty.")

        query_url = (
            f"https://api.crossref.org/works/{urllib.parse.quote(cleaned_doi, safe='/')}"
        )
        try:
            with urllib.request.urlopen(query_url, timeout=10) as response:
                raw_json = response.read().decode("utf-8")
        except (URLError, HTTPError, OSError) as exc:
            raise ValueError(f"Failed to fetch CrossRef metadata: {exc}") from exc

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON returned by CrossRef: {exc}") from exc

        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError(f"No CrossRef work found for '{cleaned_doi}'.")

        titles = message.get("title") or []
        title = _clean_whitespace(titles[0]) if titles else ""
        if not title:
            raise ValueError(f"Missing title in CrossRef metadata for '{cleaned_doi}'.")

        year = self._extract_year(message, cleaned_doi)
        authors = self._extract_authors(message)
        doi = _clean_whitespace(message.get("DOI")) or cleaned_doi
        url = _clean_whitespace(message.get("URL")) or f"https://doi.org/{doi}"
        raw_abstract = message.get("abstract") or ""
        abstract = _clean_whitespace(re.sub(r"<[^>]+>", " ", raw_abstract))

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "arxiv_id": "",
            "url": url,
            "abstract": abstract,
        }

    @staticmethod
    def _extract_authors(message: dict) -> str:
        formatted: list[str] = []
        for author in message.get("author") or []:
            if not isinstance(author, dict):
                continue
            full_name = " ".join(
                part
                for part in (
                    (author.get("given") or "").strip(),
                    (author.get("family") or "").strip(),
                )
                if part
            )
            if full_name:
                formatted.append(full_name)
        return ", ".join(formatted)

    @staticmethod
    def _extract_year(message: dict, identifier: str) -> int:
        for field in ("published-print", "published-online", "issued", "created"):
            date_info = message.get(field)
            if isinstance(date_info, dict):
                parts = date_info.get("date-parts")
                if parts and isinstance(parts[0], list) and parts[0]:
                    try:
                        return int(parts[0][0])
                    except (TypeError, ValueError):
                        continue
        raise ValueError(
            f"Missing or invalid publication year in CrossRef metadata for '{identifier}'."
        )


_METADATA_ADAPTERS: dict[str, type[MetadataProvider]] = {
    "arxiv": ArxivAdapter,
    "crossref": CrossRefAdapter,
}


def get_metadata_adapter(source: str) -> MetadataProvider:
    """Return the MetadataProvider adapter for the given source ('arxiv' or 'crossref')."""
    normalized = (source or "").strip().lower()
    adapter_cls = _METADATA_ADAPTERS.get(normalized)
    if adapter_cls is None:
        supported = ", ".join(_METADATA_ADAPTERS.keys())
        raise ValueError(
            f"Unsupported metadata source '{source}'. Supported: {supported}."
        )
    return adapter_cls()
