import os
import sys

# ETL project organized into src/ structure
from utils import data_loader
from core import data_processor

def run_etl():
    """
    Simulated ETL entry point with a BUG:
    Wrong function call or missing arg.
    """
    try:
        print("Starting ETL Process Build #23334599684...")
        
        # 1. LOAD DATA (Will fail with KeyError: 'employee_id')
        df = data_loader.load_data()
        
        # 2. PROCESS DATA (Will fail with TypeError if it got here)
        avg = data_processor.process_salaries(df)
        
        print("ETL Process Completed Successfuly!")
        return 0
        
    except Exception as e:
        print(f"CRITICAL ETL FAILURE: {e}", flush=True)
        # We raise the exception so the CI knows it failed
        raise e

if __name__ == "__main__":
    exit_code = run_etl()
    sys.exit(exit_code)
