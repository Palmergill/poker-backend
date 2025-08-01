#!/usr/bin/env python3
"""
Test script to check if the big blind option is properly implemented.
In preflop, if everyone calls, the big blind should get an option to raise.
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


def test_big_blind_option():
    """Test if the big blind gets the option to act when everyone calls."""
    print("🃏 Testing big blind option...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_bb').delete()
    PokerTable.objects.filter(name='Test Big Blind').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_bb_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Test Big Blind',
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
    
    # Show initial setup
    player_games = PlayerGame.objects.filter(game=game).order_by('seat_position')
    print(f"\n📊 Initial setup:")
    for pg in player_games:
        blind_type = ""
        if pg.current_bet == Decimal('5'):
            blind_type = " (Small Blind)"
        elif pg.current_bet == Decimal('10'):
            blind_type = " (Big Blind)"
        print(f"   {pg.player.user.username} (Seat {pg.seat_position}): "
              f"Stack=${pg.stack}, Bet=${pg.current_bet}{blind_type}")
    
    print(f"\n   Current player: {game.current_player.user.username}")
    print(f"   Current bet: ${game.current_bet}")
    
    # Identify who has the big blind
    big_blind_player = None
    for pg in player_games:
        if pg.current_bet == Decimal('10'):
            big_blind_player = pg
            break
    
    if big_blind_player:
        print(f"   Big blind: {big_blind_player.player.user.username}")
    
    # Test scenario: Everyone calls the big blind
    print(f"\n🎯 Testing scenario: Everyone calls, big blind should get option")
    
    actions_taken = 0
    max_actions = 10
    
    while game.phase == 'PREFLOP' and actions_taken < max_actions:
        current_player_id = game.current_player.id
        current_player_name = game.current_player.user.username
        
        # Get player's current state
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        
        # Everyone just calls (no raises)
        if pg.current_bet < game.current_bet:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} calls ${game.current_bet}...")
            GameService.process_action(game.id, current_player_id, 'CALL')
        else:
            print(f"\n{actions_taken + 1}️⃣ Player {current_player_name} checks...")
            GameService.process_action(game.id, current_player_id, 'CHECK')
            
        game.refresh_from_db()
        actions_taken += 1
        
        print(f"   After action - Phase: {game.phase}")
        if game.phase != 'PREFLOP':
            print(f"   🔄 Advanced to {game.phase}")
            break
        else:
            print(f"   Current player: {game.current_player.user.username}")
        
        # Check if we're back to the big blind
        if game.current_player.id == big_blind_player.player.id and actions_taken > 1:
            print(f"   🎯 Action is back to big blind ({big_blind_player.player.user.username})")
    
    # Analyze the results
    actions = GameAction.objects.filter(
        player_game__game=game,
        phase='PREFLOP'
    ).order_by('timestamp')
    
    print(f"\n📊 Final Analysis:")
    print(f"   Total preflop actions: {actions.count()}")
    print(f"   Final phase: {game.phase}")
    
    # Check if big blind got the option
    big_blind_actions = actions.filter(player_game=big_blind_player)
    print(f"   Big blind actions: {big_blind_actions.count()}")
    
    for i, action in enumerate(actions):
        action_num = i + 1
        is_bb = " (BIG BLIND)" if action.player_game == big_blind_player else ""
        print(f"     {action_num}. {action.player_game.player.user.username}: {action.action_type}{is_bb}")
    
    # According to poker rules, in preflop when everyone calls:
    # 1. Action should return to big blind
    # 2. Big blind should get option to raise or check
    # 3. Only after big blind acts should the round be complete
    
    if game.phase == 'PREFLOP':
        print(f"⚠️  Still in preflop after {actions_taken} actions")
        return False
    
    # Check if big blind got proper option
    if big_blind_actions.count() == 0:
        print(f"❌ BUG: Big blind never got to act!")
        return False
    elif big_blind_actions.count() == 1:
        # Big blind should have at least one action (could be just the initial check if everyone called)
        last_action = actions.last()
        if last_action.player_game != big_blind_player and last_action.action_type not in ['CHECK', 'RAISE', 'FOLD']:
            print(f"❌ BUG: Round ended without giving big blind final option")
            print(f"   Last action was by {last_action.player_game.player.user.username}: {last_action.action_type}")
            return False
        else:
            print(f"✅ Big blind got proper option")
            return True
    else:
        print(f"✅ Big blind acted {big_blind_actions.count()} times")
        return True


if __name__ == '__main__':
    try:
        success = test_big_blind_option()
        if success:
            print("\n✅ Test completed successfully")
        else:
            print("\n❌ Test found issues with big blind option")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()