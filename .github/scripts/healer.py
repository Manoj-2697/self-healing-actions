import os
import sys
import requests
import json
import base64
import time
import google.generativeai as genai

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
REPO = os.getenv('GITHUB_REPOSITORY')
RUN_ID = os.getenv('GITHUB_RUN_ID')
RETRY_BRANCH = os.getenv('GITHUB_REF_NAME')

if not GEMINI_API_KEY:
    print("Error: No GEMINI_API_KEY provided.", flush=True)
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

def get_failed_logs():
    print(f"Fetching logs for run {RUN_ID} in {REPO}...", flush=True)
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    jobs_url = f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}/jobs"
    response = requests.get(jobs_url, headers=headers)
    jobs = response.json().get('jobs', [])
    
    failed_job_logs = ""
    for job in jobs:
        if job['conclusion'] == 'failure':
            job_id = job['id']
            log_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs"
            log_response = requests.get(log_url, headers=headers)
            failed_job_logs += f"\n--- Logs from Job: {job['name']} ---\n"
            failed_job_logs += log_response.text
            
    return failed_job_logs

def get_codebase():
    codebase = {}
    ignored_dirs = {'.git', 'Images', 'static', 'templates', '__pycache__', '.github'}
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(('.py', '.txt', '.yaml', '.yml', '.md', '.html')):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        codebase[file_path] = f.read()
                except Exception as e:
                    print(f"Could not read {file_path}: {e}", flush=True)
    return codebase

def apply_fix(filename, new_content):
    print(f"Applying fix to {filename}...", flush=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

def heal():
    logs = get_failed_logs()
    if not logs:
        print("No failed job logs found.", flush=True)
        return

    codebase = get_codebase()
    
    prompt = f"""
I am a CI/CD self-healing agent. A deployment recently failed.
Analyze the logs and codebase below and suggest a fix.

--- FAILED LOGS ---
{logs}

--- CODEBASE ---
{json.dumps(codebase, indent=2)}

Your response MUST be a JSON object:
{{
  "analysis": "failure reason",
  "fixes": [ {{ "filename": "path", "content": "full content" }} ]
}}
Only return JSON.
"""
    
    print("Asking Gemini for a fix...", flush=True)
    response = model.generate_content(prompt)
    
    try:
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[len("```json"):].strip()
        if raw_text.endswith("```"): raw_text = raw_text[:-3].strip()
            
        fix_data = json.loads(raw_text)
        print(f"Analysis: {fix_data.get('analysis')}", flush=True)
        
        fixes = fix_data.get('fixes', [])
        if not fixes:
            print("No fix found.", flush=True)
            return

        for fix in fixes:
            apply_fix(fix['filename'], fix['content'])
            
        fix_branch = f"gemini-fix-{int(time.time())}"
        print(f"Creating and pushing branch: {fix_branch}...", flush=True)
        
        os.system(f'git checkout -b {fix_branch}')
        os.system('git config user.name "Gemini Healer"')
        os.system('git config user.email "healer@gemini.ai"')
        os.system('git add .')
        os.system(f'git commit -m "Auto-fix by Gemini for run #{RUN_ID}"')
        
        remote_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{REPO}.git"
        os.system(f'git push {remote_url} {fix_branch}')
        
        print("Opening Pull Request...", flush=True)
        pr_url = f"https://api.github.com/repos/{REPO}/pulls"
        pr_data = {
            "title": f"Gemini Auto-Fix: {fix_data.get('analysis')[:50]}...",
            "body": f"### 🤖 Gemini Self-Healing PR\n\n**Analysis:**\n{fix_data.get('analysis')}\n\nGenerated for Run ID: {RUN_ID}",
            "head": fix_branch,
            "base": RETRY_BRANCH
        }
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        pr_res = requests.post(pr_url, headers=headers, json=pr_data)
        
        if pr_res.status_code == 201:
            print(f"PR created successfully: {pr_res.json().get('html_url')}", flush=True)
        else:
            print(f"Failed to create PR (HTTP {pr_res.status_code}): {pr_res.text}", flush=True)

    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    heal()
