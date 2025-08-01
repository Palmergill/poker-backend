#!/usr/bin/env python3
"""
Test script to reproduce the issue in the SECOND hand where 
checking causes premature phase advancement.
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


def test_second_hand_issue():
    """Test betting round progression in the second hand specifically."""
    print("🃏 Testing SECOND hand betting round progression...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_2nd').delete()
    PokerTable.objects.filter(name='Test Second Hand').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_2nd_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Second Hand',
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
    
    print(f"✅ Started game {game.id} - FIRST HAND")
    print(f"   Phase: {game.phase}, Hand: {game.hand_count}")
    
    # Play through the first hand quickly (everyone calls to showdown)
    print(f"\n🔄 Playing through FIRST HAND...")
    
    max_actions = 20
    actions_taken = 0
    
    while game.status == 'PLAYING' and game.hand_count == 1 and actions_taken < max_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        
        # Get player's current state
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        
        # Just call/check through all phases
        if pg.current_bet < game.current_bet:
            print(f"   {current_player_name} calls ${game.current_bet}")
            GameService.process_action(game.id, current_player_id, 'CALL')
        else:
            print(f"   {current_player_name} checks")
            GameService.process_action(game.id, current_player_id, 'CHECK')
            
        game.refresh_from_db()
        actions_taken += 1
        
        if game.hand_count > 1:
            print(f"✅ First hand completed, now on hand {game.hand_count}")
            break
    
    if game.hand_count == 1:
        print("❌ Failed to complete first hand")
        return False
    
    # Now test the SECOND hand specifically
    print(f"\n🎯 Testing SECOND HAND (Hand #{game.hand_count})")
    print(f"   Phase: {game.phase}")
    print(f"   Current bet: ${game.current_bet}")
    print(f"   Current player: {game.current_player.user.username}")
    
    # Show player states at start of second hand
    player_games = PlayerGame.objects.filter(game=game, is_active=True).order_by('seat_position')
    print(f"\n📊 Player states at start of second hand:")
    for pg in player_games:
        blind_type = ""
        if pg.current_bet == game.table.small_blind:
            blind_type = " (Small Blind)"
        elif pg.current_bet == game.table.big_blind:
            blind_type = " (Big Blind)"
        print(f"   {pg.player.user.username} (Seat {pg.seat_position}): "
              f"Stack=${pg.stack}, Bet=${pg.current_bet}{blind_type}")
    
    # Test the specific issue: first player checks, does it skip others?
    print(f"\n🎯 TESTING THE BUG: First player action in second hand...")
    
    initial_phase = game.phase
    initial_current_player = game.current_player.user.username
    
    # Store the active player count before the action
    active_count_before = PlayerGame.objects.filter(game=game, is_active=True).count()
    
    # First player action
    current_player_id = game.current_player.id
    current_player_name = game.current_player.user.username
    pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
    
    if pg.current_bet < game.current_bet:
        action = 'CALL'
        print(f"\n1️⃣ Player {current_player_name} calls ${game.current_bet}...")
        GameService.process_action(game.id, current_player_id, 'CALL')
    else:
        action = 'CHECK'
        print(f"\n1️⃣ Player {current_player_name} checks...")
        GameService.process_action(game.id, current_player_id, 'CHECK')
    
    game.refresh_from_db()
    
    print(f"   After {action}:")
    print(f"     Phase: {game.phase}")
    print(f"     Current player: {game.current_player.user.username}")
    
    # Check if phase advanced prematurely
    if game.phase != initial_phase:
        print(f"❌ BUG FOUND: Phase advanced from {initial_phase} to {game.phase} after only ONE action!")
        print(f"   Expected: Should stay in {initial_phase} until all {active_count_before} players act")
        
        # Show the actions taken
        actions = GameAction.objects.filter(
            player_game__game=game,
            phase=initial_phase
        ).order_by('timestamp')
        
        print(f"\n   Actions taken in {initial_phase}:")
        for i, action_obj in enumerate(actions):
            print(f"     {i+1}. {action_obj.player_game.player.user.username}: {action_obj.action_type}")
        
        return False
    
    # Continue testing with remaining players
    print(f"   ✅ Phase stayed in {initial_phase}, continuing...")
    
    actions_taken = 1
    while game.phase == initial_phase and actions_taken < 10:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        
        if pg.current_bet < game.current_bet:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} calls ${game.current_bet}...")
            GameService.process_action(game.id, current_player_id, 'CALL')
        else:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} checks...")
            GameService.process_action(game.id, current_player_id, 'CHECK')
            
        game.refresh_from_db()
        actions_taken += 1
        
        if game.phase != initial_phase:
            print(f"   ✅ Phase advanced to {game.phase} after {actions_taken} actions")
            break
        else:
            print(f"   Current player: {game.current_player.user.username}")
    
    # Final analysis
    actions = GameAction.objects.filter(
        player_game__game=game,
        phase=initial_phase
    ).order_by('timestamp')
    
    print(f"\n📊 Final analysis of {initial_phase} phase:")
    print(f"   Total actions: {actions.count()}")
    print(f"   Active players: {active_count_before}")
    
    if actions.count() >= active_count_before:
        print(f"✅ Correct: All players got to act")
        return True
    else:
        print(f"❌ BUG: Only {actions.count()} actions for {active_count_before} players")
        return False


if __name__ == '__main__':
    try:
        success = test_second_hand_issue()
        if success:
            print("\n✅ Test completed successfully")
        else:
            print("\n❌ Test found issues in second hand")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()