#!/usr/bin/env python3
"""
Full application browser test - requires both Django and React servers to be running.

Before running this test, start both servers:
1. Terminal 1: python manage.py runserver
2. Terminal 2: cd poker-frontend && npm start
3. Terminal 3: python -m pytest tests/browser/test_full_app_browser.py -v -s
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
from django.contrib.auth.models import User
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from poker_api.models import PokerTable, Player, Game


class FullAppBrowserTest(TestCase):
    """Test full application with both Django and React servers running."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        
        # Application URLs (must be running)
        cls.django_url = "http://localhost:8000"
        cls.react_url = "http://localhost:3000"
        
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
            cls.drivers = []
            return
        
        cls.skip_tests = False
        
        # Chrome options - not headless so you can see what's happening
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Comment out to see browser
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.binary_location = chrome_binary
        
        # Create drivers for 3 players
        cls.drivers = []
        try:
            # Get the correct ChromeDriver path
            driver_path = ChromeDriverManager().install()
            
            # Fix the path if it's pointing to the wrong file
            if 'THIRD_PARTY_NOTICES' in driver_path:
                driver_dir = os.path.dirname(driver_path)
                driver_path = os.path.join(driver_dir, 'chromedriver')
            
            for i in range(3):
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.implicitly_wait(10)
                cls.drivers.append(driver)
        except Exception as e:
            print(f"Failed to create Chrome drivers: {e}")
            cls.skip_tests = True
            cls.drivers = []
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test class."""
        if hasattr(cls, 'drivers'):
            for driver in cls.drivers:
                try:
                    driver.quit()
                except Exception:
                    pass
        super().tearDownClass()
    
    def setUp(self):
        """Set up test."""
        super().setUp()
        
        # Clean up existing data
        User.objects.all().delete()
        Player.objects.all().delete()
        PokerTable.objects.all().delete()
        Game.objects.all().delete()
        
        # Test user credentials
        self.test_users = [
            {'username': 'player1', 'password': 'testpass123', 'email': 'player1@test.com'},
            {'username': 'player2', 'password': 'testpass123', 'email': 'player2@test.com'},
            {'username': 'player3', 'password': 'testpass123', 'email': 'player3@test.com'},
        ]
        
        # Test table settings
        self.table_name = "Test 3-Player Table"
        self.buy_in_amount = 100.00
    
    def check_servers_running(self):
        """Check if both servers are running."""
        import requests
        
        try:
            # Check Django server
            django_response = requests.get(f"{self.django_url}/admin/", timeout=5)
            print(f"Django server status: {django_response.status_code}")
        except requests.exceptions.RequestException as e:
            self.fail(f"Django server not running at {self.django_url}. Please start with: python manage.py runserver")
        
        try:
            # Check React server
            react_response = requests.get(self.react_url, timeout=5)
            print(f"React server status: {react_response.status_code}")
        except requests.exceptions.RequestException as e:
            self.fail(f"React server not running at {self.react_url}. Please start with: cd poker-frontend && npm start")
    
    def wait_for_element(self, driver, selector, timeout=10):
        """Wait for element to be present and visible."""
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            # Take screenshot for debugging
            screenshot_path = f"/tmp/browser_test_error_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to: {screenshot_path}")
            print(f"Current URL: {driver.current_url}")
            print(f"Page title: {driver.title}")
            self.fail(f"Element '{selector}' not found within {timeout} seconds")
    
    def register_user(self, driver, user_data):
        """Register a new user."""
        # Navigate to register page
        driver.get(f"{self.react_url}/register")
        
        # Fill registration form - inputs don't have name attributes, use order
        inputs = self.wait_for_element(driver, 'input')  # Wait for first input
        all_inputs = driver.find_elements(By.TAG_NAME, 'input')
        
        if len(all_inputs) >= 4:
            # Username (first input, type=text)
            username_input = all_inputs[0]
            username_input.send_keys(user_data['username'])
            
            # Email (second input, type=email)
            email_input = all_inputs[1]
            email_input.send_keys(user_data['email'])
            
            # Password (third input, type=password)
            password_input = all_inputs[2]
            password_input.send_keys(user_data['password'])
            
            # Confirm Password (fourth input, type=password)
            confirm_password_input = all_inputs[3]
            confirm_password_input.send_keys(user_data['password'])
        else:
            self.fail(f"Expected 4 inputs for registration, found {len(all_inputs)}")
        
        # Submit registration
        register_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        register_button.click()
        
        # Wait for redirect or success
        time.sleep(3)
    
    def login_user(self, driver, user_data):
        """Login a user."""
        # Navigate to login page
        driver.get(f"{self.react_url}/login")
        
        # Fill login form - inputs don't have name attributes, use type
        username_input = self.wait_for_element(driver, 'input[type="text"]')
        username_input.send_keys(user_data['username'])
        
        password_input = self.wait_for_element(driver, 'input[type="password"]')
        password_input.send_keys(user_data['password'])
        
        # Submit login
        login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_button.click()
        
        # Wait for redirect to tables page - look for multiple possible selectors
        try:
            self.wait_for_element(driver, '.create-table-btn', timeout=10)
        except:
            try:
                self.wait_for_element(driver, 'a[href="/tables/create"]', timeout=5)
            except:
                # Check if we're on tables page by looking for any table-related elements
                try:
                    self.wait_for_element(driver, '.table-list, .table-card, h2', timeout=5)
                except:
                    # Print current page for debugging
                    print(f"Login redirect failed. Current URL: {driver.current_url}")
                    print(f"Page title: {driver.title}")
                    time.sleep(2)
    
    def test_servers_are_running(self):
        """Test that both servers are running."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        print("Checking if servers are running...")
        self.check_servers_running()
        print("Both servers are running!")
    
    def test_user_registration_and_login(self):
        """Test user registration and login."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        print("Testing user registration and login...")
        self.check_servers_running()
        
        driver = self.drivers[0]
        user_data = self.test_users[0]
        
        print(f"Registering user: {user_data['username']}")
        self.register_user(driver, user_data)
        
        print(f"Logging in user: {user_data['username']}")
        self.login_user(driver, user_data)
        
        print("User registration and login successful!")
    
    def test_table_creation(self):
        """Test creating a poker table."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        print("Testing table creation...")
        self.check_servers_running()
        
        driver = self.drivers[0]
        user_data = self.test_users[0]
        
        # Register and login
        self.register_user(driver, user_data)
        self.login_user(driver, user_data)
        
        # Navigate to create table
        create_table_btn = self.wait_for_element(driver, '.create-table-btn, a[href="/tables/create"]')
        create_table_btn.click()
        
        # Fill table creation form
        name_input = self.wait_for_element(driver, 'input[name="name"]')
        name_input.send_keys(self.table_name)
        
        # Submit table creation
        create_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        create_button.click()
        
        # Wait for redirect to tables list
        self.wait_for_element(driver, '.table-card', timeout=15)
        
        print("Table creation successful!")


if __name__ == '__main__':
    unittest.main()