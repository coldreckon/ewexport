#!/usr/bin/env python3
"""
Launch script for EasyWorship to ProPresenter Converter
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()