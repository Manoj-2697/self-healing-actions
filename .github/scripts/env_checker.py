import os
import sys
import requests
import re

def check_env_errors():
    github_token = os.getenv('GITHUB_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY')
    run_id = os.getenv('FAILED_RUN_ID') or os.getenv('GITHUB_RUN_ID')
    
    if not github_token or not repo or not run_id:
        print("Missing required environment variables for error checking.")
        sys.exit(0) # Not failing the check itself, just skip

    print(f"Checking logs for run {run_id} to identify environmental errors...", flush=True)
    headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github+json"}
    jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
    
    try:
        response = requests.get(jobs_url, headers=headers)
        jobs = response.json().get('jobs', [])
        
        full_logs = ""
        for job in jobs:
            if job['conclusion'] == 'failure':
                log_url = f"https://api.github.com/repos/{repo}/actions/jobs/{job['id']}/logs"
                log_res = requests.get(log_url, headers=headers)
                full_logs += log_res.text

        # Patterns that indicate environmental/manual fix required
        non_healable_patterns = {
            "SignatureDoesNotMatch": "Invalid AWS Secret Access Key signature.",
            "InvalidClientTokenId": "The AWS Access Key ID you provided does not exist in our records.",
            "NoCredentialsError": "Unable to locate credentials. Check your GitHub Secrets.",
            "ExpiredToken": "The security token included in the request is expired.",
            "AccessDenied": "User is not authorized to perform the action. Check IAM policies.",
            "ResourceNotFound": "The requested AWS resource was not found.",
        }

        for pattern, description in non_healable_patterns.items():
            if pattern in full_logs:
                print(f"\n[ENVIRONMENTAL ERROR DETECTED]: {pattern}")
                print(f"Description: {description}")
                print("ACTION REQUIRED: A human must fix this in GitHub Secrets or AWS IAM. AI healing aborted.")
                # Exit with non-zero code to stop the workflow or signal skip
                sys.exit(1)

        print("\nNo environmental errors detected. Safe to proceed with AI healing.", flush=True)
        sys.exit(0)

    except Exception as e:
        print(f"Error while checking logs: {e}")
        sys.exit(0) # Fallback to AI healing if check fails

if __name__ == "__main__":
    check_env_errors()
