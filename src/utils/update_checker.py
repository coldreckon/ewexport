"""
Update checker for EasyWorship to ProPresenter Converter
Checks GitHub for new releases and notifies the user
"""

import json
import logging
import urllib.request
import urllib.error
import webbrowser
from typing import Optional, Dict, Any
from packaging import version
import threading
from src.version import __version__

logger = logging.getLogger(__name__)

class UpdateChecker:
    """Handles checking for application updates from GitHub"""

    GITHUB_API_URL = "https://api.github.com/repos/coldreckon/ewexport/releases/latest"
    GITHUB_RELEASES_URL = "https://github.com/coldreckon/ewexport/releases"
    CURRENT_VERSION = __version__  # Imported from centralized version module
    
    def __init__(self, config=None):
        """Initialize the update checker
        
        Args:
            config: Configuration manager instance for storing preferences
        """
        self.config = config
        self.latest_version_info = None
        
    def get_current_version(self) -> str:
        """Get the current application version
        
        Returns:
            Current version string
        """
        # In future, this could read from a version file or package metadata
        return self.CURRENT_VERSION
    
    def fetch_latest_release(self) -> Optional[Dict[str, Any]]:
        """Fetch the latest release information from GitHub
        
        Returns:
            Dictionary with release information or None if failed
        """
        try:
            # Create request with proper headers
            req = urllib.request.Request(
                self.GITHUB_API_URL,
                headers={
                    'User-Agent': 'EWExport-UpdateChecker',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            
            # Fetch data from GitHub
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            # Extract relevant information
            release_info = {
                'version': data.get('tag_name', '').lstrip('v'),
                'name': data.get('name', ''),
                'body': data.get('body', ''),
                'html_url': data.get('html_url', ''),
                'published_at': data.get('published_at', ''),
                'prerelease': data.get('prerelease', False),
                'assets': []
            }
            
            # Get download links for assets
            for asset in data.get('assets', []):
                release_info['assets'].append({
                    'name': asset.get('name', ''),
                    'download_url': asset.get('browser_download_url', ''),
                    'size': asset.get('size', 0)
                })
            
            self.latest_version_info = release_info
            logger.info(f"Fetched latest release: v{release_info['version']}")
            return release_info
            
        except urllib.error.URLError as e:
            logger.error(f"Network error checking for updates: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GitHub API response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error checking for updates: {e}")
            return None
    
    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """Check if a newer version is available
        
        Returns:
            Update information if available, None otherwise
        """
        latest_release = self.fetch_latest_release()
        if not latest_release:
            return None
        
        try:
            current_ver = version.parse(self.get_current_version())
            latest_ver = version.parse(latest_release['version'])
            
            if latest_ver > current_ver:
                logger.info(f"Update available: v{latest_release['version']} (current: v{self.get_current_version()})")
                return {
                    'available': True,
                    'current_version': self.get_current_version(),
                    'latest_version': latest_release['version'],
                    'release_info': latest_release
                }
            else:
                logger.info("Application is up to date")
                return {
                    'available': False,
                    'current_version': self.get_current_version(),
                    'latest_version': latest_release['version']
                }
                
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return None
    
    def check_for_updates_async(self, callback):
        """Check for updates in a background thread
        
        Args:
            callback: Function to call with the update information
        """
        def check_thread():
            result = self.check_for_updates()
            callback(result)
        
        thread = threading.Thread(target=check_thread, daemon=True)
        thread.start()
    
    def open_download_page(self):
        """Open the GitHub releases page in the default browser"""
        webbrowser.open(self.GITHUB_RELEASES_URL)
    
    def open_specific_release(self, release_url: str):
        """Open a specific release page in the default browser

        Args:
            release_url: URL to the specific release
        """
        # Only allow https:// URLs. The release URL comes from the GitHub API
        # response, so a compromised release could otherwise supply javascript:,
        # file://, or an OS-registered scheme handler.
        if not isinstance(release_url, str) or not release_url.startswith('https://'):
            logger.warning(f"Refusing to open non-https release URL: {release_url!r}")
            webbrowser.open(self.GITHUB_RELEASES_URL)
            return
        webbrowser.open(release_url)
    
    def should_check_on_startup(self) -> bool:
        """Check if automatic update checking is enabled
        
        Returns:
            True if automatic checking is enabled
        """
        if self.config:
            # Use get method with proper path notation
            value = self.config.get('updates.check_on_startup', True)
            # Convert to bool if it's a string
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        return True
    
    def set_check_on_startup(self, enabled: bool):
        """Set whether to check for updates on startup
        
        Args:
            enabled: True to enable automatic checking
        """
        if self.config:
            self.config.set('updates.check_on_startup', enabled)
            self.config.save_settings()
    
    def format_update_message(self, update_info: Dict[str, Any]) -> str:
        """Format an update notification message
        
        Args:
            update_info: Update information dictionary
            
        Returns:
            Formatted message string
        """
        if not update_info:
            return "Could not check for updates. Please check your internet connection."
        
        if not update_info.get('available'):
            return f"You are running the latest version (v{update_info['current_version']})."
        
        release = update_info.get('release_info', {})
        message = f"A new version is available!\n\n"
        message += f"Current version: v{update_info['current_version']}\n"
        message += f"Latest version: v{update_info['latest_version']}\n\n"
        
        if release.get('name'):
            message += f"Release: {release['name']}\n\n"
        
        # Add truncated release notes if available
        if release.get('body'):
            notes = release['body']
            max_length = 500
            if len(notes) > max_length:
                notes = notes[:max_length] + "..."
            message += f"Release Notes:\n{notes}\n\n"
        
        message += "Would you like to download the update now?"
        
        return message