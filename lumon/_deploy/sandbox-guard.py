"""Claude Code pre-tool-use hook: only allow lumon commands with --working-dir sandbox."""

import json
import sys

ALLOWED_PREFIXES = [
    "lumon --working-dir sandbox ",
    "lumon --working-dir sandbox\n",
    "lumon --working-dir ./sandbox ",
    "lumon --working-dir ./sandbox\n",
    "lumon spec",
    "lumon version",
]


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")

    if tool != "Bash":
        return

    command = data.get("tool_input", {}).get("command", "").strip()

    if not command:
        return

    for prefix in ALLOWED_PREFIXES:
        if command.startswith(prefix) or command == prefix.strip():
            return

    print(
        f"BLOCKED: Only `lumon --working-dir sandbox` commands are allowed.\n"
        f"  Attempted: {command}",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
