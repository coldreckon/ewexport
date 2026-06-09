#!/usr/bin/env python3
"""
EasyWorship to ProPresenter Converter
Main entry point
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from src.utils.config import get_app_data_dir
from src.utils.section_mappings import ensure_mappings_file


def initialize_application():
    """Initialize application directories and configuration"""
    # Determine if running as frozen executable or script
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        application_path = os.path.dirname(sys.executable)
    else:
        # Running as script
        application_path = os.path.dirname(os.path.abspath(__file__))

    # Get app data directory using centralized cross-platform function
    app_data_dir = get_app_data_dir()

    # Create logs directory
    logs_dir = app_data_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)

    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / 'ewexport.log'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Application initialized. Running from: {application_path}")
    logger.info(f"Configuration directory: {app_data_dir}")

    # Ensure default section mappings exist in app data directory
    ensure_mappings_file()

from src.gui.main_window import MainWindow

def main():
    # Initialize application environment
    initialize_application()
    
    # Start the GUI
    app = MainWindow()
    app.run()

if __name__ == "__main__":
    main()