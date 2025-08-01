#!/usr/bin/env python3
"""
Test script to verify frontend console logging and hand history display fixes.
This will create some hands and provide instructions to check the frontend.
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


def create_test_hands():
    """Create test hands for frontend testing."""
    print("🃏 Creating test hands for frontend testing...")
    
    # Clean up any existing test data
    User.objects.filter(username__startswith='test_frontend').delete()
    PokerTable.objects.filter(name='Frontend Test Table').delete()
    
    # Create test users and players
    users = []
    players = []
    for i in range(3):
        user = User.objects.create_user(
            username=f'test_frontend_{i+1}', 
            password='testpass'
        )
        player = Player.objects.create(user=user, balance=Decimal('1000'))
        users.append(user)
        players.append(player)
    
    # Create test table
    table = PokerTable.objects.create(
        name='Frontend Test Table',
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
    
    # Create multiple test hands
    for hand_num in range(1, 4):  # Create 3 hands
        print(f"\n🎯 Creating test hand #{hand_num}...")
        
        # Play a few actions then end the hand
        actions_taken = 0
        max_actions = 6
        
        while game.status == 'PLAYING' and actions_taken < max_actions:
            current_player_id = game.current_player.id
            current_player_name = game.current_player.user.username
            pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
            
            if actions_taken < 2:  # First few actions
                if pg.current_bet < game.current_bet:
                    print(f"     {current_player_name} calls ${game.current_bet}")
                    GameService.process_action(game.id, current_player_id, 'CALL')
                else:
                    print(f"     {current_player_name} checks")
                    GameService.process_action(game.id, current_player_id, 'CHECK')
            else:
                # End hand with folds
                print(f"     {current_player_name} folds")
                GameService.process_action(game.id, current_player_id, 'FOLD')
            
            game.refresh_from_db()
            actions_taken += 1
            
            # Check if hand completed
            current_hand_count = HandHistory.objects.filter(game=game).count()
            if current_hand_count >= hand_num:
                print(f"   ✅ Hand #{hand_num} completed!")
                break
    
    # Show final results
    hand_histories = HandHistory.objects.filter(game=game).order_by('hand_number')
    print(f"\n📊 Created {hand_histories.count()} test hands:")
    
    for hh in hand_histories:
        winner_info = hh.get_winner_info()
        if winner_info and 'winners' in winner_info:
            winner_name = winner_info['winners'][0]['player_name']
            winning_amount = winner_info['winners'][0]['winning_amount']
        else:
            winner_name = 'Unknown'
            winning_amount = 0
        print(f"   Hand #{hh.hand_number}: Winner: {winner_name}, Amount: ${winning_amount}")
    
    print(f"\n🎮 Game ID: {game.id}")
    print(f"🌐 Game URL: http://localhost:3000/games/{game.id}")
    print(f"\n📋 To test the fixes:")
    print(f"1. Start the React app: cd poker-frontend && npm start")
    print(f"2. Go to: http://localhost:3000/games/{game.id}")
    print(f"3. Open Chrome Developer Tools (F12) and check the Console tab")
    print(f"4. Look for:")
    print(f"   - 📡 Hand history API response logs")
    print(f"   - 📝 Hand processing logs")
    print(f"   - 📋 Formatted hand history logs")
    print(f"   - 🎨 Hand history rendering logs")
    print(f"5. Check if the hand history panel shows the winners correctly")
    
    return game.id


if __name__ == '__main__':
    try:
        game_id = create_test_hands()
        print(f"\n✅ Test data created successfully!")
        print(f"🎯 Next step: Test the frontend at http://localhost:3000/games/{game_id}")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()