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

def get_codebase(logs, include_all=False):
    """
    Step-by-step codebase collection as requested by the user.
    include_all=False: Only send changed/log-affected files.
    include_all=True: Send the entire project context as a fallback.
    """
    # 1. Collect files from logs
    log_files = re.findall(r'([a-zA-Z0-9_\-/]+\.py)', logs)
    
    # 2. Collect files from git diff (changed in this feature branch)
    changed_files = []
    try:
        git_diff_cmd = ['git', 'diff', 'origin/master...HEAD', '--name-only']
        changed_files = subprocess.check_output(git_diff_cmd, text=True, stderr=subprocess.STDOUT).splitlines()
    except Exception as e:
        print(f"Diff Note: {e}")

    # 3. Consolidate and Clean (Deduplicate + Filter + Exclude Infra)
    all_potential = log_files + changed_files
    cleaned_set = set()
    for f in all_potential:
        # Normalize to relative path to avoid duplicates (/home/runner/... vs app.py)
        rel_path = os.path.relpath(os.path.normpath(f), os.getcwd())
        # Filter: Must exist, be a .py file, and NOT be in .github (infrastructure)
        if (os.path.isfile(rel_path) and 
            rel_path.endswith('.py') and 
            not rel_path.startswith('.github') and 
            not rel_path.startswith('..')):
            cleaned_set.add(rel_path)

    primary_files = sorted(list(cleaned_set))

    codebase = {}
    
    # Logic: Only send primary (changed/log) files first
    if not include_all:
        if primary_files:
            print(f"Codebase Context (Targeted): {', '.join(primary_files)}", flush=True)
            for f in primary_files:
                with open(f, 'r', encoding='utf-8') as src:
                    codebase[f] = src.read()
            return codebase, False # False means 'not include_all'
        else:
            print("No targeted files found. Proceeding to fallback scan...", flush=True)
            include_all = True

    # Fallback: Send everything if primary is empty OR explicitly requested
    if include_all:
        print("Codebase Context (Full Scan): Including all project files.", flush=True)
        ignored_dirs = {'.git', 'Images', 'static', 'templates', '__pycache__', '.github'}
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                if file.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(root, file), os.getcwd())
                    try:
                        with open(rel_path, 'r', encoding='utf-8') as f:
                            codebase[rel_path] = f.read()
                    except: pass
    
    return codebase, True

def apply_fix(filename, new_content):
    print(f"Applying fix to {filename}...", flush=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

def heal():
    logs = get_failed_logs()
    if not logs:
        print("No failed job logs found.", flush=True)
        return

    # User's request: Start with only the specific changes
    codebase, is_full_scan = get_codebase(logs, include_all=False)
    
    prompt = f"""
I am a CI/CD self-healing agent. A deployment recently failed.
Analyze the logs and the PROVIDED codebase to suggest a fix.

--- FAILED LOGS ---
{logs}

--- CODEBASE ({'FULL' if is_full_scan else 'TARGETED CHANGES'}) ---
{json.dumps(codebase, indent=2)}

Your response MUST be a JSON object:
{{
  "analysis": "failure reason",
  "fixes": [ {{ "filename": "path", "content": "full content" }} ],
  "insufficient_context": false 
}}
If you cannot find the fix because some files are missing, set 'insufficient_context' to true.
"""
    
    print("Asking Gemini for a fix...", flush=True)
    response = model.generate_content(prompt)
    
    try:
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[len("```json"):].strip()
        if raw_text.endswith("```"): raw_text = raw_text[:-3].strip()
            
        fix_data = json.loads(raw_text)
        
        # Next step logic: If AI needs more files and we haven't sent them yet
        if fix_data.get('insufficient_context') and not is_full_scan:
            print("AI reported insufficient context. Retrying with full codebase...", flush=True)
            codebase, _ = get_codebase(logs, include_all=True)
            # Re-run heal with full codebase (one recursion)
            # Actually, I'll just re-call the model here to keeps it simple
            prompt = prompt.replace('TARGETED CHANGES', 'FULL PROJECT FALLBACK')
            prompt = prompt.replace(json.dumps(fix_data), json.dumps(codebase)) # Update codebase in prompt
            response = model.generate_content(prompt)
            # Parse again
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
            print(f"Fix pushed! Triggering verification signals...", flush=True)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
            requests.post(f"https://api.github.com/repos/{REPO}/dispatches", 
                          headers=headers, 
                          json={"event_type": "verify-fix", "client_payload": {"branch": fix_branch}})
            requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/cd.yaml/dispatches", 
                          headers=headers, 
                          json={"ref": fix_branch})
        
    except Exception as e:
        print(f"Error in healing: {e}", flush=True)

if __name__ == "__main__":
    heal()
