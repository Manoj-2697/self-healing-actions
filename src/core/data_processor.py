import pandas as pd

def process_salaries(df):
    """
    Simulated data processor:
    Fixed by casting the 'salary' column to numeric before calculating the mean.
    """
    print("Calculating average salary...")
    
    # Convert column to numeric to handle mixed types (e.g., strings like '7000')
    avg_salary = pd.to_numeric(df['salary']).mean()
    
    print(f"Average Salary: {avg_salary}")
    
    return avg_salary
