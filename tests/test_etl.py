import pytest
import pandas as pd
from src.utils.data_loader import load_data
from src.core.data_processor import process_salaries

def test_data_loader():
    df = load_data()
    assert isinstance(df, pd.DataFrame)
    # The intentional bug: expecting 'employee_id'
    assert 'employee_id' in df.columns

def test_data_processor():
    data = {
        'emp_id': [1, 2],
        'name': ['A', 'B'],
        'salary': [1000, 2000]
    }
    df = pd.DataFrame(data)
    avg = process_salaries(df)
    assert avg == 1500
