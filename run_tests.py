"""Test runner for audiobook_narrator test suite."""

import os
import sys
import types
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Initialize package object if not present
if "audiobook_narrator" not in sys.modules:
    import importlib.util
    init_path = os.path.join(current_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location("audiobook_narrator", init_path, submodule_search_locations=[current_dir])
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["audiobook_narrator"] = mod
        spec.loader.exec_module(mod)

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(current_dir, "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
