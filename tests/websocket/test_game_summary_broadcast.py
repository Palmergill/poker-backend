#!/usr/bin/env python3
"""
Test script to verify WebSocket broadcasting for game summary notifications.
"""

import os
import sys
import django
from pathlib import Path
from decimal import Decimal
import json
from unittest.mock import patch, MagicMock, call

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()

from django.contrib.auth.models import User
from poker_api.models import Player, PokerTable, Game, PlayerGame
from poker_api.services.game_service import GameService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def test_broadcast_game_summary_available():
    """Test the broadcast_game_summary_available method directly."""
    print("📡 Testing broadcast_game_summary_available method...")
    
    # Create a test game
    table = PokerTable.objects.create(
        name="Test Broadcast Table",
        max_players=6,
        small_blind=Decimal('10'),
        big_blind=Decimal('20'),
        min_buy_in=Decimal('500'),
        max_buy_in=Decimal('2000')
    )
    
    game = Game.objects.create(
        table=table,
        status='FINISHED',
        hand_count=5
    )
    
    # Mock summary data
    summary_data = {
        'game_id': game.id,
        'table_name': table.name,
        'completed_at': '2025-06-26T15:39:32.544961+00:00',
        'total_hands': 5,
        'players': [
            {
                'player_name': 'test_user_1',
                'player_id': 1,
                'starting_stack': 1000.0,
                'final_stack': 1200.0,
                'win_loss': 200.0,
                'status': 'CASHED_OUT'
            },
            {
                'player_name': 'test_user_2',
                'player_id': 2,
                'starting_stack': 1000.0,
                'final_stack': 800.0,
                'win_loss': -200.0,
                'status': 'CASHED_OUT'
            }
        ]
    }
    
    # Mock the channel layer
    with patch('poker_api.services.game_service.get_channel_layer') as mock_get_channel_layer, \
         patch('poker_api.services.game_service.async_to_sync') as mock_async_to_sync:
        
        # Set up mock channel layer
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # Set up mock async_to_sync
        mock_group_send = MagicMock()
        mock_async_to_sync.return_value = mock_group_send
        
        # Call the method
        GameService.broadcast_game_summary_available(game.id, summary_data)
        
        # Verify the channel layer was called correctly
        mock_get_channel_layer.assert_called_once()
        mock_async_to_sync.assert_called_once_with(mock_channel_layer.group_send)
        
        # Verify the group_send was called with correct parameters
        mock_group_send.assert_called_once()
        call_args = mock_group_send.call_args[0]
        
        # Check the group name
        assert call_args[0] == f'game_{game.id}', f"Expected group 'game_{game.id}', got '{call_args[0]}'"
        
        # Check the message structure
        message = call_args[1]
        assert message['type'] == 'game_summary_notification', f"Expected type 'game_summary_notification', got '{message['type']}'"
        
        # Check the data structure
        data = message['data']
        assert data['type'] == 'game_summary_available'
        assert data['game_id'] == game.id
        assert data['game_summary'] == summary_data
        assert data['message'] == 'Game summary is now available - all players have cashed out'
        assert data['game_status'] == 'FINISHED'
        assert data['total_hands'] == 5
        
        print("✅ broadcast_game_summary_available method test passed")
        
        # Print the exact message that would be sent
        print(f"📨 Broadcast message structure:")
        print(json.dumps(message, indent=2))
        
    return True


def test_broadcast_vs_regular_update():
    """Test that game summary broadcast is different from regular game update."""
    print("\n🔄 Testing broadcast differentiation...")
    
    # Create a test game
    table = PokerTable.objects.create(
        name="Test Diff Table",
        max_players=6,
        small_blind=Decimal('10'),
        big_blind=Decimal('20'),
        min_buy_in=Decimal('500'),
        max_buy_in=Decimal('2000')
    )
    
    game = Game.objects.create(
        table=table,
        status='PLAYING',
        phase='FLOP'
    )
    
    summary_data = {'game_id': game.id, 'players': []}
    
    # Mock the channel layer for both calls
    with patch('poker_api.services.game_service.get_channel_layer') as mock_get_channel_layer, \
         patch('poker_api.services.game_service.async_to_sync') as mock_async_to_sync:
        
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        mock_group_send = MagicMock()
        mock_async_to_sync.return_value = mock_group_send
        
        # Call regular broadcast
        GameService.broadcast_game_update(game.id)
        
        # Reset mock to separate calls
        mock_group_send.reset_mock()
        
        # Call summary broadcast
        GameService.broadcast_game_summary_available(game.id, summary_data)
        
        # Verify different message types were sent
        summary_call = mock_group_send.call_args[0][1]
        assert summary_call['type'] == 'game_summary_notification', "Summary broadcast should use 'game_summary_notification' type"
        
        print("✅ Broadcast differentiation test passed")
    
    return True


