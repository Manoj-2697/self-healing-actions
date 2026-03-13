import pytest

def test_self_healing_trigger():
    """
    This test is intentionally designed to fail. 
    It will trigger the 'self-healing' job in the GitHub Actions pipeline.
    Gemini will then analyze the failure logs and correct this file.
    """
    expected_value = 10
    actual_value = 5 + 4  # This is intentionally wrong (should be 5 + 5 or expected should be 9)
    
    print(f"Checking if {actual_value} equals {expected_value}")
    assert actual_value == expected_value, f"Error: Expected {expected_value} but got {actual_value}. Triggering AI Healing..."
