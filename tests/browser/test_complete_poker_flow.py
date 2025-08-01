#!/usr/bin/env python3
"""
Complete poker game flow browser test with all issues fixed.

This test properly handles:
1. Correct input selectors (no name attributes)
2. Proper authentication state detection
3. Robust error handling and debugging
4. Complete 3-player game flow
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from poker_api.models import PokerTable, Player, Game


class CompletePokerFlowTest(TestCase):
    """Complete poker game flow browser test with proper error handling."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        
        # Application URLs
        cls.django_url = "http://localhost:8000"
        cls.react_url = "http://localhost:3000"
        
        # Chrome setup
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        
        # Check if Chrome is available
        import shutil
        chrome_binary = None
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
        
        for path in chrome_paths:
            if path and Path(path).exists():
                chrome_binary = path
                break
        
        if not chrome_binary:
            print("Chrome not found. Skipping browser tests.")
            cls.skip_tests = True
            cls.drivers = []
            return
        
        chrome_options.binary_location = chrome_binary
        cls.skip_tests = False
        
        # Create drivers for 3 players
        cls.drivers = []
        try:
            driver_path = ChromeDriverManager().install()
            if 'THIRD_PARTY_NOTICES' in driver_path:
                import os
                driver_dir = os.path.dirname(driver_path)
                driver_path = os.path.join(driver_dir, 'chromedriver')
            
            for i in range(3):
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.implicitly_wait(5)  # Reduced timeout
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
        
        self.table_name = "Test 3-Player Table"
        self.buy_in_amount = 100.00
    
    def debug_print(self, message, driver=None):
        """Print debug information."""
        print(f"\n🔍 {message}")
        if driver:
            print(f"   URL: {driver.current_url}")
            print(f"   Title: {driver.title}")
            
            # Check for error messages
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, '.error-message, .alert-danger, [class*="error"]')
                for error in error_elements:
                    if error.text.strip():
                        print(f"   ❌ Error: {error.text}")
            except:
                pass
    
    def wait_for_element_robust(self, driver, selectors, timeout=10, description=""):
        """Wait for element using multiple selectors."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return element
            except TimeoutException:
                continue
        
        # If we get here, none of the selectors worked
        self.debug_print(f"Failed to find element: {description}", driver)
        raise AssertionError(f"None of the selectors {selectors} found within {timeout} seconds")
    
    def check_authentication_state(self, driver):
        """Check if user is authenticated."""
        try:
            # Look for authenticated user indicators
            user_indicators = [
                '.username',
                '.user-info', 
                '.logout-btn',
                'a[href="/profile"]',
                'a[href*="/tables"]'
            ]
            
            for selector in user_indicators:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return True
            
            # Alternative: check if we can access tables page
            current_url = driver.current_url
            if '/tables' in current_url and '/login' not in current_url:
                return True
                
            return False
            
        except Exception:
            return False
    
    def register_user(self, driver, user_data):
        """Register a new user with proper error handling."""
        self.debug_print(f"Registering user: {user_data['username']}", driver)
        
        # Navigate to register page
        driver.get(f"{self.react_url}/register")
        time.sleep(2)
        
        # Wait for registration form
        self.wait_for_element_robust(driver, 'input[type="text"]', description="username input")
        
        # Get all inputs - they appear in order: username, email, password, confirmPassword
        inputs = driver.find_elements(By.TAG_NAME, 'input')
        
        if len(inputs) < 4:
            raise AssertionError(f"Expected 4 inputs for registration, found {len(inputs)}")
        
        # Fill form
        inputs[0].clear()
        inputs[0].send_keys(user_data['username'])
        
        inputs[1].clear()
        inputs[1].send_keys(user_data['email'])
        
        inputs[2].clear()
        inputs[2].send_keys(user_data['password'])
        
        inputs[3].clear()
        inputs[3].send_keys(user_data['password'])
        
        # Submit registration
        submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_btn.click()
        
        # Wait for registration to complete
        time.sleep(3)
        self.debug_print("Registration completed", driver)
    
    def login_user(self, driver, user_data):
        """Login user with proper authentication state checking."""
        self.debug_print(f"Logging in user: {user_data['username']}", driver)
        
        # Navigate to login page
        driver.get(f"{self.react_url}/login")
        time.sleep(2)
        
        # Wait for login form
        self.wait_for_element_robust(driver, 'input[type="text"]', description="username input")
        
        # Get login inputs
        username_input = driver.find_element(By.CSS_SELECTOR, 'input[type="text"]')
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        
        # Fill form
        username_input.clear()
        username_input.send_keys(user_data['username'])
        
        password_input.clear()
        password_input.send_keys(user_data['password'])
        
        # Submit login
        login_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_btn.click()
        
        # Wait for login to complete and check authentication state
        time.sleep(3)
        
        # Check if login was successful
        max_attempts = 5
        for attempt in range(max_attempts):
            if self.check_authentication_state(driver):
                self.debug_print("Login successful - user authenticated", driver)
                return True
            
            # If still on login page, there might be an error
            if '/login' in driver.current_url:
                time.sleep(2)  # Wait a bit more
                continue
            
            # If redirected elsewhere, consider it successful
            if '/tables' in driver.current_url:
                self.debug_print("Login successful - redirected to tables", driver)
                return True
            
            time.sleep(1)
        
        # Login failed
        self.debug_print("Login failed - user not authenticated", driver)
        return False
    
    def create_table(self, driver):
        """Create a poker table with proper navigation."""
        self.debug_print("Creating table", driver)
        
        # Ensure we're on tables page
        driver.get(f"{self.react_url}/tables")
        time.sleep(2)
        
        # Look for create table button/link
        create_selectors = [
            'button:contains("Create")',
            'a[href*="/create"]',
            'a[href="/tables/create"]',
            '.create-table-btn',
            '.btn-primary'
        ]
        
        # Try to find create button using text content
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        links = driver.find_elements(By.TAG_NAME, 'a')
        
        create_element = None
        
        # Check buttons for create text
        for btn in buttons:
            if 'create' in btn.text.lower():
                create_element = btn
                break
        
        # Check links for create text or href
        if not create_element:
            for link in links:
                if 'create' in link.text.lower() or 'create' in link.get_attribute('href'):
                    create_element = link
                    break
        
        if not create_element:
            raise AssertionError("Could not find create table button or link")
        
        # Click create element
        create_element.click()
        time.sleep(2)
        self.debug_print("Clicked create table", driver)
        
        # Wait for create table form
        self.wait_for_element_robust(driver, 'input', description="table form input")
        
        # Get form inputs - look for name input specifically
        inputs = driver.find_elements(By.TAG_NAME, 'input')
        if not inputs:
            raise AssertionError("No inputs found in create table form")
        
        # Fill table name (first input is usually name)
        name_input = inputs[0]
        name_input.clear()
        name_input.send_keys(self.table_name)
        
        # Submit form
        submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_btn.click()
        
        # Wait for table creation to complete
        time.sleep(3)
        self.debug_print("Table creation completed", driver)
    
    def join_table(self, driver, table_name):
        """Join a table with proper element finding."""
        self.debug_print(f"Joining table: {table_name}", driver)
        
        # Navigate to tables page
        driver.get(f"{self.react_url}/tables")
        time.sleep(2)
        
        # Look for table with matching name
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        if table_name not in page_text:
            raise AssertionError(f"Table '{table_name}' not found on page")
        
        # Look for join button
        join_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Join')]")
        if not join_buttons:
            raise AssertionError("No join buttons found")
        
        # Click first join button
        join_buttons[0].click()
        time.sleep(2)
        
        # Handle buy-in dialog if it appears
        try:
            buy_in_input = driver.find_element(By.CSS_SELECTOR, 'input[type="number"]')
            buy_in_input.clear()
            buy_in_input.send_keys(str(self.buy_in_amount))
            
            # Find confirm button
            confirm_btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'Join') or contains(text(), 'Confirm')]")
            if confirm_btns:
                confirm_btns[0].click()
            
        except NoSuchElementException:
            # No buy-in dialog, that's okay
            pass
        
        time.sleep(3)
        self.debug_print("Table join completed", driver)
    
    def test_complete_three_player_flow(self):
        """Test complete 3-player poker game flow."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        print("🎯 Starting complete 3-player poker game flow test...")
        
        # Check servers are running
        self.check_servers_running()
        
        # Step 1: Register and login all players
        print("\n📝 Step 1: Register and login all players")
        for i, (driver, user_data) in enumerate(zip(self.drivers, self.test_users)):
            print(f"   Setting up player {i+1}: {user_data['username']}")
            
            self.register_user(driver, user_data)
            success = self.login_user(driver, user_data)
            
            if not success:
                self.fail(f"Failed to login user {user_data['username']}")
        
        # Step 2: First player creates table
        print("\n🏗️ Step 2: Creating table")
        self.create_table(self.drivers[0])
        
        # Step 3: All players join table
        print("\n🎮 Step 3: Players joining table")
        for i, driver in enumerate(self.drivers):
            print(f"   Player {i+1} joining table...")
            self.join_table(driver, self.table_name)
        
        # Step 4: Verify all players are in game
        print("\n✅ Step 4: Verifying game state")
        for i, driver in enumerate(self.drivers):
            # Check if we're on a game page
            current_url = driver.current_url
            if '/games/' not in current_url and '/tables/' not in current_url:
                self.fail(f"Player {i+1} not on game page: {current_url}")
        
        print("\n🎉 Test completed successfully!")
        print(f"✅ All {len(self.drivers)} players registered and logged in")
        print(f"✅ Table '{self.table_name}' created")
        print(f"✅ All players joined the table")
    
    def check_servers_running(self):
        """Check if both servers are running."""
        import requests
        
        try:
            django_response = requests.get(f"{self.django_url}/admin/", timeout=5)
            print(f"✅ Django server running (status: {django_response.status_code})")
        except requests.exceptions.RequestException:
            self.fail(f"Django server not running at {self.django_url}")
        
        try:
            react_response = requests.get(self.react_url, timeout=5)
            print(f"✅ React server running (status: {react_response.status_code})")
        except requests.exceptions.RequestException:
            self.fail(f"React server not running at {self.react_url}")
    
    def test_single_user_flow(self):
        """Test single user authentication flow."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        print("🧪 Testing single user authentication flow...")
        
        self.check_servers_running()
        
        driver = self.drivers[0]
        user_data = self.test_users[0]
        
        # Register user
        self.register_user(driver, user_data)
        
        # Login user
        success = self.login_user(driver, user_data)
        self.assertTrue(success, "User login should be successful")
        
        # Check authentication state
        is_authenticated = self.check_authentication_state(driver)
        self.assertTrue(is_authenticated, "User should be authenticated")
        
        print("✅ Single user authentication test passed!")


if __name__ == '__main__':
    unittest.main()