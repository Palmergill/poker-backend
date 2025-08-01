#!/usr/bin/env python3
"""
Test script to check edge cases in betting round progression,
including scenarios with folding players.
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


def test_edge_cases():
    """Test edge cases that might cause premature phase advancement."""
    print("🃏 Testing edge cases in betting round progression...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_edge').delete()
    PokerTable.objects.filter(name='Test Edge Cases').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(4):  # Use 4 players for more complex scenarios
        user = User.objects.create_user(
            username=f'test_edge_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Edge Cases',
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
    print(f"   Current player: {game.current_player.user.username}")
    print(f"   Current bet: ${game.current_bet}")
    
    # Show all players initial state
    player_games = PlayerGame.objects.filter(game=game).order_by('seat_position')
    print(f"\n📊 Initial player states:")
    for pg in player_games:
        print(f"   {pg.player.user.username} (Seat {pg.seat_position}): "
              f"Stack=${pg.stack}, Current bet=${pg.current_bet}, Active={pg.is_active}")
    
    # Test Case 1: One player folds immediately
    print(f"\n🎯 Test Case 1: Player folds, then others check")
    
    # First player folds
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    
    print(f"\n1️⃣ Player {current_player_name} folds...")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"   After fold - Phase: {game.phase}, Current player: {game.current_player.user.username}")
    
    # Check active players count
    active_players = PlayerGame.objects.filter(game=game, is_active=True)
    print(f"   Active players: {active_players.count()}")
    for pg in active_players:
        print(f"     - {pg.player.user.username} (${pg.current_bet} bet)")
    
    # Continue with remaining players
    actions_taken = 1  # Already did one fold
    max_actions = 10
    initial_phase = game.phase
    
    while game.phase == initial_phase and actions_taken < max_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        
        # Get player's current state
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        
        # Determine action based on current bet
        if pg.current_bet < game.current_bet:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} calls ${game.current_bet}...")
            GameService.process_action(game.id, current_player_id, 'CALL')
        else:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} checks...")
            GameService.process_action(game.id, current_player_id, 'CHECK')
            
        game.refresh_from_db()
        actions_taken += 1
        
        print(f"   After action - Phase: {game.phase}")
        if game.phase != initial_phase:
            print(f"   🔄 Advanced to {game.phase}")
            break
        else:
            print(f"   Current player: {game.current_player.user.username}")
        
        # Show actions this phase
        actions = GameAction.objects.filter(
            player_game__game=game,
            phase=initial_phase
        ).order_by('timestamp')
        
        print(f"   Total actions this phase: {actions.count()}")
        active_players_with_actions = set()
        for action in actions:
            active_players_with_actions.add(action.player_game.player.user.username)
            print(f"     - {action.player_game.player.user.username}: {action.action_type}")
        
        # Check logic manually
        active_count = PlayerGame.objects.filter(game=game, is_active=True).count()
        actions_count = actions.count()
        unique_actors = len(active_players_with_actions)
        
        print(f"   Analysis: {active_count} active players, {actions_count} total actions, {unique_actors} unique actors")
        
        # Early detection of potential issue
        if game.phase != initial_phase:
            if unique_actors < active_count:
                print(f"❌ POTENTIAL BUG: Phase advanced with only {unique_actors} unique actors out of {active_count} active players")
                
                # Show which players haven't acted
                all_active = set(pg.player.user.username for pg in 
                               PlayerGame.objects.filter(game=game, is_active=True))
                missing_actors = all_active - active_players_with_actions
                if missing_actors:
                    print(f"   Players who haven't acted: {', '.join(missing_actors)}")
                return False
            else:
                print(f"✅ Correct: All {active_count} active players acted")
    
    return True


if __name__ == '__main__':
    try:
        success = test_edge_cases()
        if success:
            print("\n✅ Test completed successfully")
        else:
            print("\n❌ Test found issues")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()