#!/usr/bin/env python3
"""
Test script to reproduce the issue where checking in post-flop phases
advances to next phase before all players have acted.
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
from poker_api.models import Player, PokerTable, Game, PlayerGame, GameAction
from poker_api.services.game_service import GameService


def test_flop_checking_issue():
    """Test the checking issue in post-flop phases (no betting, just checking)."""
    print("🃏 Testing post-flop checking progression...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_flop').delete()
    PokerTable.objects.filter(name='Test Flop Checking').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_flop_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Flop Checking',
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
    
    print(f"✅ Started game {game.id} in {game.phase} phase")
    
    # Quickly get to the flop by having everyone call preflop
    print("\n🔄 Getting through preflop...")
    max_preflop_actions = 10
    preflop_actions = 0
    
    while game.phase == 'PREFLOP' and preflop_actions < max_preflop_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        
        # Get player's current bet to see if they need to call
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        if pg.current_bet < game.current_bet:
            print(f"   {current_player_name} calls ${game.current_bet}")
            GameService.process_action(game.id, current_player_id, 'CALL')
        else:
            print(f"   {current_player_name} checks")
            GameService.process_action(game.id, current_player_id, 'CHECK')
            
        game.refresh_from_db()
        preflop_actions += 1
        
        if game.phase != 'PREFLOP':
            print(f"✅ Advanced to {game.phase} phase")
            break
    
    if game.phase == 'PREFLOP':
        print("❌ Failed to advance past preflop")
        return False
    
    # Now test the flop phase checking issue
    print(f"\n🎯 Testing {game.phase} phase checking...")
    print(f"   Current bet: ${game.current_bet}")
    print(f"   Current player: {game.current_player.user.username}")
    
    # Show current player states
    player_games = PlayerGame.objects.filter(game=game, is_active=True).order_by('seat_position')
    print(f"\n📊 Player states in {game.phase}:")
    for pg in player_games:
        print(f"   {pg.player.user.username} (Seat {pg.seat_position}): "
              f"Stack=${pg.stack}, Current bet=${pg.current_bet}")
    
    # Store initial state
    initial_phase = game.phase
    actions_taken = 0
    max_actions = 10
    
    print(f"\n🔄 Starting {initial_phase} betting round...")
    
    # Test checking progression
    while game.phase == initial_phase and actions_taken < max_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        
        print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} checks...")
        GameService.process_action(game.id, current_player_id, 'CHECK')
        game.refresh_from_db()
        
        print(f"   After check - Phase: {game.phase}")
        if game.phase != initial_phase:
            print(f"   🔄 Advanced to {game.phase}")
        else:
            print(f"   Current player: {game.current_player.user.username}")
        
        actions_taken += 1
        
        # Show all actions so far this phase
        actions = GameAction.objects.filter(
            player_game__game=game,
            phase=initial_phase
        ).order_by('timestamp')
        
        print(f"   Actions this phase: {actions.count()}")
        for action in actions:
            print(f"     - {action.player_game.player.user.username}: {action.action_type}")
        
        # Check if phase advanced prematurely
        if game.phase != initial_phase:
            active_player_count = PlayerGame.objects.filter(game=game, is_active=True).count()
            actions_count = actions.count()
            
            print(f"\n📊 Phase Analysis:")
            print(f"   Active players: {active_player_count}")
            print(f"   Actions taken: {actions_count}")
            
            if actions_count < active_player_count:
                print(f"❌ BUG FOUND: Phase advanced after only {actions_count} actions")
                print(f"   Expected: Should wait for all {active_player_count} players to act")
                return False
            else:
                print(f"✅ Correct: All {active_player_count} players acted before phase advanced")
                return True
    
    if game.phase == initial_phase:
        print(f"\n⚠️  Phase didn't advance after {actions_taken} actions (might be stuck)")
        return False
    
    return True


if __name__ == '__main__':
    try:
        success = test_flop_checking_issue()
        if success:
            print("\n✅ Test completed successfully")
        else:
            print("\n❌ Test found issues")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()