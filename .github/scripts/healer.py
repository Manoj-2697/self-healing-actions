import os
import sys
import requests
import json
import time
import google.generativeai as genai
import re
import subprocess

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GITHUB_TOKEN   = os.getenv('GITHUB_TOKEN')
REPO           = os.getenv('GITHUB_REPOSITORY')
RUN_ID         = os.getenv('FAILED_RUN_ID') or os.getenv('GITHUB_RUN_ID')
RETRY_BRANCH   = os.getenv('GITHUB_REF_NAME')

# Mode flags passed from the workflow
PYTHON_FAILED    = os.getenv('PYTHON_FAILED', 'false').lower() == 'true'
TERRAFORM_FAILED = os.getenv('TERRAFORM_FAILED', 'false').lower() == 'true'

if not GEMINI_API_KEY:
    print("Error: No GEMINI_API_KEY provided.", flush=True)
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

# ─────────────────────────────────────────────
# SHARED: Fetch failed job logs from GitHub API
# ─────────────────────────────────────────────
def get_failed_logs():
    print(f"Fetching logs for run {RUN_ID}...", flush=True)
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    jobs_url = f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}/jobs"
    response = requests.get(jobs_url, headers=headers)
    jobs = response.json().get('jobs', [])

    error_context = ""
    for job in jobs:
        if job['conclusion'] == 'failure':
            log_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job['id']}/logs"
            full_logs = requests.get(log_url, headers=headers).text

            tracebacks    = re.findall(r'Traceback \(most recent call last\):.*?(?:\r?\n.*?)+?(?=\r?\n\r?\n|\Z)', full_logs, re.DOTALL)
            assertions    = re.findall(r'(_+ [^_]+ _+|E   .*|AssertionError:.*)', full_logs)
            generic_errors = re.findall(r'(\w+Error:.*|\w+Exception:.*)', full_logs)
            tf_errors     = re.findall(r'(│ Error:.*?(?:\r?\n.*?)+?(?=\r?\n\r?\n|╵))', full_logs, re.DOTALL)

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


# ─────────────────────────────────────────────
# MODE A: Python fix — collect only .py files
# ─────────────────────────────────────────────
def get_python_codebase(logs):
    print(f"Identifying Python files to fix (Branch: {RETRY_BRANCH})...", flush=True)
    potential_files = set()

    # From log tracebacks
    for f in re.findall(r'([a-zA-Z0-9_\-/]+\.py)', logs):
        potential_files.add(f)

    # From git diff
    try:
        remotes = subprocess.check_output(['git', 'remote', 'show', 'origin'], text=True)
        default_branch = "main" if "HEAD branch: main" in remotes else "master"
        cmd = ['git', 'diff', 'HEAD~1...HEAD', '--name-only'] if RETRY_BRANCH == default_branch \
              else ['git', 'diff', f'origin/{default_branch}...HEAD', '--name-only']
        for f in subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).splitlines():
            potential_files.add(f)
    except:
        try:
            for f in subprocess.check_output(['git', 'show', '--name-only', '--format=', 'HEAD'], text=True).splitlines():
                potential_files.add(f)
        except: pass

    py_files = []
    for f in potential_files:
        rel = os.path.relpath(os.path.normpath(f), os.getcwd())
        if os.path.isfile(rel) and rel.endswith('.py') and not rel.startswith('.github'):
            py_files.append(rel)

    py_files = sorted(set(py_files))
    print(f"Sharing {len(py_files)} Python files with Gemini: {', '.join(py_files)}", flush=True)

    return {f: open(f, 'r', encoding='utf-8').read() for f in py_files if os.path.isfile(f)}


