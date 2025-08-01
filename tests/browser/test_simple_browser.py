#!/usr/bin/env python3
"""
Simple browser test to verify server connectivity.
"""

import os
import sys
import time
import unittest
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
import django
django.setup()

from django.test import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


class SimpleBrowserTest(LiveServerTestCase):
    """Simple browser test to verify server is working."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        
        # Check if Chrome is available
        import shutil
        import os
        
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chrome",
            "/opt/google/chrome/google-chrome",
            shutil.which("chrome"),
            shutil.which("google-chrome"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
        ]
        
        chrome_binary = None
        for path in chrome_paths:
            if path and os.path.exists(path):
                chrome_binary = path
                break
        
        if not chrome_binary:
            print("Chrome not found. Skipping browser tests.")
            cls.skip_tests = True
            cls.driver = None
            return
        
        cls.skip_tests = False
        
        # Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.binary_location = chrome_binary
        
        try:
            # Get the correct ChromeDriver path
            driver_path = ChromeDriverManager().install()
            
            # Fix the path if it's pointing to the wrong file
            if 'THIRD_PARTY_NOTICES' in driver_path:
                driver_dir = os.path.dirname(driver_path)
                driver_path = os.path.join(driver_dir, 'chromedriver')
            
            service = Service(driver_path)
            cls.driver = webdriver.Chrome(service=service, options=chrome_options)
            cls.driver.implicitly_wait(10)
        except Exception as e:
            print(f"Failed to create Chrome driver: {e}")
            cls.skip_tests = True
            cls.driver = None
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test class."""
        if hasattr(cls, 'driver') and cls.driver:
            cls.driver.quit()
        super().tearDownClass()
    
    def test_server_responds(self):
        """Test that the test server responds."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        print(f"Test server URL: {self.live_server_url}")
        
        # Navigate to the home page
        self.driver.get(self.live_server_url)
        
        # Wait a moment for page to load
        time.sleep(2)
        
        # Get page title and source
        print(f"Page title: {self.driver.title}")
        print(f"Page URL: {self.driver.current_url}")
        
        # Check if we get any content
        page_source = self.driver.page_source
        print(f"Page source length: {len(page_source)}")
        
        # Print first 500 characters of page source for debugging
        print("Page source preview:")
        print(page_source[:500])
        
        # Basic assertion - we should get some HTML content
        self.assertIn('html', page_source.lower())
    
    def test_navigate_to_login(self):
        """Test navigating to login page."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        # Navigate to login page
        login_url = f"{self.live_server_url}/login"
        print(f"Navigating to: {login_url}")
        
        self.driver.get(login_url)
        time.sleep(2)
        
        print(f"Login page title: {self.driver.title}")
        print(f"Login page URL: {self.driver.current_url}")
        
        # Check page source
        page_source = self.driver.page_source
        print(f"Login page source length: {len(page_source)}")
        print("Login page source preview:")
        print(page_source[:1000])


if __name__ == '__main__':
    unittest.main()