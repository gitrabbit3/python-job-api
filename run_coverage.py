#!/usr/bin/env python
"""
Coverage runner script for Django project.
This script runs coverage with proper Django settings and generates reports.
"""

import os
import sys
import subprocess
import django
from django.conf import settings

def run_coverage():
    """Run coverage and generate reports."""

    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobapi.settings')
    django.setup()

    # Run coverage
    cmd = [
        sys.executable, '-m', 'coverage', 'run', '--source=.',
        'manage.py', 'test', '--verbosity=2'
    ]

    print("Running tests with coverage...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Tests failed:")
        print(result.stdout)
        print(result.stderr)
        return False

    print("Tests completed successfully!")
    print(result.stdout)

    # Generate reports
    print("\nGenerating coverage reports...")

        # Terminal report
    subprocess.run([sys.executable, '-m', 'coverage', 'report'], check=True)

    # HTML report
    subprocess.run([sys.executable, '-m', 'coverage', 'html'], check=True)
    print("HTML report generated in htmlcov/ directory")

    # XML report (for CI/CD)
    subprocess.run([sys.executable, '-m', 'coverage', 'xml'], check=True)
    print("XML report generated as coverage.xml")

    return True

if __name__ == '__main__':
    success = run_coverage()
    sys.exit(0 if success else 1)
