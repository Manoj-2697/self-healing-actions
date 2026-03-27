import pandas as pd

def process_salaries(df):
    """
    Simulated data processor with a BUG:
    It will fail because one of the 'salary' values is a string ('7000'), 
    but it's trying to calculate a mean without casting.
    """
    print("Calculating average salary...")
    
    # Intentional BUG: Mean on un-cast string/object column
    avg_salary = df['salary'].mean()
    
    print(f"Average Salary: {avg_salary}")
    
    return avg_salary
