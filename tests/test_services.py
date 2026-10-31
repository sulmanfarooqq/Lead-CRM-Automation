from app.services import normalize_phone, parse_budget

def test_normalize_pakistani_phone():
    assert normalize_phone("0300 1234567") == "+923001234567"

def test_invalid_phone_returns_none():
    assert normalize_phone("123") is None

def test_budget_units():
    assert parse_budget("1.5 crore") == 15000000
    assert parse_budget("PKR 750k") == 750000
    assert parse_budget("50 lakh") == 5000000