# ─────────────────────────────────────────────
# MODE A: Apply fix and push branch
# ─────────────────────────────────────────────
def heal_python(logs):
    print("\n=== MODE: Python Fix ===", flush=True)
    codebase = get_python_codebase(logs)
    if not codebase:
        print("No Python files identified. Skipping.", flush=True)
        return

    prompt = (
        f"Failure errors:\n{logs}\n\n"
        f"Python code context:\n{json.dumps(codebase, indent=2)}\n\n"
        f"Suggest a fix. Return JSON only: "
        f"{{'analysis': '...', 'fixes': [{{'filename': '...', 'content': '...'}}]}}"
    )

    print("Asking Gemini for a Python fix...", flush=True)
    response = model.generate_content(prompt)

    try:
        raw = response.text.strip()
        if raw.startswith("```json"): raw = raw[7:].strip()
        if raw.endswith("```"):       raw = raw[:-3].strip()

        fix_data = json.loads(raw)
        analysis = fix_data.get('analysis', 'No analysis')
        print(f"\n--- AI ANALYSIS ---\n{analysis}\n------------------\n", flush=True)

        fixes = fix_data.get('fixes', [])
        if not fixes:
            print("No fixes suggested.", flush=True)
            return

        for fix in fixes:
            print(f"Applying fix to {fix['filename']}...", flush=True)
            with open(fix['filename'], 'w', encoding='utf-8') as fh:
                fh.write(fix['content'])

        print("--- CHANGES APPLIED (DIFF) ---", flush=True)
        os.system('git diff')
        print("------------------------------", flush=True)

        # Branch logic
        if RETRY_BRANCH.startswith("gemini-fix-"):
            fix_branch = RETRY_BRANCH
            print(f"Continuing on existing fix branch: {fix_branch}", flush=True)
        else:
            fix_branch = f"gemini-fix-{int(time.time())}"
            print(f"Creating new fix branch: {fix_branch}", flush=True)
            os.system(f'git checkout -b {fix_branch}')

        os.system('git config user.name "Gemini Healer"')
        os.system('git config user.email "healer@gemini.ai"')
        os.system('git add .')

        orig_branch = RETRY_BRANCH if not RETRY_BRANCH.startswith("gemini-fix-") else "master"
        tag = f"[ANALYSIS]: {analysis}\n[ORIGINAL_BRANCH]: {orig_branch}"
        os.system(f'git commit -m "Auto-fix cycle for run #{RUN_ID}\n\n{tag}"')

        pat_token  = os.getenv('HEALER_PAT')
        push_token = pat_token if (pat_token and pat_token.startswith('ghp_')) else GITHUB_TOKEN
        os.system('git config --local --unset-all http.https://github.com/.extraheader')
        remote_url = f"https://x-access-token:{push_token}@github.com/{REPO}.git"

        if os.system(f'git push --set-upstream {remote_url} {fix_branch}') == 0:
            print(f"Fix pushed to {fix_branch}. Verification run triggered.", flush=True)

    except Exception as e:
        print(f"Error during Python healing: {e}", flush=True)


# ─────────────────────────────────────────────
# MODE B: Terraform analysis only — no file changes
# ─────────────────────────────────────────────
def get_terraform_codebase():
    tf_files = {}
    terraform_dir = os.path.join(os.getcwd(), 'terraform')
    if os.path.isdir(terraform_dir):
        for fname in os.listdir(terraform_dir):
            if fname.endswith('.tf'):
                fpath = os.path.join(terraform_dir, fname)
                try:
                    tf_files[f"terraform/{fname}"] = open(fpath, 'r', encoding='utf-8').read()
                except: pass
    print(f"Sharing {len(tf_files)} Terraform files with Gemini: {', '.join(tf_files.keys())}", flush=True)
    return tf_files


def analyze_terraform(logs):
    print("\n=== MODE: Terraform Analysis (Read-Only) ===", flush=True)
    tf_codebase = get_terraform_codebase()

    prompt = (
        f"The Terraform deployment failed with the following errors:\n{logs}\n\n"
        f"Terraform configuration:\n{json.dumps(tf_codebase, indent=2)}\n\n"
        f"IMPORTANT: Do NOT suggest code changes. Instead:\n"
        f"1. Explain clearly WHY the deployment failed.\n"
        f"2. List the specific manual steps a developer must take to fix it.\n"
        f"Return plain text explanation only, no JSON."
    )

    print("Asking Gemini to analyze the Terraform failure...", flush=True)
    response = model.generate_content(prompt)

    print("\n" + "=" * 60, flush=True)
    print("       TERRAFORM FAILURE ANALYSIS (AI Report)       ", flush=True)
    print("=" * 60, flush=True)
    print(response.text.strip(), flush=True)
    print("=" * 60, flush=True)
    print("NOTE: No code changes were made. Manual intervention required.", flush=True)


# ─────────────────────────────────────────────
# Entry point — route to correct mode
# ─────────────────────────────────────────────
def heal():
    logs = get_failed_logs()
    if not logs:
        print("No failure logs found.", flush=True)
        return

    if PYTHON_FAILED:
        heal_python(logs)

    if TERRAFORM_FAILED:
        analyze_terraform(logs)

    if not PYTHON_FAILED and not TERRAFORM_FAILED:
        print("\n=== UNKNOWN FAILURE: Manual Review Required ===", flush=True)
        print("Neither PYTHON_FAILED nor TERRAFORM_FAILED was set.", flush=True)
        print("AI will not attempt any fixes.\n", flush=True)

        # Best effort: identify files mentioned in the logs
        affected_files = sorted(set(
            f for f in re.findall(r'([a-zA-Z0-9_\-/]+\.\w+)', logs)
            if not f.startswith('.github') and ('/' in f or '.' in f)
            and any(f.endswith(ext) for ext in ['.py', '.tf', '.yml', '.yaml', '.json', '.sh'])
        ))

        if affected_files:
            print("Files referenced in the failure logs (manual fix needed):", flush=True)
            for f in affected_files:
                print(f"  - {f}", flush=True)
        else:
            print("No specific files could be identified from the logs.", flush=True)

        print("\nPlease review the failed job logs and fix manually.", flush=True)


if __name__ == "__main__":
    heal()
