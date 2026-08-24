#!/usr/bin/env python3
"""Run all unit, dsp, parser, web, and integration tests across the Parlando package."""

import os
import sys
import unittest

def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, repo_root)

    print("======================================================================")
    print("PARLANDO // UNIT, DSP, PARSER, WEB & PIPELINE TEST SUITE")
    print("======================================================================")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=os.path.join(repo_root, "parlando"), pattern="*_test.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        print(f"\n❌ FAILED: {len(result.failures)} failures, {len(result.errors)} errors.")
        return 1

    print(f"\n✔ ALL {result.testsRun} TESTS PASSED CLEANLY.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
