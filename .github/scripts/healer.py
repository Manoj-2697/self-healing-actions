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
RUN_ID = os.getenv('FAILED_RUN_ID') or os.getenv('GITHUB_RUN_ID')
RETRY_BRANCH = os.getenv('GITHUB_REF_NAME')

if not GEMINI_API_KEY:
    print("Error: No GEMINI_API_KEY provided.", flush=True)
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

def get_failed_logs():
    print(f"Grepping logs for run {RUN_ID} (extracting error messages only)...", flush=True)
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
            
            # GREG ERROR MESSAGE Strategy: Capture Tracebacks and explicit Exception lines
            tracebacks = re.findall(r'Traceback \(most recent call last\):.*?(?:\r?\n.*?)+?(?=\r?\n\r?\n|\Z)', full_logs, re.DOTALL)
            assertions = re.findall(r'(_+ [^_]+ _+|E   .*|AssertionError:.*)', full_logs)
            generic_errors = re.findall(r'(\w+Error:.*|\w+Exception:.*)', full_logs)
            tf_errors = re.findall(r'(│ Error:.*?(?:\r?\n.*?)+?(?=\r?\n\r?\n|╵))', full_logs, re.DOTALL)
            
            error_context += f"\n--- Error Block Job: {job['name']} ---\n"
            if tracebacks:
                error_context += "\n--- Tracebacks ---\n" + "\n".join(tracebacks)
            if tf_errors:
                error_context += "\n--- Terraform Errors ---\n" + "\n".join(tf_errors)
            if assertions or generic_errors:
                error_context += "\n--- Error Messages ---\n" + "\n".join(set(assertions + generic_errors))
            
            if not error_context:
                lines = full_logs.splitlines()
                error_context += "\n--- Last 30 lines ---\n" + "\n".join(lines[-30:])
            
    return error_context

def get_codebase(logs):
    print(f"Identifying related Python files (Branch: {RETRY_BRANCH})...", flush=True)
    potential_files = set()
    
    # 1. Grab files from log tracebacks
    log_candidates = re.findall(r'([a-zA-Z0-9_\-/]+\.py)', logs)
    for f in log_candidates: potential_files.add(f)

    # 2. Grab files from git changes
    try:
        remotes = subprocess.check_output(['git', 'remote', 'show', 'origin'], text=True)
        default_branch = "main" if "HEAD branch: main" in remotes else "master"
        
        # Scenario: If we are already on a fix branch, compare vs the original base (detected from commit history or default)
        # But for logic simplicity: if on main/master, compare vs HEAD~1. Else, compare vs default.
        if RETRY_BRANCH == default_branch:
            git_diff_cmd = ['git', 'diff', 'HEAD~1...HEAD', '--name-only']
        else:
            git_diff_cmd = ['git', 'diff', f'origin/{default_branch}...HEAD', '--name-only']
            
        branch_files = subprocess.check_output(git_diff_cmd, text=True, stderr=subprocess.STDOUT).splitlines()
        for f in branch_files: potential_files.add(f)
            
    except:
        try:
            fallback = subprocess.check_output(['git', 'show', '--name-only', '--format=', 'HEAD'], text=True).splitlines()
            for f in fallback: potential_files.add(f)
        except: pass

    cleaned_py_files = []
    for f in potential_files:
        rel_path = os.path.relpath(os.path.normpath(f), os.getcwd())
        if os.path.isfile(rel_path) and (rel_path.endswith('.py') or rel_path.endswith('.tf')) and not rel_path.startswith('.github'):
            cleaned_py_files.append(rel_path)
            
    cleaned_py_files = sorted(list(set(cleaned_py_files)))
    print(f"Sharing {len(cleaned_py_files)} files with Gemini: {', '.join(cleaned_py_files)}", flush=True)

    codebase = {}
    for f in cleaned_py_files:
        try:
            with open(f, 'r', encoding='utf-8') as src: codebase[f] = src.read()
        except: pass
    return codebase

def apply_fix(filename, new_content):
    print(f"Applying fix to {filename}...", flush=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

def heal():
    logs = get_failed_logs()
    if not logs: return
    
    codebase = get_codebase(logs)
    if not codebase: return

    prompt = f"Failure errors:\n{logs}\n\nCode context:\n{json.dumps(codebase, indent=2)}\n\nSuggest a fix. Return JSON: {{'analysis': '...', 'fixes': [{{'filename': '...', 'content': '...'}}]}}"
    
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
        if not fixes: return

        for fix in fixes: apply_fix(fix['filename'], fix['content'])
            
        print("--- CHANGES APPLIED (DIFF) ---", flush=True)
        os.system('git diff')
        print("-------------------------------", flush=True)

        # BRANCH LOGIC: Reuse existing gemini-fix branch if we are currently on one
        if RETRY_BRANCH.startswith("gemini-fix-"):
            fix_branch = RETRY_BRANCH
            print(f"Continuing work on existing fix branch: {fix_branch}", flush=True)
        else:
            fix_branch = f"gemini-fix-{int(time.time())}"
            print(f"Creating new fix branch: {fix_branch}", flush=True)
            os.system(f'git checkout -b {fix_branch}')

        os.system('git config user.name "Gemini Healer"')
        os.system('git config user.email "healer@gemini.ai"')
        os.system('git add .')
        
        # Pass the original branch name in the metadata so we know where to merge eventually
        orig_branch = RETRY_BRANCH if not RETRY_BRANCH.startswith("gemini-fix-") else "main" # logic fallback
        analysis_tag = f"[ANALYSIS]: {analysis}\n[ORIGINAL_BRANCH]: {orig_branch}"
        os.system(f'git commit -m "Auto-fix cycle for run #{RUN_ID}\n\n{analysis_tag}"')
        
        pat_token = os.getenv('HEALER_PAT')
        push_token = pat_token if (pat_token and pat_token.startswith('ghp_')) else GITHUB_TOKEN

        os.system('git config --local --unset-all http.https://github.com/.extraheader')
        remote_url = f"https://x-access-token:{push_token}@github.com/{REPO}.git"
        
        # Pushing to the same branch (will trigger a NEW run if HEALER_PAT is used)
        push_res = os.system(f'git push --set-upstream {remote_url} {fix_branch}')
        if push_res == 0:
            print(f"Fix updated on {fix_branch}. Verification run triggered.", flush=True)
        
    except Exception as e:
        print(f"Error in healing: {e}", flush=True)

if __name__ == "__main__":
    heal()
