#!/usr/bin/env python3
"""Executable launcher for the Audiobook Narrator synthesis deck."""

import os
import sys

# Ensure package directory is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

for p in [current_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from audiobook_narrator.cli import main
except ImportError:
    try:
        from cli import main
    except ImportError:
        from experimental.users.plbogen.audiobook_narrator.cli import main

if __name__ == "__main__":
    main()
