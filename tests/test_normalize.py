import pytest

from app.services import UNKNOWN_NAME, normalize_lead, normalize_phone, parse_budget


@pytest.mark.parametrize("raw, expected", [
    ("0300 1234567", "+923001234567"),
    ("0300-1234567", "+923001234567"),
    ("+92 300 1234567", "+923001234567"),
    ("00923001234567", "+923001234567"),
    ("923001234567", "+923001234567"),
    ("3001234567", "+923001234567"),
    (3001234567, "+923001234567"),
    ("+1 415 555 2671", "+14155552671"),
])
def test_valid_phone_numbers(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "abc", "", None, "   ", "+", "0"])
def test_invalid_phone_numbers_return_none(raw):
    assert normalize_phone(raw) is None


def test_phone_uses_configured_country_code():
    assert normalize_phone("07911 123456", "+44") == "+447911123456"


@pytest.mark.parametrize("raw, expected", [
    ("1.5 crore", 15_000_000),
    ("PKR 750k", 750_000),
    ("50 lakh", 5_000_000),
    ("50 lac", 5_000_000),
    ("2 million", 2_000_000),
    ("$1.2m", 1_200_000),
    ("250 thousand", 250_000),
    ("1,50,00,000", 15_000_000),
    ("rs. 3 cr", 30_000_000),
    (5_000_000, 5_000_000),
    ("1500000", 1_500_000),
])
def test_budget_parsing(raw, expected):
    assert parse_budget(raw) == expected


@pytest.mark.parametrize("raw", ["negotiable", "", None, "0", "   "])
def test_unreadable_budgets_return_none(raw):
    assert parse_budget(raw) is None


def test_budget_unit_must_be_a_whole_word():
    """'5 marla' must not be read as 5 million: the 'm' is only a unit when it stands alone."""
    assert parse_budget("5 marla") != 5_000_000
    assert parse_budget("3 kanal") != 3_000


def test_budget_rounds_half_up_like_javascript():
    assert parse_budget("0.0000005 million") == 1  # 0.5 -> 1 (Python's round() would give 0)


def test_clean_lead_has_no_flags():
    n = normalize_lead({"full_name": "  Ahmed   Khan ", "email": " Ahmed@Example.COM ", "phone": "0300 1234567",
                        "budget": "1 crore", "buying_timeline": "7 days"})
    assert (n["full_name"], n["email"], n["phone"], n["budget_value"]) == ("Ahmed Khan", "ahmed@example.com", "+923001234567", 10_000_000)
    assert n["flags"] == [] and n["rejected"] is False


def test_missing_name_is_kept_and_flagged():
    n = normalize_lead({"email": "a@b.co"})
    assert n["full_name"] == UNKNOWN_NAME and "Missing name" in n["flags"] and not n["rejected"]


def test_invalid_email_with_valid_phone_is_kept_and_flagged():
    n = normalize_lead({"full_name": "A", "email": "nope", "phone": "03001234567"})
    assert n["email"] == "" and n["phone"] == "+923001234567"
    assert n["flags"] == ["Invalid email format"] and not n["rejected"]


def test_no_valid_contact_is_rejected():
    n = normalize_lead({"full_name": "A", "email": "nope", "phone": "12"})
    assert n["rejected"] and n["reject_reason"] == "No valid email or phone number"
    assert n["flags"] == ["Invalid email format", "Invalid phone number"]


def test_secret_is_never_kept_in_the_raw_payload():
    n = normalize_lead({"full_name": "A", "email": "a@b.co", "secret": "hunter2"})
    assert "secret" not in n["raw"]
