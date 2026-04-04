import json
import sys
import os

# Add the root of the Lambda (containing core/ and utils/) to sys.path
# In AWS Lambda, the extraction dir is in the sys.path by default, 
# but being explicit about our structure helps.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import data_loader
from core import data_processor

def handler(event, context):
    """
    Main ETL Lambda Entry Point
    """
    print(f"Triggering AI-Resilient ETL for event: {json.dumps(event)}")
    
    try:
        # Load and Process (This is where the 'healing' might be needed if broken)
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
        # Note: If this fails in production, the healer doesn't heal the LIVE lambda instantly,
        # but the CI failure on push will heal the codebase for the next deployment.
        raise e

if __name__ == "__main__":
    # Simulate a local run (replacing the old main.py)
    print("Starting Local ETL Simulation...")
    result = handler({"local": True}, None)
    print(json.dumps(result, indent=2))
