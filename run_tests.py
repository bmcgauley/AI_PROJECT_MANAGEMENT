#!/usr/bin/env python
"""
Test runner script for the AI Project Management System.
"""

import os
import sys
import pytest


def main():
    """
    Run all tests for the AI Project Management System.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    print("Running tests for the AI Project Management System...")
    
    # Add the project root to the Python path to fix import issues
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # Run pytest with specific arguments
    args = [
        "-v",  # Verbose output
        "--no-header",  # No pytest header
        "tests"  # Test directory
    ]
    
    # Add additional arguments from command line
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    
    # Run pytest and return exit code
    return pytest.main(args)


if __name__ == "__main__":
    sys.exit(main()) 