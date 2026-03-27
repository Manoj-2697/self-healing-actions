import os
import sys
import requests
import json
import base64
import time
import google.generativeai as genai
import re
import subprocess

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
    print(f"Fetching and parsing logs for run {RUN_ID} (extracting error blocks)...", flush=True)
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    jobs_url = f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}/jobs"
    response = requests.get(jobs_url, headers=headers)
    jobs = response.json().get('jobs', [])
    
    error_context = ""
    for job in jobs:
        if job['conclusion'] == 'failure':
            job_id = job['id']
            log_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs"
            log_response = requests.get(log_url, headers=headers)
            full_logs = log_response.text
            
            # Use Regex to Extract Error Blocks (Tracebacks, Assertion Errors)
            # Pattern 1: Python Tracebacks
            tracebacks = re.findall(r'Traceback \(most recent call last\):.*?(?:\r?\n.*?)+?(?=\r?\n\r?\n|\Z)', full_logs, re.DOTALL)
            # Pattern 2: Pytest/Generic Assertion Errors
            assertions = re.findall(r'(_+ [^_]+ _+|E   .*|AssertionError:.*)', full_logs)
            
            error_context += f"\n--- Error Blocks found in Job: {job['name']} ---\n"
            if tracebacks:
                error_context += "\n--- Tracebacks ---\n" + "\n".join(tracebacks)
            if assertions:
                error_context += "\n--- Assertions/Summary ---\n" + "\n".join(assertions)
            
            if not tracebacks and not assertions:
                # Fallback to last 50 lines if no pattern matches
                lines = full_logs.splitlines()
                error_context += "\n--- Last 50 lines (No pattern match) ---\n" + "\n".join(lines[-50:])
            
    return error_context

def get_codebase():
    """
    User request: Only identify and send Python files that are part of the CHANGES.
    """
    print("Identifying Python files in feature branch changes...", flush=True)
    changed_py_files = []
    try:
        # Detect default branch automatically
        remotes = subprocess.check_output(['git', 'remote', 'show', 'origin'], text=True)
        default_branch = "main" if "HEAD branch: main" in remotes else "master"
        
        # Get all files changed in this branch vs base
        git_diff_cmd = ['git', 'diff', f'origin/{default_branch}...HEAD', '--name-only']
        files = subprocess.check_output(git_diff_cmd, text=True, stderr=subprocess.STDOUT).splitlines()
        
        # Filter for Python files that exist
        for f in files:
            rel_path = os.path.relpath(os.path.normpath(f), os.getcwd())
            if os.path.isfile(rel_path) and rel_path.endswith('.py') and not rel_path.startswith('.github'):
                changed_py_files.append(rel_path)
        
        # Deduplicate
        changed_py_files = sorted(list(set(changed_py_files)))
        print(f"Verified {len(changed_py_files)} changed Python files: {', '.join(changed_py_files)}", flush=True)
        
    except Exception as e:
        print(f"Error identifying changed files: {e}", flush=True)

    codebase = {}
    for f in changed_py_files:
        try:
            with open(f, 'r', encoding='utf-8') as src:
                codebase[f] = src.read()
        except: pass
        
    return codebase

def apply_fix(filename, new_content):
    print(f"Applying fix to {filename}...", flush=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

def heal():
    logs = get_failed_logs()
    if not logs:
        print("No failed job context found.", flush=True)
        return

    codebase = get_codebase()
    if not codebase:
        print("No changed Python files identified to send for context.", flush=True)
        return

    prompt = f"""
I am a CI/CD self-healing agent. A deployment recently failed with the following errors:

--- EXTRACTED ERROR LOGS ---
{logs}

--- CHANGED CODEBASE ---
{json.dumps(codebase, indent=2)}

Analyze these specific errors and the modified files. Suggest a fix.
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
        analysis = fix_data.get('analysis', 'No analysis')
        print(f"\n--- AI ANALYSIS ---\n{analysis}\n------------------\n", flush=True)
        
        fixes = fix_data.get('fixes', [])
        if not fixes:
            print("No fix found.", flush=True)
            return

        for fix in fixes:
            apply_fix(fix['filename'], fix['content'])
            
        print("--- CHANGES APPLIED (DIFF) ---", flush=True)
        os.system('git diff')
        print("-------------------------------", flush=True)

        fix_branch = f"gemini-fix-{int(time.time())}"
        print(f"Pushing fix to branch: {fix_branch}...", flush=True)
        os.system(f'git checkout -b {fix_branch}')
        os.system('git config user.name "Gemini Healer"')
        os.system('git config user.email "healer@gemini.ai"')
        os.system('git add .')
        
        commit_msg = f"Auto-fix by Gemini for run #{RUN_ID}\n\n[ANALYSIS]: {analysis}\n[ORIGINAL_BRANCH]: {RETRY_BRANCH}"
        os.system(f'git commit -m "{commit_msg}"')
        
        token = os.getenv('HEALER_PAT') or GITHUB_TOKEN
        remote_url = f"https://x-access-token:{token}@github.com/{REPO}.git"
        push_res = os.system(f'git push {remote_url} {fix_branch}')
        
        if push_res == 0:
            print(f"Fix successfully pushed to {fix_branch}.", flush=True)
        
    except Exception as e:
        print(f"Error in healing: {e}", flush=True)

if __name__ == "__main__":
    heal()
