import pandas as pd

def process_salaries(df):
    """
    Simulated data processor with a BUG:
    It will fail because one of the 'salary' values is a string ('7000'), 
    but it's trying to calculate a mean without casting.
    """
    print("Calculating average salary...")
    
    # Fixed: Cast the 'salary' column to numeric to handle string values before calculating the mean
    df['salary'] = pd.to_numeric(df['salary'])
    avg_salary = df['salary'].mean()
    
    print(f"Average Salary: {avg_salary}")
    
    return avg_salary