"""Tests for lumon.source_utils — block extraction and persistence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lumon.source_utils import extract_blocks, save_blocks


class TestExtractBlocks:
    def test_single_define(self) -> None:
        source = 'define inbox.read\n  "Read messages"\n  returns: list<text>'
        blocks = extract_blocks(source)
        assert len(blocks) == 1
        assert blocks[0][0] == "define"
        assert blocks[0][1] == "inbox.read"

    def test_single_implement(self) -> None:
        source = "implement inbox.read\n  return []"
        blocks = extract_blocks(source)
        assert len(blocks) == 1
        assert blocks[0][0] == "implement"
        assert blocks[0][1] == "inbox.read"

    def test_multiple_blocks(self) -> None:
        source = (
            'define inbox.read\n  "Read messages"\n  returns: list<text>\n\n'
            "implement inbox.read\n  return []\n"
        )
        blocks = extract_blocks(source)
        assert len(blocks) == 2
        assert blocks[0][0] == "define"
        assert blocks[1][0] == "implement"

    def test_empty_source(self) -> None:
        assert extract_blocks("") == []

    def test_no_blocks(self) -> None:
        assert extract_blocks("let x = 42\nreturn x") == []

    def test_block_with_empty_lines(self) -> None:
        source = "define inbox.read\n  returns: text\n\n  takes: none"
        blocks = extract_blocks(source)
        assert len(blocks) == 1

    def test_trailing_empty_lines_stripped(self) -> None:
        source = "define inbox.read\n  returns: text\n\n"
        blocks = extract_blocks(source)
        assert len(blocks) == 1
        assert not blocks[0][2].endswith("\n")

    def test_tab_indented_block(self) -> None:
        source = "define inbox.read\n\treturns: text"
        blocks = extract_blocks(source)
        assert len(blocks) == 1


class TestSaveBlocks:
    def test_creates_manifest_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        blocks = [("define", "inbox.read", 'define inbox.read\n  "Read messages"')]
        save_blocks(str(tmp_path), blocks)
        manifest = os.path.join(str(tmp_path), "lumon", "manifests", "inbox.lumon")
        assert os.path.isfile(manifest)
        content = Path(manifest).read_text(encoding="utf-8")
        assert "inbox.read" in content

    def test_creates_impl_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        blocks = [("implement", "inbox.read", "implement inbox.read\n  return []")]
        save_blocks(str(tmp_path), blocks)
        impl = os.path.join(str(tmp_path), "lumon", "impl", "inbox.lumon")
        assert os.path.isfile(impl)

    def test_skips_builtin_namespaces(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        blocks = [("define", "text.upper", "define text.upper\n  returns: text")]
        save_blocks(str(tmp_path), blocks)
        manifest = os.path.join(str(tmp_path), "lumon", "manifests", "text.lumon")
        assert not os.path.exists(manifest)

    def test_replaces_existing_block(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        blocks1 = [("define", "inbox.read", 'define inbox.read\n  "Old"')]
        save_blocks(str(tmp_path), blocks1)
        blocks2 = [("define", "inbox.read", 'define inbox.read\n  "New"')]
        save_blocks(str(tmp_path), blocks2)
        manifest = os.path.join(str(tmp_path), "lumon", "manifests", "inbox.lumon")
        content = Path(manifest).read_text(encoding="utf-8")
        assert "New" in content
        assert "Old" not in content

    def test_appends_new_block(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        blocks1 = [("define", "inbox.read", 'define inbox.read\n  "Read"')]
        save_blocks(str(tmp_path), blocks1)
        blocks2 = [("define", "inbox.write", 'define inbox.write\n  "Write"')]
        save_blocks(str(tmp_path), blocks2)
        manifest = os.path.join(str(tmp_path), "lumon", "manifests", "inbox.lumon")
        content = Path(manifest).read_text(encoding="utf-8")
        assert "inbox.read" in content
        assert "inbox.write" in content
