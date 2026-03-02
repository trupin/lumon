"""Claude Code pre-tool-use hook: enforce sandbox boundaries for all tools."""

import json
import logging
import os
import re
import shlex
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_HOOK_DIR, "sandbox-guard.log")
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


_CHAIN_OPERATORS = ("&&", "||", ";", "$(", "`")
_REDIRECT_OPERATORS = (">", ">>", "<")
_SAFE_PIPE_TARGETS = ("head", "tail", "grep", "wc", "cat", "sort", "uniq", "tr", "cut", "less", "more")


def _strip_quoted(command: str) -> str:
    """Remove single-quoted and double-quoted strings so we only inspect shell structure."""
    result = re.sub(r"'[^']*'", "", command)
    result = re.sub(r'"(?:[^"\\]|\\.)*"', "", result)
    return result


def _split_on_pipes(command: str) -> list[str]:
    """Split command on unquoted pipe operators, preserving quoted content."""
    unquoted = _strip_quoted(command)
    # Find pipe positions in the unquoted version, but split the original
    # We need to map positions back, so instead rebuild by tracking quote state
    segments: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(command):
        ch = command[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
        elif ch == "\\" and in_double and i + 1 < len(command):
            current.append(ch + command[i + 1])
            i += 1
        elif ch == "|" and not in_single and not in_double:
            # Make sure it's not || (logical OR)
            if i + 1 < len(command) and command[i + 1] == "|":
                current.append("||")
                i += 1
            else:
                segments.append("".join(current))
                current = []
        else:
            current.append(ch)
        i += 1
    segments.append("".join(current))
    return segments


def _is_lumon_command(command: str) -> bool:
    """Check if command is a valid lumon invocation (spec/version or --working-dir sandbox)."""
    if not command.startswith("lumon"):
        return False

    try:
        parts = shlex.split(command)
    except ValueError:
        return False

    if not parts or parts[0] != "lumon":
        return False

    # Allow lumon spec / lumon version without --working-dir
    if len(parts) >= 2 and parts[1] in ("spec", "version"):
        return True

    # Must contain --working-dir sandbox
    for i, part in enumerate(parts):
        if part == "--working-dir" and i + 1 < len(parts):
            wd = parts[i + 1].rstrip("/")
            if wd in ("sandbox", "./sandbox"):
                return True
        if part.startswith("--working-dir="):
            wd = part.split("=", 1)[1].rstrip("/")
            if wd in ("sandbox", "./sandbox"):
                return True

    return False


def _is_safe_pipe_segment(segment: str) -> bool:
    """Check if a pipe segment is a safe read-only command."""
    segment = segment.strip()
    try:
        parts = shlex.split(segment)
    except ValueError:
        return False
    if not parts:
        return False
    return parts[0] in _SAFE_PIPE_TARGETS


def _is_allowed(command: str) -> bool:
    """Check if command is a single allowed lumon invocation, optionally piped to safe commands."""
    unquoted = _strip_quoted(command)
    # Strip safe fd redirects (e.g. 2>&1) before checking for redirect operators
    unquoted_clean = re.sub(r"\d*>&\d+", "", unquoted)

    # Reject chaining operators and redirects
    for op in _CHAIN_OPERATORS:
        if op in unquoted_clean:
            return False
    for op in _REDIRECT_OPERATORS:
        if op in unquoted_clean:
            return False

    # Split on pipes and validate each segment
    segments = _split_on_pipes(command)
    if not segments:
        return False

    # First segment must be a valid lumon command
    first = segments[0].strip()
    if not _is_lumon_command(first):
        return False

    # Remaining segments (if any) must be safe read-only commands
    for seg in segments[1:]:
        if not _is_safe_pipe_segment(seg):
            return False

    return True


def _is_within(path: str, allowed_dir: str) -> bool:
    """Check if path is within allowed_dir (no traversal escape)."""
    resolved = os.path.realpath(os.path.join(os.getcwd(), path))
    allowed = os.path.realpath(os.path.join(os.getcwd(), allowed_dir))
    return resolved == allowed or resolved.startswith(allowed + os.sep)


def _block(reason: str) -> None:
    logging.warning("BLOCKED: %s", reason)
    print(f"BLOCKED: {reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool == "Bash":
        command = tool_input.get("command", "").strip()
        if not command:
            return
        if _is_allowed(command):
            logging.info("ALLOWED Bash: %s", command)
            return
        _block(f"Only `lumon --working-dir sandbox` commands are allowed.\n  Attempted: {command}")

    elif tool == "Edit":
        file_path = tool_input.get("file_path", "")
        if _is_within(file_path, "sandbox"):
            logging.info("ALLOWED Edit: %s", file_path)
            return
        _block(f"Edit only allowed in sandbox/ directory.\n  Attempted: {file_path}")

    elif tool == "Read":
        file_path = tool_input.get("file_path", "")
        if _is_within(file_path, "."):
            logging.info("ALLOWED Read: %s", file_path)
            return
        _block(f"Read only allowed in current directory.\n  Attempted: {file_path}")


if __name__ == "__main__":
    main()
