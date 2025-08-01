#!/usr/bin/env python3
"""
Test script to verify the hand history API is working correctly.
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
from poker_api.services.game_service import GameService
from poker_api.serializers import HandHistorySerializer
import json


def test_hand_history_api():
    """Test that hand history is being created and can be retrieved."""
    print("🃏 Testing hand history API...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_api').delete()
    PokerTable.objects.filter(name='Test API').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_api_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test API',
        max_players=6,
        small_blind=Decimal('5'),
        big_blind=Decimal('10'),
        min_buy_in=Decimal('100'),
        max_buy_in=Decimal('500')
    )
    
    print(f"✅ Created table '{table.name}' with {len(players)} players")
    
    # Create and start game
    game = GameService.create_game(table, players)
    GameService.start_game(game.id)
    game.refresh_from_db()
    
    print(f"✅ Started game {game.id}")
    
    # Check initial hand history count
    initial_count = HandHistory.objects.filter(game=game).count()
    print(f"📊 Initial hand history count: {initial_count}")
    
    # Complete one hand by having 2 players fold
    print(f"\n🔄 Completing a hand...")
    
    # First player folds
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    # Second player folds (this should end the hand)
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"✅ Hand completed. Game hand count: {game.hand_count}")
    
    # Check if hand history was created
    final_count = HandHistory.objects.filter(game=game).count()
    print(f"📊 Final hand history count: {final_count}")
    
    if final_count > initial_count:
        print(f"✅ Hand history was created!")
        
        # Check the hand history details
        hand_histories = HandHistory.objects.filter(game=game).order_by('-hand_number')
        for hh in hand_histories:
            print(f"\n📝 Hand History #{hh.hand_number}:")
            print(f"   Pot amount: ${hh.pot_amount}")
            print(f"   Final phase: {hh.final_phase}")
            print(f"   Completed at: {hh.completed_at}")
            
            # Check winner info
            winner_info = hh.get_winner_info()
            print(f"   Winner info: {winner_info}")
            
            # Test serialization (what the API would return)
            serializer = HandHistorySerializer(hh)
            serialized_data = serializer.data
            print(f"   Serialized data: {json.dumps(serialized_data, indent=2, default=str)}")
    else:
        print(f"❌ No hand history was created!")
        return False
    
    # Test the actual API response format
    print(f"\n🔍 Testing API response format...")
    
    hand_histories = HandHistory.objects.filter(game=game)
    serializer = HandHistorySerializer(hand_histories, many=True)
    api_response = {
        'hand_history': serializer.data
    }
    
    print(f"📡 API Response format:")
    print(json.dumps(api_response, indent=2, default=str))
    
    # Check if the response has the expected structure for frontend
    if api_response['hand_history']:
        first_hand = api_response['hand_history'][0]
        required_fields = ['hand_number', 'pot_amount', 'completed_at', 'winner_info']
        
        for field in required_fields:
            if field in first_hand:
                print(f"   ✅ Has required field: {field}")
            else:
                print(f"   ❌ Missing required field: {field}")
                return False
        
        # Check winner_info structure
        winner_info = first_hand.get('winner_info')
        if winner_info and 'winners' in winner_info:
            print(f"   ✅ Winner info has 'winners' field")
        else:
            print(f"   ❌ Winner info missing 'winners' field")
            print(f"       Actual winner_info: {winner_info}")
            return False
    else:
        print(f"   ❌ API response has no hand history data")
        return False
    
    return True


if __name__ == '__main__':
    try:
        success = test_hand_history_api()
        if success:
            print("\n✅ Hand history API test successful")
        else:
            print("\n❌ Hand history API test failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()