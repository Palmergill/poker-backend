#!/usr/bin/env python3
"""
Test script to verify the complete hand history functionality:
1. Initial loading of existing hand history
2. Real-time updates via WebSocket
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
from poker_api.serializers import GameSerializer
import json


def test_hand_history_complete():
    """Test complete hand history functionality."""
    print("🃏 Testing complete hand history functionality...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_complete').delete()
    PokerTable.objects.filter(name='Test Complete History').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_complete_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Complete History',
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
    
    # Complete first hand to create hand history
    print(f"\n🔄 Completing first hand...")
    
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
    
    print(f"✅ First hand completed. Game hand count: {game.hand_count}")
    
    # Test 1: Check if hand history was created
    hand_histories = HandHistory.objects.filter(game=game)
    print(f"\n📊 Test 1 - Hand History Creation:")
    print(f"   Hand histories created: {hand_histories.count()}")
    
    if hand_histories.count() == 0:
        print("❌ No hand history was created!")
        return False
    
    for hh in hand_histories:
        print(f"   Hand #{hh.hand_number}: ${hh.pot_amount} pot, winner: {hh.get_winner_info()}")
    
    # Test 2: Check API endpoint response format
    print(f"\n📡 Test 2 - API Endpoint Format:")
    
    from poker_api.serializers import HandHistorySerializer
    serializer = HandHistorySerializer(hand_histories, many=True)
    api_response = {
        'game_id': game.id,
        'hand_history': serializer.data
    }
    
    print(f"   API response structure: {list(api_response.keys())}")
    if api_response['hand_history']:
        first_hand = api_response['hand_history'][0]
        print(f"   First hand fields: {list(first_hand.keys())}")
        print(f"   Winner info structure: {first_hand.get('winner_info', {})}")
    
    # Test 3: Check WebSocket broadcast data includes winner_info
    print(f"\n📻 Test 3 - WebSocket Broadcast Data:")
    
    # Test the GameSerializer that's used for WebSocket broadcasts
    game_serializer = GameSerializer(game)
    websocket_data = game_serializer.data
    
    print(f"   WebSocket data includes winner_info: {'winner_info' in websocket_data}")
    if 'winner_info' in websocket_data:
        print(f"   Winner info in WebSocket: {websocket_data['winner_info']}")
    else:
        print("❌ winner_info missing from WebSocket data!")
        return False
    
    # Test 4: Complete another hand and verify winner_info is set
    print(f"\n🔄 Test 4 - Second Hand with Winner Info:")
    
    # Take some actions to get to a state where we have winner_info
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds to end second hand")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds to end second hand")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"   Second hand completed. Game hand count: {game.hand_count}")
    
    # Check if game has winner_info set
    print(f"   Game winner_info: {game.get_winner_info()}")
    
    # Check WebSocket data again
    game_serializer = GameSerializer(game)
    websocket_data = game_serializer.data
    print(f"   Updated WebSocket winner_info: {websocket_data.get('winner_info')}")
    
    # Test 5: Verify frontend data transformation would work
    print(f"\n🔄 Test 5 - Frontend Data Transformation:")
    
    # Simulate what the frontend would receive
    hand_histories = HandHistory.objects.filter(game=game).order_by('-hand_number')
    serializer = HandHistorySerializer(hand_histories, many=True)
    frontend_api_data = {
        'game_id': game.id,
        'hand_history': serializer.data
    }
    
    # Simulate frontend transformation
    if frontend_api_data['hand_history']:
        formatted_history = []
        for hand in frontend_api_data['hand_history']:
            transformed = {
                'timestamp': hand['completed_at'],  # Frontend would convert this
                'winners': hand['winner_info']['winners'] if hand['winner_info'] else [],
                'potAmount': hand['pot_amount'] or 0,
                'type': hand['winner_info']['type'] if hand['winner_info'] else 'Unknown'
            }
            formatted_history.append(transformed)
            print(f"   Transformed hand: {transformed}")
        
        print(f"   ✅ Frontend would show {len(formatted_history)} hands in history")
    else:
        print("❌ No hand history data for frontend!")
        return False
    
    return True


if __name__ == '__main__':
    try:
        success = test_hand_history_complete()
        if success:
            print("\n✅ Complete hand history test successful")
        else:
            print("\n❌ Complete hand history test failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()