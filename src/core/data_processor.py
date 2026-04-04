import pandas as pd

def process_salaries(df):
    """
    Calculates the average salary from the provided DataFrame.
    """
    if df is None or df.empty or 'salary' not in df.columns:
        return 0
    return df['salary'].mean()