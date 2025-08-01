#!/usr/bin/env python3
"""
Detailed debugging test to fix authentication and navigation issues.
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


class DetailedDebugTest(TestCase):
    """Detailed debugging test to understand authentication and navigation flow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        
        # Application URLs
        cls.react_url = "http://localhost:3000"
        
        # Chrome options - visible browser for debugging
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Keep headless for now
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
            cls.driver.quit()
        super().tearDownClass()
    
    def wait_and_debug(self, description, wait_time=2):
        """Wait and print debug info."""
        time.sleep(wait_time)
        print(f"\n=== {description} ===")
        print(f"URL: {self.driver.current_url}")
        print(f"Title: {self.driver.title}")
        
        # Check for error messages
        try:
            error_elements = self.driver.find_elements(By.CSS_SELECTOR, '.error-message, .alert-danger, [class*="error"]')
            if error_elements:
                print("Error messages found:")
                for i, error in enumerate(error_elements):
                    if error.text.strip():
                        print(f"  Error {i}: {error.text}")
        except:
            pass
        
        # Check for success messages
        try:
            success_elements = self.driver.find_elements(By.CSS_SELECTOR, '.success-message, .alert-success, [class*="success"]')
            if success_elements:
                print("Success messages found:")
                for i, success in enumerate(success_elements):
                    if success.text.strip():
                        print(f"  Success {i}: {success.text}")
        except:
            pass
    
    def check_authentication_state(self):
        """Check if user is authenticated by looking at the navbar."""
        print("\n--- Checking Authentication State ---")
        
        # Look for login/register links (indicates not authenticated)
        login_links = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Login')]")
        register_links = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Register')]")
        
        # Look for user-specific elements (indicates authenticated)
        user_elements = self.driver.find_elements(By.CSS_SELECTOR, '.username, .user-info, .logout-btn')
        tables_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/tables') or contains(text(), 'Tables')]")
        
        print(f"Login links found: {len(login_links)}")
        print(f"Register links found: {len(register_links)}")
        print(f"User elements found: {len(user_elements)}")
        print(f"Tables links found: {len(tables_links)}")
        
        if user_elements or (tables_links and not login_links):
            print("✅ User appears to be authenticated")
            return True
        else:
            print("❌ User appears to be NOT authenticated")
            return False
    
    def test_detailed_authentication_flow(self):
        """Test authentication flow with detailed debugging."""
        if not self.driver:
            self.skipTest("Chrome driver not available")
        
        # Step 1: Navigate to registration
        print("🚀 Starting detailed authentication flow test...")
        self.driver.get(f"{self.react_url}/register")
        self.wait_and_debug("After navigating to register page")
        
        # Step 2: Fill registration form
        inputs = self.driver.find_elements(By.TAG_NAME, 'input')
        print(f"Found {len(inputs)} input fields for registration")
        
        if len(inputs) >= 4:
            print("Filling registration form...")
            inputs[0].clear()
            inputs[0].send_keys('debuguser')
            inputs[1].clear()
            inputs[1].send_keys('debug@test.com')
            inputs[2].clear()
            inputs[2].send_keys('debugpass123')
            inputs[3].clear()
            inputs[3].send_keys('debugpass123')
            
            # Submit registration
            register_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            print(f"Clicking register button: '{register_button.text}'")
            register_button.click()
            
            self.wait_and_debug("After registration submission", 3)
        
        # Step 3: Navigate to login (in case registration redirected elsewhere)
        print("Navigating to login page...")
        self.driver.get(f"{self.react_url}/login")
        self.wait_and_debug("After navigating to login page")
        
        # Step 4: Fill login form
        login_inputs = self.driver.find_elements(By.TAG_NAME, 'input')
        print(f"Found {len(login_inputs)} input fields for login")
        
        if len(login_inputs) >= 2:
            print("Filling login form...")
            login_inputs[0].clear()
            login_inputs[0].send_keys('debuguser')
            login_inputs[1].clear()
            login_inputs[1].send_keys('debugpass123')
            
            # Submit login
            login_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            print(f"Clicking login button: '{login_button.text}'")
            login_button.click()
            
            self.wait_and_debug("After login submission", 3)
        
        # Step 5: Check authentication state
        is_authenticated = self.check_authentication_state()
        
        # Step 6: Try to navigate to tables page
        print("Attempting to navigate to tables page...")
        self.driver.get(f"{self.react_url}/tables")
        self.wait_and_debug("After navigating to tables page", 2)
        
        # Step 7: Look for table-related elements
        print("\n--- Looking for table-related elements ---")
        
        # Look for create table button/link
        create_elements = []
        create_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Create') or contains(text(), 'create')]")
        create_links = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Create') or contains(text(), 'create') or contains(@href, 'create')]")
        
        print(f"Create buttons found: {len(create_buttons)}")
        for i, btn in enumerate(create_buttons):
            print(f"  Button {i}: '{btn.text}' - visible: {btn.is_displayed()}")
            
        print(f"Create links found: {len(create_links)}")
        for i, link in enumerate(create_links):
            print(f"  Link {i}: '{link.text}' - href: {link.get_attribute('href')} - visible: {link.is_displayed()}")
        
        # Look for existing tables
        table_cards = self.driver.find_elements(By.CSS_SELECTOR, '.table-card, [class*="table"], [class*="card"]')
        print(f"Table-like elements found: {len(table_cards)}")
        
        # Look for any lists or grids
        lists = self.driver.find_elements(By.CSS_SELECTOR, 'ul, ol, .list, .grid')
        print(f"List/grid elements found: {len(lists)}")
        
        # Get page text to see what's actually there
        body_text = self.driver.find_element(By.TAG_NAME, 'body').text
        print(f"\nPage body text (first 500 chars):\n{body_text[:500]}")
        
        if 'create' in body_text.lower() or 'table' in body_text.lower():
            print("✅ Page contains table-related text")
        else:
            print("❌ Page does not contain expected table-related text")
        
        # Step 8: If we found create elements, try to use them
        if create_buttons or create_links:
            element_to_click = create_buttons[0] if create_buttons else create_links[0]
            print(f"\nAttempting to click create element: '{element_to_click.text}'")
            
            try:
                element_to_click.click()
                self.wait_and_debug("After clicking create element", 3)
                
                # Look for form elements
                form_inputs = self.driver.find_elements(By.TAG_NAME, 'input')
                print(f"Form inputs found after clicking create: {len(form_inputs)}")
                
                for i, inp in enumerate(form_inputs):
                    print(f"  Input {i}: type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")
                
            except Exception as e:
                print(f"❌ Failed to click create element: {e}")
        
        return is_authenticated


if __name__ == '__main__':
    unittest.main()