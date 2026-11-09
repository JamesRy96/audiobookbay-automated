# File: audiobook_automated/contributors.py
"""Conservative presentation of contributor credits without network enrichment."""

import re
from typing import TypedDict

_PARTICLES = {"de", "del", "da", "di", "du", "la", "le", "van", "von", "der", "den"}
_MIN_NAME_WORDS = 2
_MAX_NAME_WORDS = 6
_GROUP_WORDS = {
    "the",
    "courses",
    "authors",
    "cast",
    "press",
    "publishing",
    "audio",
    "company",
    "novel",
    "book",
    "volume",
}


def _person_name(value: str) -> bool:
    words = value.split()
    return (
        _MIN_NAME_WORDS <= len(words) <= _MAX_NAME_WORDS
        and not re.search(r"[,;&]", value)
        and all(word[0].isupper() or word.casefold() in _PARTICLES for word in words)
        and not any(word.casefold().strip(".,") in _GROUP_WORDS for word in words)
    )


def split_contributors(value: str | None) -> list[str]:
    """Split clear full-name lists; preserve organizations and ambiguous commas."""
    credit = (value or "").strip()
    if not credit:
        return []
    parts = re.split(r"\s+(?:and|&)\s+|\s*[;,]\s*", credit)
    if len(parts) > 1 and all(_person_name(part) or part.casefold() == "full cast" for part in parts):
        return list(dict.fromkeys(parts))
    return [credit]


class CatalogCredit(TypedDict):
    """Display-only credit, retaining the original catalog title elsewhere."""

    display_title: str
    author_credit: str
    credited_contributors: list[str]


def catalog_credit(value: str | None) -> CatalogCredit:
    """Recognize a final full-name credit without classifying arbitrary subtitles."""
    title = value or ""
    result: CatalogCredit = {"display_title": title, "author_credit": "", "credited_contributors": []}
    match = re.fullmatch(r"(.+)\s+[-–—]\s+(.+)", title)
    if match:
        credit = match[2].strip()
        people = split_contributors(credit)
        if people and all(_person_name(person) for person in people):
            result = {"display_title": match[1].strip(), "author_credit": credit, "credited_contributors": people}
    return result
