import pandas as pd

def process_salaries(df):
    """
    Processes salary data to return the average value.
    """
    if df is None or df.empty or 'salary' not in df.columns:
        return 0.0
    return df['salary'].mean()