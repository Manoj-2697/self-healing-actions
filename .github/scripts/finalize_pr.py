import os
import json
import urllib.request
import subprocess
import sys

def get_git_info():
    try:
        # Get the commit message of the latest commit
        result = subprocess.run(['git', 'log', '-1', '--pretty=%B'], capture_output=True, text=True)
        message = result.stdout
        
        analysis = "No detailed analysis provided."
        original_branch = "master"
        
        if "[ANALYSIS]:" in message:
            analysis = message.split("[ANALYSIS]:")[1].split("[ORIGINAL_BRANCH]:")[0].strip()
        
        if "[ORIGINAL_BRANCH]:" in message:
            original_branch = message.split("[ORIGINAL_BRANCH]:")[1].strip()
            
        return analysis, original_branch
    except Exception as e:
        print(f"Warning: Could not extract analysis from git log. {e}")
        return "Automatic fix by Gemini.", "master"

def finalize_pr():
    print("Step 1: Extracting analysis from latest commit message...", flush=True)
    analysis, original_branch = get_git_info()
    
    current_branch = os.environ.get('GITHUB_REF_NAME')
    repo = os.environ.get('GITHUB_REPOSITORY')
    token = os.environ.get('GITHUB_TOKEN')

    print(f"Step 2: Preparing Pull Request for branch {current_branch} (base: {original_branch})...", flush=True)
    title = f"Gemini Verified Fix: {analysis[:50]}..."
    body = f"""### 🤖 Gemini Verified Fix

**AI Analysis:**
{analysis}

**Validation Result:**
Verification tests run on the self-hosted runner: **✅ PASSED**

*Note: This PR was automatically opened following a successful verification rerun.*
"""

    pr_payload = {
        'title': title,
        'body': body,
        'base': original_branch,
        'head': current_branch
    }

    print("Step 3: Triggering GitHub API to create Pull Request...", flush=True)
    api_url = f"https://api.github.com/repos/{repo}/pulls"
    
    try:
        encoded_data = json.dumps(pr_payload).encode('utf-8')
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json'
        }
        
        req = urllib.request.Request(api_url, data=encoded_data, headers=headers)
        with urllib.request.urlopen(req) as response:
            res_content = response.read().decode('utf-8')
            res_data = json.loads(res_content)
            print(f"SUCCESS: Pull Request created: {res_data.get('html_url')}", flush=True)
            
    except urllib.error.HTTPError as e:
        print(f"ERROR: API request failed. Status: {e.code}", flush=True)
        print(f"Response: {e.read().decode('utf-8')}", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)

if __name__ == "__main__":
    finalize_pr()
