"""Shared shell/subprocess tools available to any agent or app."""
import os
import sys
import subprocess
from langchain_core.tools import tool


@tool
def run_python(code: str) -> str:
    """Execute Python code and return stdout/stderr. 30-second timeout."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = ""
        if result.stdout:
            out += f"stdout:\n{result.stdout}"
        if result.stderr:
            out += f"\nstderr:\n{result.stderr}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: execution timed out (30s)"
    except Exception as e:
        return f"Error: {e}"


@tool
def shell_exec(command: str, cwd: str = None, timeout: int = 120) -> str:
    """
    Execute a shell command and return stdout + stderr.

    Use this for git operations, running tests, installing packages,
    compiling code, running linters, or any system command.

    Args:
        command: The shell command to run (e.g. 'git status', 'npm test', 'pytest')
        cwd: Working directory to run the command in (optional)
        timeout: Max seconds to wait (default 120)

    Returns stdout and stderr combined with exit code.
    """
    try:
        work_dir = cwd or os.getcwd()
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )
        out = ""
        if result.stdout:
            out += result.stdout
        if result.stderr:
            out += result.stderr
        if result.returncode != 0:
            out += f"\n[exit code {result.returncode}]"
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"
