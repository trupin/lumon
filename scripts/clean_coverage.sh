#!/usr/bin/env bash
# Remove stale coverage data files
rm -f .coverage
find . -maxdepth 1 -name '.coverage.*' -delete 2>/dev/null || true
