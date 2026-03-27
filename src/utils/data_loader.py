import pandas as pd
import os

def load_data():
    """
    Simulated data loader with a BUG:
    It expects 'employee_id' but the file will have 'emp_id'.
    """
    data = {
        'emp_id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'salary': [5000, 6000, '7000', 8000, 9000] # Note: one is a string
    }
    df = pd.DataFrame(data)
    
    # Intentional BUG: Accessing non-existent column
    print(f"Total Employees: {len(df['employee_id'])}")
    
    return df
