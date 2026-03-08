"""Utilities for extracting and persisting define/implement blocks from source code."""

from __future__ import annotations

import os
import re


def extract_blocks(source: str) -> list[tuple[str, str, str]]:
    """Extract define/implement/test blocks from Lumon source code.

    Returns a list of (block_type, namespace_path, source_text) tuples.
    block_type is "define", "implement", or "test".
    """
    blocks: list[tuple[str, str, str]] = []
    lines = source.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        match = re.match(r"^(define|implement|test)\s+(\S+)", stripped)
        if match:
            block_type = match.group(1)
            ns_path = match.group(2)
            block_lines = [line]
            i += 1

            # Collect indented continuation lines
            while i < len(lines):
                next_line = lines[i]
                # Empty lines within a block are part of it
                if next_line.strip() == "":
                    # Look ahead: if the next non-empty line is indented, include it
                    lookahead = i + 1
                    while lookahead < len(lines) and lines[lookahead].strip() == "":
                        lookahead += 1
                    next_nonblank = lines[lookahead] if lookahead < len(lines) else ""
                    if next_nonblank.startswith("  ") or next_nonblank.startswith("\t"):
                        block_lines.append(next_line)
                        i += 1
                        continue
                    break
                if next_line.startswith("  ") or next_line.startswith("\t"):
                    block_lines.append(next_line)
                    i += 1
                else:
                    break

            # Strip trailing empty lines
            while block_lines and block_lines[-1].strip() == "":
                block_lines.pop()

            source_text = "\n".join(block_lines)
            blocks.append((block_type, ns_path, source_text))
        else:
            i += 1

    return blocks


def save_blocks(working_dir: str, blocks: list[tuple[str, str, str]]) -> None:
    """Save extracted blocks to the appropriate files on disk.

    - define blocks go to lumon/manifests/<namespace>.lumon
    - implement blocks go to lumon/impl/<namespace>.lumon

    Creates directories as needed. Replaces existing block for the same
    function or appends if not found.
    """
    # Builtin namespaces that should not be persisted
    builtin_ns = {"text", "list", "map", "number", "type", "time", "io"}

    for block_type, ns_path, source_text in blocks:
        namespace = ns_path.split(".")[0]
        if namespace in builtin_ns:
            continue

        if block_type == "define":
            dir_path = os.path.join(working_dir, "lumon", "manifests")
        elif block_type == "test":
            dir_path = os.path.join(working_dir, "lumon", "tests")
        else:
            dir_path = os.path.join(working_dir, "lumon", "impl")

        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{namespace}.lumon")

        if os.path.isfile(file_path):
            with open(file_path, encoding="utf-8") as f:
                existing = f.read()
            updated = _replace_or_append(existing, block_type, ns_path, source_text)
        else:
            updated = source_text + "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)


def _replace_or_append(existing: str, block_type: str, ns_path: str, new_source: str) -> str:
    """Replace an existing block for the same function, or append if not found."""
    lines = existing.split("\n")
    result_lines: list[str] = []
    i = 0
    replaced = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        match = re.match(r"^(define|implement|test)\s+(\S+)", stripped)

        if match and match.group(1) == block_type and match.group(2) == ns_path:
            # Skip the old block
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip() == "":
                    i += 1
                    continue
                if next_line.startswith("  ") or next_line.startswith("\t"):
                    i += 1
                else:
                    break
            # Insert the new block
            result_lines.append(new_source)
            replaced = True
        else:
            result_lines.append(line)
            i += 1

    if not replaced:
        # Ensure there's a blank line before appending
        if result_lines and result_lines[-1].strip() != "":
            result_lines.append("")
        result_lines.append(new_source)

    text = "\n".join(result_lines)
    if not text.endswith("\n"):
        text += "\n"
    return text
