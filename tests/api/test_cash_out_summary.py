#!/usr/bin/env python3
"""
Test script to test the enhanced cash out endpoint logic for game summary generation.
"""

import os
import sys
import django
from pathlib import Path
from decimal import Decimal
import json

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()

from django.contrib.auth.models import User
from poker_api.models import Player, PokerTable, Game, PlayerGame
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock


def create_test_game_with_players():
    """Create a test game with multiple players."""
    print("🎮 Creating test game with players...")
    
    # Create or get a test table
    table, created = PokerTable.objects.get_or_create(
        name="Test Cash Out Table",
        defaults={
            'max_players': 6,
            'small_blind': Decimal('10'),
            'big_blind': Decimal('20'),
            'min_buy_in': Decimal('500'),
            'max_buy_in': Decimal('2000')
        }
    )
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        username = f"test_cashout_user_{i}"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@test.com'}
        )
        if created:
            user.set_password('testpass123')
            user.save()
        
        player, created = Player.objects.get_or_create(
            user=user,
            defaults={'balance': Decimal('3000')}
        )
        
        users.append(user)
        players.append(player)
    
    # Create a game
    game = Game.objects.create(
        table=table,
        status='WAITING',
        pot=0,
        current_bet=0,
        dealer_position=0,
    )
    
    # Add players to the game
    for i, player in enumerate(players):
        PlayerGame.objects.create(
            player=player,
            game=game,
            seat_position=i,
            stack=Decimal('1000'),
            starting_stack=Decimal('1000'),
            is_active=True,
            cashed_out=False
        )
    
    print(f"✅ Created game {game.id} with {len(players)} players")
    return game, users, players


def test_cash_out_game_summary():
    """Test the cash out endpoint and game summary generation."""
    print("💰 Testing cash out and game summary functionality...")
    
    # Create test game
    game, users, players = create_test_game_with_players()
    
    # Create API client
    client = APIClient()
    
    # Mock the broadcast functions to capture their calls
    with patch('poker_api.services.game_service.GameService.broadcast_game_update') as mock_broadcast_update, \
         patch('poker_api.services.game_service.GameService.broadcast_game_summary_available') as mock_broadcast_summary:
        
        # Test Case 1: Cash out first player (should not trigger game summary)
        print("\n🔍 Test Case 1: Cash out first player...")
        
        refresh = RefreshToken.for_user(users[0])
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = client.post(f'/api/games/{game.id}/cash_out/', HTTP_HOST='localhost')
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.data['success'] == True
        assert response.data['game_summary_generated'] == False
        assert 'game_summary' not in response.data
        
        # Should call regular broadcast update, not summary broadcast
        mock_broadcast_update.assert_called_once_with(game.id)
        mock_broadcast_summary.assert_not_called()
        
        print("✅ First player cash out test passed")
        
        # Reset mocks
        mock_broadcast_update.reset_mock()
        mock_broadcast_summary.reset_mock()
        
        # Test Case 2: Cash out second player (should not trigger game summary)
        print("\n🔍 Test Case 2: Cash out second player...")
        
        refresh = RefreshToken.for_user(users[1])
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = client.post(f'/api/games/{game.id}/cash_out/', HTTP_HOST='localhost')
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.data['success'] == True
        assert response.data['game_summary_generated'] == False
        assert 'game_summary' not in response.data
        
        # Should call regular broadcast update, not summary broadcast
        mock_broadcast_update.assert_called_once_with(game.id)
        mock_broadcast_summary.assert_not_called()
        
        print("✅ Second player cash out test passed")
        
        # Reset mocks
        mock_broadcast_update.reset_mock()
        mock_broadcast_summary.reset_mock()
        
        # Test Case 3: Cash out last player (should trigger game summary)
        print("\n🔍 Test Case 3: Cash out last player (should trigger game summary)...")
        
        refresh = RefreshToken.for_user(users[2])
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = client.post(f'/api/games/{game.id}/cash_out/', HTTP_HOST='localhost')
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.data['success'] == True
        assert response.data['game_summary_generated'] == True
        assert 'game_summary' in response.data
        assert 'Game summary has been generated' in response.data['message']
        
        # Should call summary broadcast, not regular update
        mock_broadcast_update.assert_not_called()
        mock_broadcast_summary.assert_called_once()
        
        # Check the broadcast call arguments
        call_args = mock_broadcast_summary.call_args
        assert call_args[0][0] == game.id  # game_id
        summary_data = call_args[0][1]  # summary_data
        assert 'game_id' in summary_data
        assert 'players' in summary_data
        assert len(summary_data['players']) == 3
        
        print("✅ Last player cash out and game summary test passed")
        
        # Test Case 4: Verify game summary structure
        print("\n🔍 Test Case 4: Verify game summary structure...")
        
        game_summary = response.data['game_summary']
        print(f"Game summary: {json.dumps(game_summary, indent=2)}")
        
        # Check required fields
        assert 'game_id' in game_summary
        assert 'table_name' in game_summary
        assert 'completed_at' in game_summary
        assert 'total_hands' in game_summary
        assert 'players' in game_summary
        
        # Check players data
        assert len(game_summary['players']) == 3
        for player_data in game_summary['players']:
            assert 'player_name' in player_data
            assert 'player_id' in player_data
            assert 'starting_stack' in player_data
            assert 'final_stack' in player_data
            assert 'win_loss' in player_data
            assert 'status' in player_data
            assert player_data['status'] == 'CASHED_OUT'
        
        print("✅ Game summary structure test passed")
        
        # Test Case 5: Verify game status
        print("\n🔍 Test Case 5: Verify game status...")
        
        game.refresh_from_db()
        assert game.status == 'FINISHED', f"Expected game status FINISHED, got {game.status}"
        assert game.get_game_summary() is not None, "Game summary should be stored in the database"
        
        print("✅ Game status verification test passed")
        
        # Test Case 6: Test trying to cash out again (should fail)
        print("\n🔍 Test Case 6: Test double cash out (should fail)...")
        
        response = client.post(f'/api/games/{game.id}/cash_out/', HTTP_HOST='localhost')
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert 'already cashed out' in response.data['error']
        
        print("✅ Double cash out prevention test passed")
    
    print("\n🎉 All cash out and game summary tests passed!")
    return True


def test_game_summary_endpoint():
    """Test the game summary endpoint after all players have cashed out."""
    print("\n📊 Testing game summary endpoint...")
    
    # Get the game from previous test
    game = Game.objects.filter(status='FINISHED').last()
    if not game:
        print("❌ No finished game found. Run cash out test first.")
        return False
    
    # Get a user who participated in the game
    player_game = PlayerGame.objects.filter(game=game).first()
    if not player_game:
        print("❌ No player found for game.")
        return False
    
    user = player_game.player.user
    
    # Create API client
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    # Test the summary endpoint
    response = client.get(f'/api/games/{game.id}/summary/', HTTP_HOST='localhost')
    print(f"Summary endpoint response status: {response.status_code}")
    print(f"Summary endpoint response data: {response.data}")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert 'game_summary' in response.data
    assert 'game_status' in response.data
    assert response.data['game_status'] == 'FINISHED'
    
    print("✅ Game summary endpoint test passed")
    return True


if __name__ == '__main__':
    try:
        success = test_cash_out_game_summary()
        if success:
            success = test_game_summary_endpoint()
        
        if success:
            print("\n🎉 All tests passed successfully!")
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)