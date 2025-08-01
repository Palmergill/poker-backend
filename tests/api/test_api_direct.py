#!/usr/bin/env python3
"""
Test script to directly test the hand history API endpoint.
"""

import os
import sys
import django
from pathlib import Path
from decimal import Decimal

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()

from django.contrib.auth.models import User
from poker_api.models import Player, PokerTable, Game, PlayerGame, GameAction, HandHistory
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


def test_api_directly():
    """Test the hand history API endpoint directly."""
    print("🔍 Testing hand history API endpoint directly...")
    
    # Get the game we created in the previous test
    try:
        game = Game.objects.get(id=31)
        print(f"✅ Found test game {game.id}")
    except Game.DoesNotExist:
        print("❌ Test game not found. Run test_frontend_logging.py first.")
        return False
    
    # Check if hand histories exist in database
    hand_histories = HandHistory.objects.filter(game=game)
    print(f"📊 Hand histories in database: {hand_histories.count()}")
    
    for hh in hand_histories:
        winner_info = hh.get_winner_info()
        print(f"   Hand #{hh.hand_number}: {winner_info}")
    
    # Test the API endpoint using Django's test client
    print(f"\n🌐 Testing API endpoint /api/games/{game.id}/hand-history/")
    
    # Get a user for authentication
    user = User.objects.filter(username__startswith='test_frontend').first()
    if not user:
        print("❌ No test user found")
        return False
    
    # Create API client and authenticate
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    # Make the API call
    response = client.get(f'/api/games/{game.id}/hand-history/', HTTP_HOST='localhost')
    print(f"📡 API Response Status: {response.status_code}")
    
    # Handle response data
    if hasattr(response, 'data'):
        print(f"📡 API Response Data: {response.data}")
        data = response.data
    else:
        # Parse JSON content
        import json
        try:
            data = json.loads(response.content.decode('utf-8'))
            print(f"📡 API Response Data: {data}")
        except json.JSONDecodeError:
            print(f"📡 API Response Content: {response.content}")
            return False
    
    # Test the response structure
    if response.status_code == 200:
        if 'hand_history' in data:
            print(f"✅ hand_history key found with {len(data['hand_history'])} items")
            
            for i, hand in enumerate(data['hand_history']):
                print(f"\n📝 Hand {i+1} data structure:")
                print(f"   Keys: {list(hand.keys())}")
                if 'winner_info' in hand:
                    print(f"   Winner info: {hand['winner_info']}")
                else:
                    print(f"   ❌ No winner_info key")
        else:
            print(f"❌ No 'hand_history' key in response")
            print(f"   Available keys: {list(data.keys())}")
    else:
        print(f"❌ API call failed: {data}")
    
    return response.status_code == 200


if __name__ == '__main__':
    try:
        success = test_api_directly()
        if success:
            print("\n✅ API test completed")
        else:
            print("\n❌ API test failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()