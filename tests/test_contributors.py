# File: tests/test_contributors.py
"""Contributor credit edge cases and conservative title presentation."""

import pytest

from audiobook_automated.contributors import catalog_credit, split_contributors


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        (" ", []),
        ("Gert Heidenreich and Timmo Niesner", ["Gert Heidenreich", "Timmo Niesner"]),
        ("Jane Doe & John Smith", ["Jane Doe", "John Smith"]),
        ("Anna Elliott,Charles Veley", ["Anna Elliott", "Charles Veley"]),
        ("Jane Doe; John Smith and Alex Brown", ["Jane Doe", "John Smith", "Alex Brown"]),
        ("Jane Doe and Jane Doe", ["Jane Doe"]),
        (
            "Erik Bauersfeld, Gail Chugg, Bernard Mayes, Ray Reinhardt, full cast",
            ["Erik Bauersfeld", "Gail Chugg", "Bernard Mayes", "Ray Reinhardt", "full cast"],
        ),
        ("Jane Doe, John Smith, Full Cast", ["Jane Doe", "John Smith", "Full Cast"]),
        ("Smith, John", ["Smith, John"]),
        ("James Doe, Jr.", ["James Doe, Jr."]),
        ("Simon & Schuster Audio", ["Simon & Schuster Audio"]),
        ("Earth, Wind & Fire", ["Earth, Wind & Fire"]),
        ("Sørina Higgins, The Great Courses", ["Sørina Higgins, The Great Courses"]),
        ("Alexandra David-Neel", ["Alexandra David-Neel"]),
        ("Ludwig van Beethoven and Jane Doe", ["Ludwig van Beethoven", "Jane Doe"]),
    ],
)
def test_split_contributors(value: str | None, expected: list[str]) -> None:
    """Only divide lists whose components resemble complete individual names."""
    assert split_contributors(value) == expected


@pytest.mark.parametrize(
    ("title", "display", "credit"),
    [
        (None, "", ""),
        ("A plain title", "A plain title", ""),
        ("A title -  ", "A title -  ", ""),
        ("A title - A Novel", "A title - A Novel", ""),
        ("A title - Book 2", "A title - Book 2", ""),
        ("A title - Smith, John", "A title - Smith, John", ""),
        ("The Hobbit - J. R. R. Tolkien", "The Hobbit", "J. R. R. Tolkien"),
        ("A series - Second Line - Gregory Ashe", "A series - Second Line", "Gregory Ashe"),
        ("A title: A subtitle — Alexandra David-Neel", "A title: A subtitle", "Alexandra David-Neel"),
        ("A title - Anna Elliott,Charles Veley", "A title", "Anna Elliott,Charles Veley"),
    ],
)
def test_catalog_credit(title: str | None, display: str, credit: str) -> None:
    """Preserve internal punctuation and leave ambiguous suffixes unchanged."""
    result = catalog_credit(title)
    assert result["display_title"] == display
    assert result["author_credit"] == credit
    assert result["credited_contributors"] == (split_contributors(credit) if credit else [])
