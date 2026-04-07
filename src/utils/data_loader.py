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
        'salary': [5000, 6000, 7000, 8000, '9000']
    }
df = pd.DataFrame(data)
    
    # Fixed: Accessing the correct column name 'emp_id'
    print(f"Total Employees: {len(df['emp_id'])}")
    
    return df
