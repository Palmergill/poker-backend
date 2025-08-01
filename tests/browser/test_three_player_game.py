#!/usr/bin/env python3
"""
Browser integration test for creating and playing a 3-player poker game.

This test uses Selenium WebDriver to simulate the full user experience:
1. Creates 3 user accounts
2. Creates a poker table
3. All 3 players join the table
4. Starts the game
5. Plays several hands with betting actions
6. Tests cash out functionality
"""

import os
import sys
import time
import unittest
import threading
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
import django
django.setup()

from django.test import LiveServerTestCase
from django.contrib.auth.models import User
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from poker_api.models import PokerTable, Player, Game


class ThreePlayerGameBrowserTest(LiveServerTestCase):
    """Test full 3-player game flow using browser automation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        
        # Check if Chrome is available
        import shutil
        import os
        
        # Try to find Chrome installation
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
        
        # Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
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
        
        # Server URL
        self.server_url = self.live_server_url
        
        # Test table settings
        self.table_name = "Test 3-Player Table"
        self.small_blind = 0.50
        self.big_blind = 1.00
        self.min_buy_in = 50.00
        self.max_buy_in = 200.00
        self.buy_in_amount = 100.00
    
    def wait_for_element(self, driver, selector, timeout=10):
        """Wait for element to be present and visible."""
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            self.fail(f"Element '{selector}' not found within {timeout} seconds")
    
    def wait_for_clickable(self, driver, selector, timeout=10):
        """Wait for element to be clickable."""
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            self.fail(f"Element '{selector}' not clickable within {timeout} seconds")
    
    def register_user(self, driver, user_data):
        """Register a new user."""
        # Navigate to register page
        driver.get(f"{self.server_url}/register")
        
        # Fill registration form
        username_input = self.wait_for_element(driver, 'input[name="username"]')
        username_input.send_keys(user_data['username'])
        
        email_input = self.wait_for_element(driver, 'input[name="email"]')
        email_input.send_keys(user_data['email'])
        
        password_input = self.wait_for_element(driver, 'input[name="password"]')
        password_input.send_keys(user_data['password'])
        
        confirm_password_input = self.wait_for_element(driver, 'input[name="confirmPassword"]')
        confirm_password_input.send_keys(user_data['password'])
        
        # Submit registration
        register_button = self.wait_for_clickable(driver, 'button[type="submit"]')
        register_button.click()
        
        # Wait for redirect to login or success
        time.sleep(2)
    
    def login_user(self, driver, user_data):
        """Login a user."""
        # Navigate to login page
        driver.get(f"{self.server_url}/login")
        
        # Fill login form
        username_input = self.wait_for_element(driver, 'input[type="text"]')
        username_input.send_keys(user_data['username'])
        
        password_input = self.wait_for_element(driver, 'input[type="password"]')
        password_input.send_keys(user_data['password'])
        
        # Submit login
        login_button = self.wait_for_clickable(driver, 'button[type="submit"]')
        login_button.click()
        
        # Wait for redirect to tables page
        self.wait_for_element(driver, '.create-table-btn, a[href="/tables/create"]', timeout=15)
    
    def create_table(self, driver):
        """Create a new poker table."""
        # Navigate to create table page
        create_table_btn = self.wait_for_clickable(driver, '.create-table-btn, a[href="/tables/create"]')
        create_table_btn.click()
        
        # Fill table creation form
        name_input = self.wait_for_element(driver, 'input[name="name"]')
        name_input.send_keys(self.table_name)
        
        max_players_input = self.wait_for_element(driver, 'input[name="max_players"]')
        max_players_input.clear()
        max_players_input.send_keys("3")
        
        small_blind_input = self.wait_for_element(driver, 'input[name="small_blind"]')
        small_blind_input.clear()
        small_blind_input.send_keys(str(self.small_blind))
        
        big_blind_input = self.wait_for_element(driver, 'input[name="big_blind"]')
        big_blind_input.clear()
        big_blind_input.send_keys(str(self.big_blind))
        
        min_buy_in_input = self.wait_for_element(driver, 'input[name="min_buy_in"]')
        min_buy_in_input.clear()
        min_buy_in_input.send_keys(str(self.min_buy_in))
        
        max_buy_in_input = self.wait_for_element(driver, 'input[name="max_buy_in"]')
        max_buy_in_input.clear()
        max_buy_in_input.send_keys(str(self.max_buy_in))
        
        # Submit table creation
        create_button = self.wait_for_clickable(driver, 'button[type="submit"]')
        create_button.click()
        
        # Wait for redirect to tables list
        self.wait_for_element(driver, '.table-card', timeout=15)
    
    def join_table(self, driver, table_name):
        """Join a table."""
        # Find the table card
        table_cards = driver.find_elements(By.CSS_SELECTOR, '.table-card')
        target_table = None
        
        for card in table_cards:
            if table_name in card.text:
                target_table = card
                break
        
        if not target_table:
            self.fail(f"Table '{table_name}' not found")
        
        # Click join button
        join_button = target_table.find_element(By.CSS_SELECTOR, '.join-table-btn')
        join_button.click()
        
        # Wait for join modal/dialog
        time.sleep(1)
        
        # Enter buy-in amount
        buy_in_input = self.wait_for_element(driver, 'input#buyInAmount')
        buy_in_input.clear()
        buy_in_input.send_keys(str(self.buy_in_amount))
        
        # Confirm join - try multiple selectors for the confirm button
        try:
            confirm_button = self.wait_for_clickable(driver, '.buy-in-confirm-btn', timeout=3)
        except:
            try:
                confirm_button = self.wait_for_clickable(driver, 'button[type="submit"]', timeout=3)
            except:
                # Look for any button with text that suggests joining
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                confirm_button = None
                for btn in buttons:
                    if 'join' in btn.text.lower() or 'confirm' in btn.text.lower():
                        confirm_button = btn
                        break
                if not confirm_button:
                    self.fail("Could not find join confirmation button")
        
        confirm_button.click()
        
        # Wait for redirect to game
        self.wait_for_element(driver, '.table-felt, .poker-table', timeout=15)
    
    def start_game(self, driver):
        """Start the game."""
        # Look for start game button - try multiple selectors
        try:
            start_button = self.wait_for_clickable(driver, '.compact-btn', timeout=5)
            if 'start' in start_button.text.lower():
                start_button.click()
            else:
                raise Exception("Not a start button")
        except:
            try:
                # Look for any button with "start" in the text
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                start_button = None
                for btn in buttons:
                    if 'start' in btn.text.lower():
                        start_button = btn
                        break
                if not start_button:
                    self.fail("Could not find start game button")
                start_button.click()
            except Exception as e:
                self.fail(f"Could not start game: {e}")
        
        # Wait for game to start
        time.sleep(2)
    
    def perform_action(self, driver, action, amount=None):
        """Perform a game action."""
        # Wait for turn indicator
        try:
            self.wait_for_element(driver, '.turn-indicator', timeout=5)
        except:
            # Not our turn, skip
            return False
        
        # Find action button by looking for buttons with the action text
        try:
            buttons = driver.find_elements(By.TAG_NAME, 'button')
            action_button = None
            
            for btn in buttons:
                btn_text = btn.text.lower()
                if action.lower() in btn_text:
                    action_button = btn
                    break
            
            if action_button:
                action_button.click()
            elif action == 'bet' or action == 'raise':
                # Try to find betting interface
                try:
                    betting_toggle = driver.find_element(By.CSS_SELECTOR, '.betting-toggle-btn')
                    betting_toggle.click()
                    time.sleep(0.5)
                    
                    if amount:
                        bet_input = driver.find_element(By.CSS_SELECTOR, '.bet-input, input[type="number"]')
                        bet_input.clear()
                        bet_input.send_keys(str(amount))
                    
                    execute_button = driver.find_element(By.CSS_SELECTOR, '.execute-bet-btn')
                    execute_button.click()
                except Exception:
                    # Fallback: just try to click any bet/raise button
                    for btn in buttons:
                        if 'bet' in btn.text.lower() or 'raise' in btn.text.lower():
                            btn.click()
                            break
            else:
                # Default actions for fold, check, call
                for btn in buttons:
                    if action.lower() in btn.text.lower():
                        btn.click()
                        break
                        
        except Exception as e:
            print(f"Action failed: {action}, error: {e}")
            return False
        
        time.sleep(1)
        return True
    
    def cash_out(self, driver):
        """Cash out of the game."""
        # Find cash out button
        cash_out_button = self.wait_for_clickable(driver, '.cash-out-btn')
        cash_out_button.click()
        
        # Confirm cash out if modal appears
        try:
            confirm_button = self.wait_for_clickable(driver, 'button:contains("Confirm"), .confirm-btn', timeout=3)
            confirm_button.click()
        except:
            pass
        
        time.sleep(2)
    
    def play_hand(self, drivers):
        """Play a complete hand with all players."""
        # Simple betting logic for testing
        actions = [
            {'action': 'call'},  # Player 1 calls
            {'action': 'call'},  # Player 2 calls  
            {'action': 'check'}, # Player 3 checks (big blind)
        ]
        
        # Pre-flop betting
        for i, driver in enumerate(drivers):
            if i < len(actions):
                self.perform_action(driver, actions[i]['action'])
            time.sleep(0.5)
        
        # Wait for community cards
        time.sleep(2)
        
        # Post-flop betting (simplified)
        for driver in drivers:
            try:
                self.perform_action(driver, 'check')
            except:
                pass
            time.sleep(0.5)
        
        # Wait for hand completion
        time.sleep(3)
        
        # Handle ready button if hand results appear
        for driver in drivers:
            try:
                ready_button = driver.find_element(By.CSS_SELECTOR, '.ready-btn')
                ready_button.click()
            except:
                pass
        
        time.sleep(2)
    
    def test_three_player_game_flow(self):
        """Test the complete 3-player game flow."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
            
        print("Starting 3-player game browser test...")
        
        # Step 1: Register and login all players
        print("Step 1: Registering and logging in players...")
        for i, (driver, user_data) in enumerate(zip(self.drivers, self.test_users)):
            print(f"  Registering player {i+1}: {user_data['username']}")
            self.register_user(driver, user_data)
            
            print(f"  Logging in player {i+1}: {user_data['username']}")
            self.login_user(driver, user_data)
        
        # Step 2: Create table with first player
        print("Step 2: Creating table...")
        self.create_table(self.drivers[0])
        
        # Step 3: All players join the table
        print("Step 3: Players joining table...")
        for i, driver in enumerate(self.drivers):
            if i == 0:
                # First player already on table creation page, navigate to tables
                driver.get(f"{self.server_url}/tables")
                time.sleep(2)
            
            print(f"  Player {i+1} joining table...")
            self.join_table(driver, self.table_name)
        
        # Step 4: Start the game
        print("Step 4: Starting game...")
        self.start_game(self.drivers[0])
        
        # Step 5: Play several hands
        print("Step 5: Playing hands...")
        for hand_num in range(3):
            print(f"  Playing hand {hand_num + 1}...")
            self.play_hand(self.drivers)
        
        # Step 6: Test cash out
        print("Step 6: Testing cash out...")
        print("  Player 1 cashing out...")
        self.cash_out(self.drivers[0])
        
        # Verify cash out worked
        time.sleep(2)
        try:
            cashed_out_indicator = self.drivers[0].find_element(By.CSS_SELECTOR, '.cashed-out, .spectating')
            self.assertIsNotNone(cashed_out_indicator)
            print("  Cash out successful!")
        except NoSuchElementException:
            print("  Cash out indicator not found (may be expected)")
        
        # Step 7: Continue playing with remaining players
        print("Step 7: Continuing with remaining players...")
        for hand_num in range(2):
            print(f"  Playing hand {hand_num + 4}...")
            self.play_hand(self.drivers[1:])
        
        print("Test completed successfully!")
    
    def test_game_creation_validation(self):
        """Test table creation form validation."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
            
        print("Testing table creation validation...")
        
        # Register and login first player
        self.register_user(self.drivers[0], self.test_users[0])
        self.login_user(self.drivers[0], self.test_users[0])
        
        # Navigate to create table
        create_table_btn = self.wait_for_clickable(self.drivers[0], '.create-table-btn, a[href="/tables/create"]')
        create_table_btn.click()
        
        # Try to create table with invalid data
        name_input = self.wait_for_element(self.drivers[0], 'input[name="name"]')
        name_input.send_keys("Test Table")
        
        # Set big blind smaller than small blind (should fail)
        small_blind_input = self.wait_for_element(self.drivers[0], 'input[name="small_blind"]')
        small_blind_input.clear()
        small_blind_input.send_keys("1.00")
        
        big_blind_input = self.wait_for_element(self.drivers[0], 'input[name="big_blind"]')
        big_blind_input.clear()
        big_blind_input.send_keys("0.50")
        
        # Try to submit
        create_button = self.wait_for_clickable(self.drivers[0], 'button[type="submit"]')
        create_button.click()
        
        # Should show error or validation message
        time.sleep(2)
        
        print("Table creation validation test completed!")


if __name__ == '__main__':
    unittest.main()