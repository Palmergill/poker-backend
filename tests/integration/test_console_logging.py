#!/usr/bin/env python3
"""
Test script to verify console logging for hand history after each hand.
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


def test_console_logging():
    """Test that hand history is logged to console after each hand."""
    print("🃏 Testing console logging for hand history...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_console').delete()
    PokerTable.objects.filter(name='Test Console Logging').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_console_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Console Logging',
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
    print("📋 Initial game state:")
    print(f"   Phase: {game.phase}")
    print(f"   Current bet: ${game.current_bet}")
    print(f"   Current player: {game.current_player.user.username}")
    print(f"   Pot: ${game.pot}")
    
    # Test 1: Complete a hand by folding (should trigger console logging)
    print(f"\n🎯 Test 1: Completing hand by folding (should see console log)")
    print("-" * 50)
    
    # First player folds
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds...")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    # Second player folds (this should end the hand and trigger logging)
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds (hand should complete)...")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"✅ First hand completed! Game hand count: {game.hand_count}")
    
    # Test 2: Complete another hand (should trigger more console logging)
    print(f"\n🎯 Test 2: Completing second hand (should see another console log)")
    print("-" * 50)
    
    # Play some actions then complete the hand
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
    
    # Player calls
    if pg.current_bet < game.current_bet:
        print(f"   {current_player_name} calls ${game.current_bet}...")
        GameService.process_action(game.id, current_player_id, 'CALL')
        game.refresh_from_db()
    
    # Next player checks
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} checks...")
    GameService.process_action(game.id, current_player_id, 'CHECK')
    game.refresh_from_db()
    
    # Last player folds to end the hand
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    print(f"   {current_player_name} folds to end hand...")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"✅ Second hand completed! Game hand count: {game.hand_count}")
    
    # Verify hand histories were created
    hand_histories = HandHistory.objects.filter(game=game).order_by('hand_number')
    print(f"\n📊 Summary:")
    print(f"   Total hands completed: {hand_histories.count()}")
    print(f"   Game hand count: {game.hand_count}")
    
    for hh in hand_histories:
        winner_info = hh.get_winner_info()
        winner_name = winner_info['winners'][0]['player_name'] if winner_info and 'winners' in winner_info else 'Unknown'
        print(f"   Hand #{hh.hand_number}: Winner: {winner_name}, Pot: ${hh.pot_amount}")
    
    print(f"\n✅ Console logging test completed!")
    print(f"   Look above for the detailed hand history logs with emojis and formatting.")
    return True


if __name__ == '__main__':
    try:
        success = test_console_logging()
        if success:
            print("\n✅ Console logging test successful")
        else:
            print("\n❌ Console logging test failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()