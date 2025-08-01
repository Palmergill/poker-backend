#!/usr/bin/env python3
"""
Test script to reproduce the betting round issue where checking 
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


def test_betting_round_issue():
    """Test the betting round progression with multiple players checking."""
    print("🃏 Testing betting round progression...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_player').delete()
    PokerTable.objects.filter(name='Test Betting Round').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_player_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Betting Round',
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
    print(f"   Phase: {game.phase}")
    print(f"   Current bet: ${game.current_bet}")
    print(f"   Current player: {game.current_player.user.username}")
    print(f"   Pot: ${game.pot}")
    
    # Show initial player states
    player_games = PlayerGame.objects.filter(game=game).order_by('seat_position')
    print("\n📊 Initial player states after blinds:")
    for pg in player_games:
        print(f"   {pg.player.user.username} (Seat {pg.seat_position}): "
              f"Stack=${pg.stack}, Current bet=${pg.current_bet}, Active={pg.is_active}")
    
    # Test the betting round progression
    print(f"\n🎯 Testing betting round progression...")
    
    # Store initial state
    initial_phase = game.phase
    initial_current_player = game.current_player.user.username
    
    # Player 1 checks (first action after blinds)
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    
    # In preflop, first player must call the big blind, not check
    if game.current_bet > 0:
        print(f"\n1️⃣ Player {current_player_name} calls ${game.current_bet}...")
        GameService.process_action(game.id, current_player_id, 'CALL')
    else:
        print(f"\n1️⃣ Player {current_player_name} checks...")
        GameService.process_action(game.id, current_player_id, 'CHECK')
        
    game.refresh_from_db()
    
    print(f"   After action - Phase: {game.phase}, Current player: {game.current_player.user.username}")
    
    # Check if phase advanced prematurely
    if game.phase != initial_phase:
        print(f"❌ BUG FOUND: Phase advanced from {initial_phase} to {game.phase} after only one player acted!")
        print(f"   Expected: Phase should remain {initial_phase} until all players have acted")
        return False
    
    # Continue with remaining players
    actions_taken = 1
    max_actions = 10  # Safety limit
    
    while game.phase == initial_phase and actions_taken < max_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        
        # Determine appropriate action based on current bet
        if game.current_bet > 0:
            # Get player's current bet to see if they need to call
            pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
            if pg.current_bet < game.current_bet:
                print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} calls ${game.current_bet}...")
                GameService.process_action(game.id, current_player_id, 'CALL')
            else:
                print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} checks...")
                GameService.process_action(game.id, current_player_id, 'CHECK')
        else:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} checks...")
            GameService.process_action(game.id, current_player_id, 'CHECK')
            
        game.refresh_from_db()
        
        print(f"   After action - Phase: {game.phase}, Current player: {game.current_player.user.username}")
        actions_taken += 1
        
        # Show all actions so far
        actions = GameAction.objects.filter(
            player_game__game=game,
            phase=initial_phase
        ).order_by('timestamp')
        
        print(f"   Actions taken this phase: {actions.count()}")
        for action in actions:
            print(f"     - {action.player_game.player.user.username}: {action.action_type}")
    
    if game.phase != initial_phase:
        print(f"\n✅ Phase advanced from {initial_phase} to {game.phase} after {actions_taken} actions")
        
        # Check if this was correct (all players should have acted)
        active_player_count = PlayerGame.objects.filter(game=game, is_active=True).count()
        actions_count = GameAction.objects.filter(
            player_game__game=game,
            player_game__is_active=True,
            phase=initial_phase
        ).count()
        
        print(f"   Active players: {active_player_count}")
        print(f"   Total actions taken: {actions_count}")
        
        if actions_count >= active_player_count:
            print("✅ Correct: All players had a chance to act")
            return True
        else:
            print("❌ BUG: Phase advanced before all players acted!")
            return False
    else:
        print(f"\n⚠️  Phase didn't advance after {actions_taken} actions (might be stuck)")
        return False


if __name__ == '__main__':
    try:
        success = test_betting_round_issue()
        if success:
            print("\n✅ Test completed successfully")
        else:
            print("\n❌ Test found issues")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()