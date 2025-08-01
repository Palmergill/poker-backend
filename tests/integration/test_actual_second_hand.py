#!/usr/bin/env python3
"""
Test script to properly play through a complete first hand and then 
test the second hand for the betting round issue.
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


def test_actual_second_hand():
    """Test the second hand issue by playing a complete first hand."""
    print("🃏 Testing actual second hand issue...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_real').delete()
    PokerTable.objects.filter(name='Test Real Second').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_real_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Real Second',
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
    
    print(f"✅ Started game {game.id} - Hand #{game.hand_count}")
    
    # Complete the first hand by having two players fold (leaving only 1)
    print(f"\n🔄 Completing FIRST HAND quickly...")
    
    # First player folds
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    
    print(f"   {current_player_name} folds...")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    # Second player folds (this should end the hand)
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    
    print(f"   {current_player_name} folds to end first hand...")
    GameService.process_action(game.id, current_player_id, 'FOLD')
    game.refresh_from_db()
    
    print(f"   After folds - Hand count: {game.hand_count}, Phase: {game.phase}")
    
    # Check if we're now in a new hand
    if game.hand_count <= 0:
        print("❌ Hand count didn't increment - hand didn't properly end")
        return False
    
    print(f"✅ Now in SECOND HAND (Hand #{game.hand_count})")
    
    # Show the state at the start of the second hand
    print(f"\n📊 SECOND HAND initial state:")
    print(f"   Phase: {game.phase}")
    print(f"   Current bet: ${game.current_bet}")
    print(f"   Current player: {game.current_player.user.username}")
    print(f"   Pot: ${game.pot}")
    
    # Show all player states
    player_games = PlayerGame.objects.filter(game=game, is_active=True).order_by('seat_position')
    for pg in player_games:
        blind_type = ""
        if pg.current_bet == game.table.small_blind:
            blind_type = " (Small Blind)"
        elif pg.current_bet == game.table.big_blind:
            blind_type = " (Big Blind)"
        print(f"   {pg.player.user.username} (Seat {pg.seat_position}): "
              f"Stack=${pg.stack}, Bet=${pg.current_bet}{blind_type}")
    
    # Now test the specific bug in the second hand
    print(f"\n🎯 TESTING SECOND HAND BUG:")
    print(f"   Issue: When one player checks, it might skip other players")
    
    initial_phase = game.phase
    active_count = PlayerGame.objects.filter(game=game, is_active=True).count()
    
    # Track each action in detail
    for action_num in range(1, active_count + 2):  # +2 to account for potential extra actions
        if game.phase != initial_phase:
            print(f"   Phase changed to {game.phase}")
            break
            
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        
        # Determine the correct action
        if pg.current_bet < game.current_bet:
            action_type = 'CALL'
            print(f"\n{action_num}️⃣ Player {current_player_name} calls ${game.current_bet}...")
            GameService.process_action(game.id, current_player_id, 'CALL')
        else:
            action_type = 'CHECK'
            print(f"\n{action_num}️⃣ Player {current_player_name} checks...")
            GameService.process_action(game.id, current_player_id, 'CHECK')
        
        game.refresh_from_db()
        
        print(f"   After {action_type}:")
        print(f"     Phase: {game.phase}")
        
        if game.phase == initial_phase:
            print(f"     Next player: {game.current_player.user.username}")
        else:
            print(f"     🔄 Advanced to {game.phase}")
        
        # Analyze the actions taken so far
        actions = GameAction.objects.filter(
            player_game__game=game,
            phase=initial_phase
        ).order_by('timestamp')
        
        unique_actors = set()
        print(f"     Actions this phase ({actions.count()} total):")
        for action in actions:
            unique_actors.add(action.player_game.player.user.username)
            print(f"       - {action.player_game.player.user.username}: {action.action_type}")
        
        # Check for premature advancement
        if game.phase != initial_phase:
            if len(unique_actors) < active_count:
                print(f"\n❌ BUG FOUND!")
                print(f"   Phase advanced after only {len(unique_actors)} unique players acted")
                print(f"   Expected: All {active_count} players should act")
                
                all_active_players = set(pg.player.user.username for pg in 
                                       PlayerGame.objects.filter(game=game, is_active=True))
                missing_players = all_active_players - unique_actors
                print(f"   Players who didn't get to act: {missing_players}")
                return False
            else:
                print(f"   ✅ All {active_count} players acted before phase advanced")
                break
        
        if action_num >= 10:  # Safety break
            print("   ⚠️ Too many actions, breaking")
            break
    
    return True


if __name__ == '__main__':
    try:
        success = test_actual_second_hand()
        if success:
            print("\n✅ Test completed successfully - no betting round bug found")
        else:
            print("\n❌ Test found the betting round bug")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()