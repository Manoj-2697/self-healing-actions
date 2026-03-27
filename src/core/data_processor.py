import pandas as pd

def process_salaries(df):
    """
    Simulated data processor:
    Converts the 'salary' column to numeric to ensure the mean can be calculated
    even if some values are provided as strings.
    """
    print("Calculating average salary...")
    
    # Ensure salary column is numeric (handles mixed string/int types)
    df['salary'] = pd.to_numeric(df['salary'])
    
    avg_salary = df['salary'].mean()
    
    print(f"Average Salary: {avg_salary}")
    
    return avg_salary
