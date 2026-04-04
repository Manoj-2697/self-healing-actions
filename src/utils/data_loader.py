import pandas as pd

def load_data():
    """
    Returns a sample DataFrame for testing purposes.
    """
    data = {
        'emp_id': [1, 2, 3],
        'name': ['Alice', 'Bob', 'Charlie'],
        'salary': [5000, 6000, 7000]
    }
    return pd.DataFrame(data)
