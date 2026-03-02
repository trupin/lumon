"""Claude Code pre-tool-use hook: only allow lumon commands with --working-dir sandbox."""

import json
import logging
import os
import shlex
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_HOOK_DIR, "sandbox-guard.log")
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


_SHELL_OPERATORS = ("&&", "||", ";", "|", ">", ">>", "<", "$(", "`")


def _is_allowed(command: str) -> bool:
    """Check if command is a single allowed lumon invocation."""
    # Reject command chaining / shell operators
    for op in _SHELL_OPERATORS:
        if op in command:
            return False

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


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")

    if tool != "Bash":
        return

    command = data.get("tool_input", {}).get("command", "").strip()

    if not command:
        return

    if _is_allowed(command):
        logging.info("ALLOWED: %s", command)
        return

    logging.warning("BLOCKED: %s", command)
    print(
        f"BLOCKED: Only `lumon --working-dir sandbox` commands are allowed.\n"
        f"  Attempted: {command}",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
