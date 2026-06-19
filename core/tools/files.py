"""Shared file-system tools available to any agent or app."""
import os
from langchain_core.tools import tool
from core.storage import read_file as _read, write_file as _write, list_files


@tool
def read_file(path: str) -> str:
    """Read the contents of a file."""
    try:
        return _read(path)
    except FileNotFoundError:
        # Fall back to reading the raw path as given (absolute paths, cwd-relative)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    try:
        location = _write(path, content)
        return f"Wrote {len(content)} characters to {location}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def list_directory(path: str = "output") -> str:
    """List files in storage under the given path prefix."""
    try:
        items = list_files(path)
        if not items:
            # Fall back to local os.scandir for absolute paths or repo browsing
            import os as _os
            if _os.path.isdir(path):
                entries = []
                for entry in sorted(_os.scandir(path), key=lambda e: (not e.is_dir(), e.name)):
                    prefix = "[DIR] " if entry.is_dir() else "[FILE]"
                    entries.append(f"{prefix} {entry.name}")
                return "\n".join(entries) or "(empty)"
            return "(empty)"
        return "\n".join(f"[FILE] {p}" for p in sorted(items))
    except Exception as e:
        return f"Error: {e}"


@tool
def search_in_files(directory: str, pattern: str) -> str:
    """Search for a text pattern in source files under a directory (case-insensitive)."""
    matches = []
    try:
        exts = {".py", ".js", ".ts", ".java", ".go", ".rs", ".txt", ".md", ".json"}
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if os.path.splitext(fname)[1].lower() in exts:
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if pattern.lower() in line.lower():
                                    matches.append(f"{fpath}:{i}: {line.rstrip()}")
                                    if len(matches) >= 50:
                                        return "\n".join(matches)
                    except Exception:
                        pass
        return "\n".join(matches) or f"No matches for '{pattern}'"
    except Exception as e:
        return f"Error: {e}"
