"""
Test configuration and shared fixtures for poker app tests.
"""
import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()