#!/usr/bin/env python3
"""
Debug browser test to see what's actually on the page.
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

from django.test import TestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


class DebugBrowserTest(TestCase):
    """Debug browser test to see what's on the page."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        
        # Application URLs
        cls.react_url = "http://localhost:3000"
        
        # Chrome options - visible browser for debugging
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Commented out to see browser
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            # Get the correct ChromeDriver path
            driver_path = ChromeDriverManager().install()
            
            # Fix the path if it's pointing to the wrong file
            if 'THIRD_PARTY_NOTICES' in driver_path:
                import os
                driver_dir = os.path.dirname(driver_path)
                driver_path = os.path.join(driver_dir, 'chromedriver')
            
            service = Service(driver_path)
            cls.driver = webdriver.Chrome(service=service, options=chrome_options)
            cls.driver.implicitly_wait(10)
        except Exception as e:
            print(f"Failed to create Chrome driver: {e}")
            cls.driver = None
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test class."""
        if hasattr(cls, 'driver') and cls.driver:
            # For debugging purposes, add a small delay before closing
            time.sleep(1)
            cls.driver.quit()
        super().tearDownClass()
    
    def test_debug_react_pages(self):
        """Debug React pages to see what's actually there."""
        if not self.driver:
            self.skipTest("Chrome driver not available")
        
        # Test home page
        print("=== Testing Home Page ===")
        self.driver.get(self.react_url)
        time.sleep(3)
        
        print(f"URL: {self.driver.current_url}")
        print(f"Title: {self.driver.title}")
        
        # Print page source for debugging
        page_source = self.driver.page_source
        print(f"Page source length: {len(page_source)}")
        print("Page source:")
        print(page_source)
        
        # Test register page
        print("\n=== Testing Register Page ===")
        register_url = f"{self.react_url}/register"
        self.driver.get(register_url)
        time.sleep(3)
        
        print(f"URL: {self.driver.current_url}")
        print(f"Title: {self.driver.title}")
        
        # Look for form elements
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} input elements:")
        for i, input_elem in enumerate(inputs):
            print(f"  Input {i}: type={input_elem.get_attribute('type')}, name={input_elem.get_attribute('name')}, placeholder={input_elem.get_attribute('placeholder')}")
        
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        print(f"Found {len(buttons)} button elements:")
        for i, button in enumerate(buttons):
            print(f"  Button {i}: text='{button.text}', type={button.get_attribute('type')}")
        
        # Test login page
        print("\n=== Testing Login Page ===")
        login_url = f"{self.react_url}/login"
        self.driver.get(login_url)
        time.sleep(3)
        
        print(f"URL: {self.driver.current_url}")
        print(f"Title: {self.driver.title}")
        
        # Look for form elements
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} input elements:")
        for i, input_elem in enumerate(inputs):
            print(f"  Input {i}: type={input_elem.get_attribute('type')}, name={input_elem.get_attribute('name')}, placeholder={input_elem.get_attribute('placeholder')}")
        
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        print(f"Found {len(buttons)} button elements:")
        for i, button in enumerate(buttons):
            print(f"  Button {i}: text='{button.text}', type={button.get_attribute('type')}")


if __name__ == '__main__':
    unittest.main()