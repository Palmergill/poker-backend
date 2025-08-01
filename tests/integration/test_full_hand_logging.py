#!/usr/bin/env python3
"""
Test script to show console logging for a complete hand that goes to showdown.
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


def test_full_hand_logging():
    """Test console logging for a hand that goes through multiple phases."""
    print("🃏 Testing console logging for a full hand...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_full').delete()
    PokerTable.objects.filter(name='Test Full Hand').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_full_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Full Hand',
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
    
    # Play through multiple phases to get community cards
    print(f"\n🎯 Playing through multiple phases to show full hand logging...")
    print("-" * 60)
    
    phase_count = 0
    max_phases = 4  # PREFLOP, FLOP, TURN, RIVER
    max_actions = 20  # Safety limit
    actions_taken = 0
    
    while game.status == 'PLAYING' and game.hand_count == 0 and actions_taken < max_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        
        print(f"   Phase: {game.phase} | {current_player_name}'s turn")
        
        # Strategy: First few actions call/check, then someone folds to end hand
        if actions_taken < 8:  # Play through a few phases
            if pg.current_bet < game.current_bet:
                print(f"     {current_player_name} calls ${game.current_bet}")
                GameService.process_action(game.id, current_player_id, 'CALL')
            else:
                print(f"     {current_player_name} checks")
                GameService.process_action(game.id, current_player_id, 'CHECK')
        else:
            # End the hand by having someone fold
            print(f"     {current_player_name} folds to end hand")
            GameService.process_action(game.id, current_player_id, 'FOLD')
        
        game.refresh_from_db()
        actions_taken += 1
        
        # Check if hand completed
        if game.hand_count > 0:
            print(f"✅ Hand completed after {actions_taken} actions!")
            break
        
        # Check if we reached a new phase
        if hasattr(test_full_hand_logging, 'last_phase'):
            if game.phase != test_full_hand_logging.last_phase:
                phase_count += 1
                print(f"     ➡️  Advanced to {game.phase} phase")
        test_full_hand_logging.last_phase = game.phase
        
        # Show community cards if available
        if game.community_cards:
            community = game.get_community_cards()
            print(f"     🎴 Community cards: {', '.join(community)}")
    
    # Show final results
    hand_histories = HandHistory.objects.filter(game=game)
    if hand_histories.exists():
        hh = hand_histories.first()
        print(f"\n📊 Hand Summary:")
        print(f"   Hand went through {phase_count} phase transitions")
        print(f"   Final phase: {hh.final_phase}")
        print(f"   Total actions: {len(hh.get_actions())}")
        if hh.get_community_cards():
            print(f"   Community cards were dealt: {', '.join(hh.get_community_cards())}")
    
    return True


if __name__ == '__main__':
    try:
        success = test_full_hand_logging()
        if success:
            print("\n✅ Full hand logging test successful")
            print("   Check the detailed console log above with community cards and all actions!")
        else:
            print("\n❌ Full hand logging test failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()