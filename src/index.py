import json
import os
from utils import data_loader
from core import data_processor

def handler(event, context):
    """
    Main ETL Lambda Entry Point
    """
    print(f"Triggering AI-Resilient ETL for event: {json.dumps(event)}")
    
    try:
        # Load and Process
        df = data_loader.load_data()
        avg_salary = data_processor.process_salaries(df)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'ETL Success!',
                'average_salary': float(avg_salary)
            })
        }
        
    except Exception as e:
        print(f"ETL Execution Failed: {e}")
        raise e

if __name__ == "__main__":
    # Simulate a local run
    print("Starting Local ETL Simulation...")
    result = handler({"local": True}, None)
    print(json.dumps(result, indent=2))