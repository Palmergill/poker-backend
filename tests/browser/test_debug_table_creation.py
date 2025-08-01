#!/usr/bin/env python3
"""
Debug table creation to see what happens.
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


class DebugTableCreationTest(TestCase):
    """Debug table creation flow."""
    
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
    
    def test_debug_table_flow(self):
        """Debug the table creation flow."""
        if not self.driver:
            self.skipTest("Chrome driver not available")
        
        print("=== Starting Table Creation Debug ===")
        
        # Register a user
        print("1. Registering user...")
        self.driver.get(f"{self.react_url}/register")
        time.sleep(2)
        
        inputs = self.driver.find_elements(By.TAG_NAME, 'input')
        if len(inputs) >= 4:
            inputs[0].send_keys('testuser123')  # username
            inputs[1].send_keys('test@example.com')  # email
            inputs[2].send_keys('testpass123')  # password
            inputs[3].send_keys('testpass123')  # confirm password
            
            register_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            register_button.click()
            time.sleep(3)
        
        # Login
        print("2. Logging in...")
        self.driver.get(f"{self.react_url}/login")
        time.sleep(2)
        
        login_inputs = self.driver.find_elements(By.TAG_NAME, 'input')
        if len(login_inputs) >= 2:
            login_inputs[0].send_keys('testuser123')  # username
            login_inputs[1].send_keys('testpass123')  # password
            
            login_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            login_button.click()
            time.sleep(3)
        
        print(f"After login - URL: {self.driver.current_url}")
        print(f"After login - Title: {self.driver.title}")
        
        # Look for create table elements
        print("3. Looking for create table elements...")
        buttons = self.driver.find_elements(By.TAG_NAME, 'button')
        links = self.driver.find_elements(By.TAG_NAME, 'a')
        
        print(f"Found {len(buttons)} buttons:")
        for i, btn in enumerate(buttons):
            print(f"  Button {i}: '{btn.text}' - classes: {btn.get_attribute('class')}")
        
        print(f"Found {len(links)} links:")
        for i, link in enumerate(links):
            print(f"  Link {i}: '{link.text}' - href: {link.get_attribute('href')}")
        
        # Try to find and click create table
        create_elements = []
        for btn in buttons:
            if 'create' in btn.text.lower() or 'table' in btn.text.lower():
                create_elements.append(('button', btn))
        
        for link in links:
            if 'create' in link.text.lower() or 'table' in link.text.lower():
                create_elements.append(('link', link))
        
        if create_elements:
            print(f"4. Found {len(create_elements)} potential create table elements")
            element_type, element = create_elements[0]
            print(f"Clicking {element_type}: '{element.text}'")
            element.click()
            time.sleep(3)
            
            print(f"After create click - URL: {self.driver.current_url}")
            print(f"After create click - Title: {self.driver.title}")
            
            # Look at the create table form
            print("5. Examining create table form...")
            form_inputs = self.driver.find_elements(By.TAG_NAME, 'input')
            print(f"Found {len(form_inputs)} inputs in create form:")
            for i, inp in enumerate(form_inputs):
                print(f"  Input {i}: type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")
            
            # Fill the form
            if len(form_inputs) >= 6:  # Expected number of inputs for table creation
                print("6. Filling table creation form...")
                form_inputs[0].send_keys('Test Table')  # name
                # Skip other fields for now, just submit
                
                submit_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                print(f"Submitting form with button: '{submit_button.text}'")
                submit_button.click()
                time.sleep(5)
                
                print(f"After submit - URL: {self.driver.current_url}")
                print(f"After submit - Title: {self.driver.title}")
                
                # Look at the resulting page
                print("7. Examining result page...")
                page_text = self.driver.find_element(By.TAG_NAME, 'body').text
                print(f"Page content (first 500 chars): {page_text[:500]}")
                
                # Look for table-related elements
                divs = self.driver.find_elements(By.TAG_NAME, 'div')
                table_divs = [div for div in divs if 'table' in div.get_attribute('class').lower()]
                print(f"Found {len(table_divs)} divs with 'table' in class name")
                
                # Look for any cards or list items
                cards = self.driver.find_elements(By.CSS_SELECTOR, '[class*="card"]')
                print(f"Found {len(cards)} elements with 'card' in class name")
                
        else:
            print("4. No create table elements found!")


if __name__ == '__main__':
    unittest.main()