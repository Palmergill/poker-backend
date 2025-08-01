#!/usr/bin/env python3
"""
Test script to verify the complete multi-hand game flow works correctly
with the betting round fix.
"""

import os
import sys
import django
from decimal import Decimal
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()

from django.contrib.auth.models import User
from poker_api.models import Player, PokerTable, Game, PlayerGame, GameAction, HandHistory
from poker_api.services.game_service import GameService


def test_complete_flow():
    """Test complete multi-hand game flow with proper betting rounds."""
    print("🃏 Testing complete multi-hand game flow...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_flow').delete()
    PokerTable.objects.filter(name='Test Complete Flow').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_flow_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Complete Flow',
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
    
    # Test multiple hands
    for hand_num in range(1, 4):  # Test 3 hands
        print(f"\n🎲 TESTING HAND #{hand_num}")
        print(f"   Current game hand count: {game.hand_count}")
        print(f"   Phase: {game.phase}")
        
        if hand_num == 1:
            # First hand - end it quickly with folds
            print("   Ending first hand quickly with folds...")
            
            # Have 2 players fold to end the hand
            for fold_count in range(2):
                current_player_id = game.current_player.id
                current_player_name = game.current_player.user.username
                print(f"     {current_player_name} folds")
                GameService.process_action(game.id, current_player_id, 'FOLD')
                game.refresh_from_db()
                
                if game.hand_count > 0:
                    print(f"   ✅ Hand ended, now in hand #{game.hand_count}")
                    break
        
        else:
            # Subsequent hands - test proper betting round progression
            print(f"   Testing betting round progression in hand #{hand_num}...")
            
            # Count active players
            active_players = PlayerGame.objects.filter(game=game, is_active=True)
            active_count = active_players.count()
            print(f"   Active players: {active_count}")
            
            # Show player states
            for pg in active_players:
                blind_type = ""
                if pg.current_bet == game.table.small_blind:
                    blind_type = " (SB)"
                elif pg.current_bet == game.table.big_blind:
                    blind_type = " (BB)"
                print(f"     {pg.player.user.username}: ${pg.current_bet}{blind_type}")
            
            # Test each player action
            actions_in_phase = 0
            max_actions = 10
            initial_phase = game.phase
            
            while game.phase == initial_phase and actions_in_phase < max_actions:
                current_player_id = game.current_player.id
                current_player_name = game.current_player.user.username
                pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
                
                # Determine action
                if pg.current_bet < game.current_bet:
                    action = 'CALL'
                    print(f"     {current_player_name} calls ${game.current_bet}")
                    GameService.process_action(game.id, current_player_id, 'CALL')
                else:
                    action = 'CHECK'
                    print(f"     {current_player_name} checks")
                    GameService.process_action(game.id, current_player_id, 'CHECK')
                
                game.refresh_from_db()
                actions_in_phase += 1
                
                if game.phase != initial_phase:
                    print(f"     ✅ Phase advanced to {game.phase} after {actions_in_phase} actions")
                    break
                else:
                    print(f"     Next player: {game.current_player.user.username}")
            
            # Verify all players got to act
            if game.phase != initial_phase:
                if actions_in_phase >= active_count:
                    print(f"     ✅ Correct: All {active_count} players acted before phase advanced")
                else:
                    print(f"     ❌ BUG: Only {actions_in_phase} actions for {active_count} players")
                    return False
            
            # End this hand quickly if it didn't advance naturally
            if game.phase == initial_phase:
                print("     Ending hand with folds...")
                for fold_count in range(2):
                    current_player_id = game.current_player.id
                    GameService.process_action(game.id, current_player_id, 'FOLD')
                    game.refresh_from_db()
                    if game.hand_count >= hand_num:
                        break
    
    print(f"\n📊 Final Results:")
    print(f"   Final hand count: {game.hand_count}")
    print(f"   Hand histories: {HandHistory.objects.filter(game=game).count()}")
    
    # Verify hand histories were created properly
    hand_histories = HandHistory.objects.filter(game=game).order_by('hand_number')
    for hh in hand_histories:
        print(f"     Hand #{hh.hand_number}: {hh.pot_amount} pot, phase {hh.final_phase}")
    
    return True


if __name__ == '__main__':
    try:
        success = test_complete_flow()
        if success:
            print("\n✅ Complete flow test successful")
        else:
            print("\n❌ Complete flow test failed")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()