#!/usr/bin/env python3
"""
Browser test for API endpoints - tests the backend without needing React frontend.
"""

import os
import sys
import time
import unittest
import json
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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from poker_api.models import PokerTable, Player, Game


class APIBrowserTest(LiveServerTestCase):
    """Test API endpoints using browser automation."""
    
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
    
    def setUp(self):
        """Set up test."""
        super().setUp()
        
        # Clean up existing data
        User.objects.all().delete()
        Player.objects.all().delete()
        PokerTable.objects.all().delete()
        Game.objects.all().delete()
    
    def test_api_endpoints_respond(self):
        """Test that API endpoints respond correctly."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        # Test user registration endpoint
        register_url = f"{self.live_server_url}/api/register/"
        print(f"Testing register endpoint: {register_url}")
        
        # Use JavaScript to make API call
        self.driver.get("data:text/html,<html><body><div id='result'></div></body></html>")
        
        # Execute JavaScript to call the API
        register_script = f"""
        fetch('{register_url}', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{
                'username': 'testuser',
                'email': 'test@example.com',
                'password': 'testpass123'
            }})
        }})
        .then(response => response.json())
        .then(data => {{
            document.getElementById('result').innerHTML = JSON.stringify(data);
        }})
        .catch(error => {{
            document.getElementById('result').innerHTML = 'Error: ' + error;
        }});
        """
        
        self.driver.execute_script(register_script)
        time.sleep(3)
        
        # Get result
        result_element = self.driver.find_element(By.ID, "result")
        result_text = result_element.text
        print(f"Register API result: {result_text}")
        
        # Should contain success message or user data
        self.assertIn('testuser', result_text)
    
    def test_token_endpoint(self):
        """Test token authentication endpoint."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        # First create a user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Test token endpoint
        token_url = f"{self.live_server_url}/api/token/"
        print(f"Testing token endpoint: {token_url}")
        
        self.driver.get("data:text/html,<html><body><div id='result'></div></body></html>")
        
        token_script = f"""
        fetch('{token_url}', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{
                'username': 'testuser',
                'password': 'testpass123'
            }})
        }})
        .then(response => response.json())
        .then(data => {{
            document.getElementById('result').innerHTML = JSON.stringify(data);
        }})
        .catch(error => {{
            document.getElementById('result').innerHTML = 'Error: ' + error;
        }});
        """
        
        self.driver.execute_script(token_script)
        time.sleep(3)
        
        result_element = self.driver.find_element(By.ID, "result")
        result_text = result_element.text
        print(f"Token API result: {result_text}")
        
        # Should contain access token
        self.assertIn('access', result_text)
    
    def test_tables_endpoint(self):
        """Test tables endpoint."""
        if self.skip_tests:
            self.skipTest("Chrome not available for browser testing")
        
        # Create a test table
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        player = Player.objects.create(user=user, balance=1000.00)
        
        table = PokerTable.objects.create(
            name='Test Table',
            max_players=6,
            small_blind=0.50,
            big_blind=1.00,
            min_buy_in=50.00,
            max_buy_in=200.00
        )
        
        # Test tables endpoint
        tables_url = f"{self.live_server_url}/api/tables/"
        print(f"Testing tables endpoint: {tables_url}")
        
        self.driver.get("data:text/html,<html><body><div id='result'></div></body></html>")
        
        tables_script = f"""
        fetch('{tables_url}')
        .then(response => response.json())
        .then(data => {{
            document.getElementById('result').innerHTML = JSON.stringify(data);
        }})
        .catch(error => {{
            document.getElementById('result').innerHTML = 'Error: ' + error;
        }});
        """
        
        self.driver.execute_script(tables_script)
        time.sleep(3)
        
        result_element = self.driver.find_element(By.ID, "result")
        result_text = result_element.text
        print(f"Tables API result: {result_text}")
        
        # Should contain the test table
        self.assertIn('Test Table', result_text)


if __name__ == '__main__':
    unittest.main()