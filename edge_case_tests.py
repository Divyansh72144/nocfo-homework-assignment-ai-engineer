"""Test edge cases for the matching system"""

import json
from pathlib import Path
from src.match import (
    find_attachment, find_transaction,
    _normalize_reference, _names_match, _are_dates_compatible,
    _get_attachment_counterparty_names, _calculate_match_score
)

def test_edge_cases():
    print("Edge case tests\n")
    
    # Reference normalization edge cases
    print("Reference Normalization Edge Cases")
    test_refs = [
        ("", ""),                           # Empty reference
        ("   ", ""),                        # Whitespace only
        ("0000", "0"),                      # All zeros
        ("00000000000", "0"),               # Many zeros
        ("000123", "123"),                  # Leading zeros
        ("RF00 0000 0000 1234", "RF1234"),  # Finnish Banking reference
        ("12 34 56", "123456"),             # Spaces
        ("  12  34  56  ", "123456"),       # Extra spaces
        ("abc123def", "ABC123DEF"),         # Mixed case
        ("12.34-56", "12.34-56"),           # Special chars preserved
    ]
    
    for input_ref, expected in test_refs:
        result = _normalize_reference(input_ref)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{input_ref}' -> '{result}' (expected: '{expected}')")
    
    # Name matching edge cases
    print("\nName matching edge cases")
    name_tests = [
        ("", "", False),
        ("Jane Smith", "", False),
        ("", "John Doe", False),
        ("Jane Smith", "Jane Smith", True),
        ("  Jane   Smith  ", "Jane Smith", True),
        ("jane smith", "JANE SMITH", True),
        ("Jane Doe", "Jane Doe Design", True),
        ("John Doe", "John Doe Consulting", True),
        ("Matti Meikäläinen", "Matti Meikäläinen Oy", True),
        ("Best Supplies EMEA", "Best Supplies Inc", True),
        ("Global Trading Corp", "Global Corp Trading", True),
        ("Jane Smith", "John Smith", False),
        ("Jane Doe", "Jane Smith", False),
        ("Apple Inc", "Orange Inc", False),
        ("A", "B", False),
    ]
    
    for name1, name2, expected in name_tests:
        result = _names_match(name1, name2)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{name1}' vs '{name2}' -> {result} (expected: {expected})")
    
    # Date compatibility edge cases
    print("\nDate compatibility edge cases")
    
    # Create test attachment data
    def test_date_compat(tx_date, att_dates, expected):
        att_data = att_dates
        result = _are_dates_compatible(tx_date, att_data)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} TX:{tx_date} vs ATT:{att_dates} -> {result} (expected: {expected})")
    
    # Valid date ranges (15-day tolerance)
    test_date_compat("2024-07-15", {"due_date": "2024-07-15"}, True)      # Exact match
    test_date_compat("2024-07-15", {"due_date": "2024-07-01"}, True)      # 14 days (within tolerance)
    test_date_compat("2024-07-15", {"due_date": "2024-07-30"}, True)      # 15 days (at boundary)
    test_date_compat("2024-07-15", {"due_date": "2024-06-30"}, True)      # 15 days before
    
    # Invalid date ranges
    test_date_compat("2024-07-15", {"due_date": "2024-07-31"}, False)     # 16 days (outside tolerance)
    test_date_compat("2024-07-15", {"due_date": "2024-06-29"}, False)     # 16 days before
    
    # Multiple date fields
    test_date_compat("2024-07-15", {
        "invoicing_date": "2024-08-01",  # 17 days (invalid)
        "due_date": "2024-07-20"         # 5 days (valid)
    }, True)  # Should match due_date
    
    # Edge case: Invalid date formats
    test_date_compat("invalid", {"due_date": "2024-07-15"}, False)
    test_date_compat("2024-07-15", {"due_date": "invalid"}, False)
    test_date_compat("2024-07-15", {}, False)                             # No dates
    test_date_compat("2024-07-15", {"due_date": None}, False)             # Null date
    
    # Amount matching edge cases
    print("\nAmount matching edge cases")
    
    def test_amount_match(tx_amount, att_amount, expected_score):
        transaction = {"amount": tx_amount, "date": "2024-07-15", "contact": None}
        attachment = {"data": {"total_amount": att_amount, "due_date": "2024-07-15"}}
        score, _ = _calculate_match_score(transaction, attachment)
        expected_pass = expected_score > 0
        actual_pass = score > 0
        status = "PASS" if actual_pass == expected_pass else "FAIL"
        print(f"  {status} TX:{tx_amount} vs ATT:{att_amount} -> score:{score}")
    
    test_amount_match(175.00, 175.00, 3)
    test_amount_match(-175.00, 175.00, 3)
    test_amount_match(200.00, 200.01, 0)
    test_amount_match(50.00, 50.005, 3)
    test_amount_match(35.00, 35.00, 3)
    test_amount_match(-35.00, 35.00, 3)
    
    test_amount_match(175.00, 200.00, 0)
    test_amount_match(None, 175.00, 0)
    test_amount_match(50.00, None, 0)
    
    # Counterparty extraction edge cases
    print("\nCounterparty extraction edge cases")
    
    def test_counterparty_extraction(attachment_data, expected):
        attachment = {"data": attachment_data}
        result = _get_attachment_counterparty_names(attachment)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} {attachment_data} -> {result}")
    
    test_counterparty_extraction({"supplier": "Jane Doe Design"}, ["Jane Doe Design"])
    test_counterparty_extraction({"issuer": "John Doe Consulting", "recipient": "Jane Smith"}, ["John Doe Consulting", "Jane Smith"])
    
    test_counterparty_extraction({}, [])
    test_counterparty_extraction({"supplier": ""}, [])
    test_counterparty_extraction({"supplier": None}, [])
    test_counterparty_extraction({"supplier": "Example Company Oy"}, [])
    test_counterparty_extraction({"other_field": "Jane Doe"}, [])
    
    # Scoring edge cases
    print("\nScoring system edge cases")
    
    def test_scoring(tx_data, att_data, expected_min_score):
        transaction = {"amount": 100, "date": "2024-07-15", "contact": None, **tx_data}
        attachment = {"data": {"total_amount": 100, "due_date": "2024-07-15", **att_data}}
        score, has_match = _calculate_match_score(transaction, attachment)
        meets_min = score >= expected_min_score
        status = "PASS" if meets_min else "FAIL"
        print(f"  {status} Score: {score}, Has_match: {has_match} (expected >={expected_min_score})")
        return score, has_match
    
    test_scoring({}, {}, 4)
    test_scoring({"contact": "Jane Smith"}, {"recipient": "Jane Smith"}, 7)
    test_scoring({"contact": None}, {"supplier": "Jane Doe Design"}, 6)
    
    test_scoring({"amount": 200}, {"total_amount": 175}, 0)
    test_scoring({"date": "2024-08-15"}, {"due_date": "2024-06-15"}, 3)
    test_scoring({"contact": "Jane Smith"}, {"supplier": "John Doe"}, 3)
    
    # Real-world edge cases
    print("\nReal-world edge cases")
    
    # Test with actual problematic data
    def test_real_scenario(scenario_name, transaction, attachments, expected_result):
        result = find_attachment(transaction, attachments)
        result_id = result['id'] if result else None
        expected_id = expected_result['id'] if expected_result else None
        status = "PASS" if result_id == expected_id else "FAIL"
        print(f"  {status} {scenario_name}: Found ATT {result_id} (expected {expected_id})")
    
    tx_duplicate = {"id": 9001, "amount": -175, "date": "2024-06-16", "contact": "Jane Smith"}
    att_a = {"id": 8001, "data": {"total_amount": 175, "due_date": "2024-07-15", "recipient": "Jane Smith"}}
    att_b = {"id": 8002, "data": {"total_amount": 175, "due_date": "2024-07-15", "supplier": "John Doe"}}
    test_real_scenario("Duplicate amounts", tx_duplicate, [att_a, att_b], att_a)
    
    tx_similar = {"id": 9002, "amount": -200, "date": "2024-06-18", "contact": "Jane Doe"}
    att_corp = {"id": 8003, "data": {"total_amount": 200, "due_date": "2024-07-18", "supplier": "Jane Doe"}}
    att_corp2 = {"id": 8004, "data": {"total_amount": 200, "due_date": "2024-07-18", "supplier": "Jane Doe Design"}}
    test_real_scenario("Similar names", tx_similar, [att_corp, att_corp2], att_corp2)
    
    tx_precise = {"id": 9003, "amount": -50.00, "date": "2024-07-15", "contact": None}
    att_precise = {"id": 8005, "data": {"total_amount": 50.05, "due_date": "2024-07-15"}}
    test_real_scenario("Amount precision", tx_precise, [att_precise], None)
    
    print("\nEdge case testing complete")

if __name__ == "__main__":
    test_edge_cases()