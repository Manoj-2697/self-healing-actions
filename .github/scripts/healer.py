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
RETRY_BRANCH = os.getenv('GITHUB_REF_NAME') # e.g. 'main', 'master', or 'gemini-fix-...'

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
            
            tracebacks = re.findall(r'Traceback \(most recent call last\):.*?(?:\r?\n.*?)+?(?=\r?\n\r?\n|\Z)', full_logs, re.DOTALL)
            assertions = re.findall(r'(_+ [^_]+ _+|E   .*|AssertionError:.*)', full_logs)
            
            error_context += f"\n--- Error Blocks found in Job: {job['name']} ---\n"
            if tracebacks:
                error_context += "\n--- Tracebacks ---\n" + "\n".join(tracebacks)
            if assertions:
                error_context += "\n--- Assertions/Summary ---\n" + "\n".join(assertions)
            
            if not tracebacks and not assertions:
                lines = full_logs.splitlines()
                error_context += "\n--- Last 50 lines (No pattern match) ---\n" + "\n".join(lines[-50:])
            
    return error_context

def get_codebase(logs):
    """
    Identifies Python files related to the failure.
    Priority:
    1. Python files mentioned in the error logs (Tracebacks).
    2. Python files changed in the current branch compared to default branch.
    3. If on default branch, Python files changed in the latest commit.
    """
    print(f"Identifying Python files for context (Current branch: {RETRY_BRANCH})...", flush=True)
    potential_files = set()
    
    # 1. Identify files from logs (Crucial if the bug is in a file NOT changed recently)
    log_candidates = re.findall(r'([a-zA-Z0-9_\-/]+\.py)', logs)
    for f in log_candidates:
        potential_files.add(f)

    # 2. Identify files changed in this branch
    try:
        # Detect default branch (main/master)
        remotes = subprocess.check_output(['git', 'remote', 'show', 'origin'], text=True)
        default_branch = "main" if "HEAD branch: main" in remotes else "master"
        
        diff_base = f"origin/{default_branch}"
        
        # Scenario A: If we are ON the default branch, compare vs the previous commit
        # Scenario B: If we are on a feature branch, compare vs the default branch
        if RETRY_BRANCH == default_branch:
            print(f"Workflow triggered on the base branch ({default_branch}). Analyzing latest commit changes...", flush=True)
            git_diff_cmd = ['git', 'diff', 'HEAD~1...HEAD', '--name-only']
        else:
            print(f"Workflow triggered on feature branch. Analyzing changes vs {diff_base}...", flush=True)
            git_diff_cmd = ['git', 'diff', f'{diff_base}...HEAD', '--name-only']
            
        branch_files = subprocess.check_output(git_diff_cmd, text=True, stderr=subprocess.STDOUT).splitlines()
        for f in branch_files:
            potential_files.add(f)
            
    except Exception as e:
        print(f"Diff Analysis Note: {e}. Falling back to latest commit scan.", flush=True)
        try:
            fallback = subprocess.check_output(['git', 'show', '--name-only', '--format=', 'HEAD'], text=True).splitlines()
            for f in fallback: potential_files.add(f)
        except: pass

    # 3. Filter and Clean
    cleaned_py_files = []
    for f in potential_files:
        rel_path = os.path.relpath(os.path.normpath(f), os.getcwd())
        if os.path.isfile(rel_path) and rel_path.endswith('.py') and not rel_path.startswith('.github'):
            cleaned_py_files.append(rel_path)
            
    cleaned_py_files = sorted(list(set(cleaned_py_files)))
    print(f"Identified {len(cleaned_py_files)} context files: {', '.join(cleaned_py_files)}", flush=True)

    codebase = {}
    for f in cleaned_py_files:
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

    # User's request: Identify and send Python files that are part of the changes + error logs
    codebase = get_codebase(logs)
    if not codebase:
        print("No related Python files identified. AI cannot heal without code context.", flush=True)
        return

    prompt = f"""
I am a CI/CD self-healing agent. A deployment recently failed with the following errors:

--- EXTRACTED ERROR LOGS ---
{logs}

--- RELATED CODEBASE ---
{json.dumps(codebase, indent=2)}

Analyze these specific errors and the files provided. Suggest a fix.
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
        
        # Tag the commit so finalize_pr.py can find the original branch to raise the PR against
        analysis_tag = f"[ANALYSIS]: {analysis}\n[ORIGINAL_BRANCH]: {RETRY_BRANCH}"
        os.system(f'git commit -m "Auto-fix by Gemini for run #{RUN_ID}\n\n{analysis_tag}"')
        
        # Authentication & Push
        pat_token = os.getenv('HEALER_PAT')
        if not pat_token or not pat_token.startswith('ghp_'):
            print("--- CRITICAL WARNING: HEALER_PAT NOT FOUND OR INVALID ---", flush=True)
            push_token = GITHUB_TOKEN
        else:
            print(f"Using HEALER_PAT for push...", flush=True)
            push_token = pat_token

        os.system('git config --local --unset-all http.https://github.com/.extraheader')
        remote_url = f"https://x-access-token:{push_token}@github.com/{REPO}.git"
        push_res = os.system(f'git push --set-upstream {remote_url} {fix_branch}')
        
        if push_res == 0:
            print(f"Fix successfully pushed! A new PR will be raised against '{RETRY_BRANCH}' upon verification.", flush=True)
        
    except Exception as e:
        print(f"Error in healing: {e}", flush=True)

if __name__ == "__main__":
    heal()
