"""WSGI entry point for PythonAnywhere."""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Set FLASK_SECRET_KEY in PythonAnywhere's Web tab; do not hard-code it here.
from app import app as application