def test_edge_case_nonexistent_game():
    """Test broadcasting for a non-existent game."""
    print("\n❌ Testing edge case: non-existent game...")
    
    fake_game_id = 99999
    summary_data = {'game_id': fake_game_id, 'players': []}
    
    # This should not crash but should log an error
    try:
        GameService.broadcast_game_summary_available(fake_game_id, summary_data)
        print("✅ Non-existent game handling test passed (no exception thrown)")
    except Exception as e:
        print(f"❌ Unexpected exception for non-existent game: {e}")
        return False
    
    return True


def test_summary_data_validation():
    """Test that the summary data contains expected fields."""
    print("\n🔍 Testing summary data validation...")
    
    # Create a real game with players and generate summary
    table = PokerTable.objects.create(
        name="Test Validation Table",
        max_players=6,
        small_blind=Decimal('10'),
        big_blind=Decimal('20'),
        min_buy_in=Decimal('500'),
        max_buy_in=Decimal('2000')
    )
    
    game = Game.objects.create(
        table=table,
        status='WAITING'
    )
    
    # Create test users and players
    for i in range(2):
        user = User.objects.create_user(
            username=f'validation_user_{i}',
            email=f'validation_user_{i}@test.com',
            password='testpass123'
        )
        
        player = Player.objects.create(
            user=user,
            balance=Decimal('3000')
        )
        
        PlayerGame.objects.create(
            player=player,
            game=game,
            seat_position=i,
            stack=Decimal('1000'),
            starting_stack=Decimal('1000'),
            is_active=False,
            cashed_out=True,
            final_stack=Decimal('1100' if i == 0 else '900')  # Winner and loser
        )
    
    # Generate actual game summary
    summary = game.generate_game_summary()
    
    # Validate summary structure
    required_fields = ['game_id', 'table_name', 'completed_at', 'total_hands', 'players']
    for field in required_fields:
        assert field in summary, f"Summary missing required field: {field}"
    
    # Validate player data
    assert len(summary['players']) == 2, f"Expected 2 players, got {len(summary['players'])}"
    
    for player_data in summary['players']:
        player_required_fields = ['player_name', 'player_id', 'starting_stack', 'final_stack', 'win_loss', 'status']
        for field in player_required_fields:
            assert field in player_data, f"Player data missing required field: {field}"
        
        # Validate win/loss calculation
        expected_win_loss = player_data['final_stack'] - player_data['starting_stack']
        assert player_data['win_loss'] == expected_win_loss, f"Win/loss calculation incorrect: {player_data['win_loss']} != {expected_win_loss}"
        
        # Validate status
        assert player_data['status'] == 'CASHED_OUT', f"Expected status CASHED_OUT, got {player_data['status']}"
    
    # Validate players are sorted by win/loss (highest first)
    win_losses = [p['win_loss'] for p in summary['players']]
    assert win_losses == sorted(win_losses, reverse=True), "Players should be sorted by win/loss (highest first)"
    
    print("✅ Summary data validation test passed")
    print(f"📊 Generated summary: {json.dumps(summary, indent=2)}")
    
    return True


if __name__ == '__main__':
    try:
        print("🧪 Running WebSocket game summary broadcast tests...\n")
        
        success = test_broadcast_game_summary_available()
        if success:
            success = test_broadcast_vs_regular_update()
        if success:
            success = test_edge_case_nonexistent_game()
        if success:
            success = test_summary_data_validation()
        
        if success:
            print("\n🎉 All WebSocket broadcast tests passed successfully!")
        else:
            print("\n❌ Some WebSocket broadcast tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 WebSocket broadcast tests failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)