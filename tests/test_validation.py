import pytest

from rejections import RejectionReason
from validation import validate_custom_situation


@pytest.mark.parametrize("text,expected", [
    ("", RejectionReason.EMPTY),
    ("   \n  ", RejectionReason.EMPTY),
    ("коротко", RejectionReason.TOO_SHORT),
    ("а" * 500, RejectionReason.TOO_LONG),
    ("Начальник год не даёт повышение, пишу вот тут https://example.com", RejectionReason.CONTAINS_LINK),
    ("!" * 40, RejectionReason.GARBAGE),
    ("Хочу попросить у начальника повышение зарплаты, но он ссылается на бюджет", None),
])
def test_validate_custom_situation(text, expected):
    assert validate_custom_situation(text) == expected
