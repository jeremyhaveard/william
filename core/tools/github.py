"""GitHub API tools for Norm — PRs, issues, code search, repo browsing."""
import os
import base64
import requests
from langchain_core.tools import tool

_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
_BASE = "https://api.github.com"


def _headers():
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if _GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {_GITHUB_TOKEN}"
    return h


def _get(path, params=None):
    r = requests.get(f"{_BASE}{path}", headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path, json):
    r = requests.post(f"{_BASE}{path}", headers=_headers(), json=json, timeout=15)
    r.raise_for_status()
    return r.json()


@tool
def github_search_code(query: str, repo: str = None) -> str:
    """
    Search code on GitHub.

    Args:
        query: Search query (e.g. 'def get_llm language:python')
        repo: Optional repo to scope search (e.g. 'jeremyhaveard/patrick')

    Returns matching files with snippets.
    """
    try:
        q = f"{query} repo:{repo}" if repo else query
        data = _get("/search/code", params={"q": q, "per_page": 10})
        items = data.get("items", [])
        if not items:
            return "No results found."
        out = []
        for item in items:
            out.append(f"File: {item['repository']['full_name']}/{item['path']}\nURL: {item['html_url']}")
        return "\n\n".join(out)
    except Exception as e:
        return f"Error: {e}"


@tool
def github_get_file(repo: str, path: str, branch: str = "main") -> str:
    """
    Read a file from a GitHub repository.

    Args:
        repo: Repository (e.g. 'jeremyhaveard/patrick')
        path: File path in the repo (e.g. 'core/llm.py')
        branch: Branch name (default: main)
    """
    try:
        data = _get(f"/repos/{repo}/contents/{path}", params={"ref": branch})
        content = base64.b64decode(data["content"]).decode("utf-8")
        return f"# {repo}/{path} @ {branch}\n\n{content}"
    except Exception as e:
        return f"Error: {e}"


@tool
def github_list_prs(repo: str, state: str = "open") -> str:
    """
    List pull requests for a repository.

    Args:
        repo: Repository (e.g. 'jeremyhaveard/patrick')
        state: 'open', 'closed', or 'all'
    """
    try:
        prs = _get(f"/repos/{repo}/pulls", params={"state": state, "per_page": 20})
        if not prs:
            return f"No {state} PRs found."
        out = []
        for pr in prs:
            out.append(f"#{pr['number']} [{pr['state']}] {pr['title']}\n  Branch: {pr['head']['ref']} → {pr['base']['ref']}\n  URL: {pr['html_url']}")
        return "\n\n".join(out)
    except Exception as e:
        return f"Error: {e}"


@tool
def github_create_pr(repo: str, title: str, body: str, head: str, base: str = "main") -> str:
    """
    Create a pull request.

    Args:
        repo: Repository (e.g. 'jeremyhaveard/patrick')
        title: PR title
        body: PR description (markdown supported)
        head: Source branch name
        base: Target branch (default: main)
    """
    try:
        pr = _post(f"/repos/{repo}/pulls", {
            "title": title, "body": body, "head": head, "base": base
        })
        return f"PR created: #{pr['number']} {pr['title']}\nURL: {pr['html_url']}"
    except Exception as e:
        return f"Error: {e}"


@tool
def github_get_pr(repo: str, pr_number: int) -> str:
    """
    Get details and diff for a pull request.

    Args:
        repo: Repository (e.g. 'jeremyhaveard/patrick')
        pr_number: PR number
    """
    try:
        pr = _get(f"/repos/{repo}/pulls/{pr_number}")
        files = _get(f"/repos/{repo}/pulls/{pr_number}/files")
        out = [
            f"PR #{pr['number']}: {pr['title']}",
            f"State: {pr['state']}",
            f"Branch: {pr['head']['ref']} → {pr['base']['ref']}",
            f"Author: {pr['user']['login']}",
            f"Body:\n{pr.get('body', '')}",
            f"\nFiles changed ({len(files)}):",
        ]
        for f in files:
            out.append(f"  {f['status']:8} {f['filename']}  (+{f['additions']} -{f['deletions']})")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"


@tool
def github_create_issue(repo: str, title: str, body: str, labels: str = "") -> str:
    """
    Create a GitHub issue.

    Args:
        repo: Repository (e.g. 'jeremyhaveard/patrick')
        title: Issue title
        body: Issue description
        labels: Comma-separated labels (e.g. 'bug,priority:high')
    """
    try:
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = [l.strip() for l in labels.split(",")]
        issue = _post(f"/repos/{repo}/issues", payload)
        return f"Issue created: #{issue['number']} {issue['title']}\nURL: {issue['html_url']}"
    except Exception as e:
        return f"Error: {e}"


@tool
def github_list_issues(repo: str, state: str = "open", labels: str = "") -> str:
    """
    List issues for a repository.

    Args:
        repo: Repository (e.g. 'jeremyhaveard/patrick')
        state: 'open', 'closed', or 'all'
        labels: Filter by comma-separated labels (optional)
    """
    try:
        params = {"state": state, "per_page": 20}
        if labels:
            params["labels"] = labels
        issues = _get(f"/repos/{repo}/issues", params=params)
        issues = [i for i in issues if "pull_request" not in i]  # exclude PRs
        if not issues:
            return f"No {state} issues found."
        out = []
        for i in issues:
            label_str = ", ".join(l["name"] for l in i.get("labels", []))
            out.append(f"#{i['number']} {i['title']}{' [' + label_str + ']' if label_str else ''}\n  URL: {i['html_url']}")
        return "\n\n".join(out)
    except Exception as e:
        return f"Error: {e}"
