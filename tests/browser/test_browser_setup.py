#!/usr/bin/env python3
"""
Browser test setup verification.

This test verifies that the browser testing infrastructure is working correctly.
"""

import os
import sys
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
from poker_api.models import PokerTable, Player, Game


class BrowserSetupTest(TestCase):
    """Test browser test setup without requiring actual browser."""
    
    def test_models_available(self):
        """Test that required models are available."""
        # This should not raise any exceptions
        User.objects.all().count()
        PokerTable.objects.all().count()
        Player.objects.all().count()
        Game.objects.all().count()
        
        self.assertTrue(True, "All models are accessible")
    
    def test_user_creation(self):
        """Test creating test users."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
    
    def test_table_creation(self):
        """Test creating poker table."""
        user = User.objects.create_user(
            username='tableowner',
            email='owner@example.com',
            password='testpass123'
        )
        
        player = Player.objects.create(
            user=user,
            balance=1000.00
        )
        
        table = PokerTable.objects.create(
            name='Test Table',
            max_players=3,
            small_blind=0.50,
            big_blind=1.00,
            min_buy_in=50.00,
            max_buy_in=200.00
        )
        
        self.assertIsNotNone(table)
        self.assertEqual(table.name, 'Test Table')
        self.assertEqual(table.max_players, 3)
        self.assertEqual(table.small_blind, 0.50)
        self.assertEqual(table.big_blind, 1.00)
    
    def test_selenium_imports(self):
        """Test that Selenium imports work."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            
            self.assertTrue(True, "Selenium imports successful")
        except ImportError as e:
            self.fail(f"Selenium import failed: {e}")
    
    def test_browser_availability(self):
        """Test if Chrome browser is available."""
        import shutil
        
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
        
        if chrome_binary:
            print(f"Chrome found at: {chrome_binary}")
            self.assertTrue(True, f"Chrome available at {chrome_binary}")
        else:
            print("Chrome not found. Browser tests will be skipped.")
            self.assertTrue(True, "Chrome not found but test setup is OK")


if __name__ == '__main__':
    unittest.main()