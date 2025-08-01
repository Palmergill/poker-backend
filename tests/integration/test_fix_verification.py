#!/usr/bin/env python3
"""
Test script to verify that the betting round fix is working correctly.
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


def test_fix_verification():
    """Test that the betting round fix properly filters actions by hand."""
    print("🃏 Testing betting round fix verification...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_fix').delete()
    PokerTable.objects.filter(name='Test Fix').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_fix_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Fix',
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
    
    # Complete first hand quickly (2 players fold)
    print(f"\n🔄 Completing FIRST HAND...")
    
    # First player folds
    current_player_id = game.current_player.id
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    # Second player folds (this should end the hand and start a new one)
    current_player_id = game.current_player.id
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"✅ First hand completed, now in hand #{game.hand_count}")
    
    # Now test the specific fix by manually checking the filtering logic
    print(f"\n🔍 TESTING THE FIX:")
    
    # Get the current hand start time (using the same logic as the fix)
    last_hand_history = HandHistory.objects.filter(game=game).order_by('-completed_at').first()
    current_hand_start = last_hand_history.completed_at if last_hand_history else game.created_at
    
    print(f"   Current hand start time: {current_hand_start}")
    print(f"   Last hand history: {last_hand_history.hand_number if last_hand_history else 'None'}")
    
    # Check actions from previous hand vs current hand
    all_actions_any_time = GameAction.objects.filter(
        player_game__game=game,
        phase='PREFLOP'
    ).order_by('timestamp')
    
    current_hand_actions = GameAction.objects.filter(
        player_game__game=game,
        phase='PREFLOP',
        timestamp__gt=current_hand_start
    ).order_by('timestamp')
    
    print(f"\n📊 Action Analysis:")
    print(f"   All PREFLOP actions (any time): {all_actions_any_time.count()}")
    for action in all_actions_any_time:
        print(f"     - {action.player_game.player.user.username}: {action.action_type} at {action.timestamp}")
    
    print(f"\n   Current hand PREFLOP actions only: {current_hand_actions.count()}")
    for action in current_hand_actions:
        print(f"     - {action.player_game.player.user.username}: {action.action_type} at {action.timestamp}")
    
    # Now take one action in the second hand and see what happens
    print(f"\n🎯 Taking one action in second hand...")
    
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
    
    print(f"   Current player: {current_player_name}")
    print(f"   Player's current bet: ${pg.current_bet}")
    print(f"   Game's current bet: ${game.current_bet}")
    
    # Take appropriate action
    if pg.current_bet < game.current_bet:
        print(f"   {current_player_name} calls ${game.current_bet}...")
        GameService.process_action(game.id, current_player_id, 'CALL')
    else:
        print(f"   {current_player_name} checks...")
        GameService.process_action(game.id, current_player_id, 'CHECK')
    
    game.refresh_from_db()
    
    # Check if the phase advanced prematurely
    if game.phase != 'PREFLOP':
        print(f"\n❌ BUG STILL EXISTS: Phase advanced to {game.phase} after only one action!")
        
        # Check what actions were considered
        actions_considered = GameAction.objects.filter(
            player_game__game=game,
            phase='PREFLOP',
            timestamp__gt=current_hand_start
        ).order_by('timestamp')
        
        print(f"   Actions considered by fixed logic:")
        for action in actions_considered:
            print(f"     - {action.player_game.player.user.username}: {action.action_type}")
        
        return False
    else:
        print(f"   ✅ Phase stayed in PREFLOP - fix is working!")
        
        # Show current state
        actions_after_one = GameAction.objects.filter(
            player_game__game=game,
            phase='PREFLOP',
            timestamp__gt=current_hand_start
        ).order_by('timestamp')
        
        print(f"   Actions in current hand after one action:")
        for action in actions_after_one:
            print(f"     - {action.player_game.player.user.username}: {action.action_type}")
        
        return True


if __name__ == '__main__':
    try:
        success = test_fix_verification()
        if success:
            print("\n✅ Fix verification successful")
        else:
            print("\n❌ Fix verification failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()