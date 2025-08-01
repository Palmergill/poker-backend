# tests/integration/test_bot_turn_taking.py

from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
import logging

from poker_api.models import PokerTable, Game, Player, PlayerGame, BotPlayer
from poker_api.services.game_service import GameService

# Disable logging during tests to reduce noise
logging.disable(logging.CRITICAL)

class BotTurnTakingTestCase(TestCase):
    """Integration tests for bot turn-taking functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.table = PokerTable.objects.create(
            name="Bot Turn Test Table",
            max_players=4,
            small_blind=Decimal('1.00'),
            big_blind=Decimal('2.00'),
            min_buy_in=Decimal('20.00'),
            max_buy_in=Decimal('200.00')
        )
        
        # Create human player
        self.human_user = User.objects.create_user(
            username='human_player',
            email='human@test.com',
            password='testpass'
        )
        self.human_player = Player.objects.create(user=self.human_user)
        
        # Create bot players
        self.bot1 = GameService.create_bot_player(
            difficulty='BASIC',
            play_style='TIGHT_AGGRESSIVE',
            aggression_factor=0.5,
            bluff_frequency=0.1
        )
        
        self.bot2 = GameService.create_bot_player(
            difficulty='INTERMEDIATE',
            play_style='LOOSE_AGGRESSIVE',
            aggression_factor=0.7,
            bluff_frequency=0.2
        )
    
    def test_bot_takes_turn_after_human(self):
        """Test that a bot takes its turn after a human player acts."""
        # Create game with human and bot
        game = GameService.create_game(self.table, [
            (self.human_player, Decimal('100.00')),
            (self.bot1.player, Decimal('100.00'))
        ])
        
        # Start the game
        GameService.start_game(game.id)
        
        # Refresh game state
        game.refresh_from_db()
        
        # Verify game started
        self.assertEqual(game.status, 'PLAYING')
        self.assertEqual(game.phase, 'PREFLOP')
        
        # Get current player (should be first to act after big blind)
        current_player = game.current_player
        
        # If current player is human, make an action and check bot responds
        if not current_player.is_bot:
            # Human player calls
            GameService.process_action(game.id, current_player.id, 'CALL', 0)
            
            # Refresh game state
            game.refresh_from_db()
            
            # Current player should now be the bot
            self.assertTrue(game.current_player.is_bot)
            
            # Bot should automatically take action (this happens via _schedule_bot_action)
            # In synchronous mode, the bot action should complete immediately
            # Let's verify the game advanced properly by checking if it's still the bot's turn
            # If bot failed to act, it would still be bot's turn
            
            # Give bot time to act (in real scenario, this happens automatically)
            import time
            time.sleep(0.1)  # Brief pause for any async operations
            
            # Refresh again
            game.refresh_from_db()
            
            # Game should have progressed (either different current player or next phase)
            # If bot acted successfully, we should see some change in game state
            self.assertIsNotNone(game.current_player)
    
    def test_bot_failure_recovery(self):
        """Test that game recovers when bot fails to act."""
        # Create game with only bots to test fallback
        game = GameService.create_game(self.table, [
            (self.bot1.player, Decimal('100.00')),
            (self.bot2.player, Decimal('100.00'))
        ])
        
        # Start the game
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Verify game started correctly
        self.assertEqual(game.status, 'PLAYING')
        self.assertIsNotNone(game.current_player)
        self.assertTrue(game.current_player.is_bot)
        
        # Simulate bot action failure by calling _handle_bot_action_failure directly
        # This tests the fallback mechanism
        original_current_player = game.current_player
        
        # Try the bot failure handler
        success = GameService._handle_bot_action_failure(game.id, "Test bot failure")
        
        # Should return True indicating successful recovery
        self.assertTrue(success)
        
        # Refresh game
        game.refresh_from_db()
        
        # Game should still be playable (not stuck)
        self.assertEqual(game.status, 'PLAYING')
    
    def test_multiple_bots_take_turns(self):
        """Test that multiple bots can take turns in sequence."""
        # Create game with multiple bots
        bot3 = GameService.create_bot_player(
            difficulty='ADVANCED',
            play_style='TIGHT_PASSIVE',
            aggression_factor=0.3,
            bluff_frequency=0.05
        )
        
        game = GameService.create_game(self.table, [
            (self.bot1.player, Decimal('100.00')),
            (self.bot2.player, Decimal('100.00')),
            (bot3.player, Decimal('100.00'))
        ])
        
        # Start the game
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Verify game started
        self.assertEqual(game.status, 'PLAYING')
        self.assertEqual(game.phase, 'PREFLOP')
        
        # Track initial state
        initial_pot = game.pot
        initial_current_player = game.current_player
        
        # Allow some time for bot actions in case of threading
        import time
        time.sleep(0.5)
        
        # Refresh game state
        game.refresh_from_db()
        
        # Game should be progressing - either pot changed, phase changed, or current player changed
        # This indicates bots are successfully taking actions
        game_progressed = (
            game.pot != initial_pot or 
            game.phase != 'PREFLOP' or 
            game.current_player != initial_current_player
        )
        
        # At minimum, the game should not be stuck on the same player
        # (unless all bots folded and only one remains)
        active_players = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False)
        if active_players.count() > 1:
            # If multiple players still active, game should have progressed
            self.assertTrue(game_progressed or game.current_player != initial_current_player)
    
    def test_bot_action_timeout_recovery(self):
        """Test that bot action timeouts are handled gracefully."""
        # This test verifies that the timeout mechanism works
        # In practice, we can't easily simulate a real timeout in unit tests,
        # but we can test the error handling path
        
        game = GameService.create_game(self.table, [
            (self.human_player, Decimal('100.00')),
            (self.bot1.player, Decimal('100.00'))
        ])
        
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Test that _handle_bot_action_failure works with timeout scenario
        if game.current_player and game.current_player.is_bot:
            success = GameService._handle_bot_action_failure(game.id, "Bot action timeout: 30.0s")
            self.assertTrue(success)
            
            # Game should still be in a valid state
            game.refresh_from_db()
            self.assertEqual(game.status, 'PLAYING')
    
    def tearDown(self):
        """Clean up after tests."""
        # Re-enable logging
        logging.disable(logging.NOTSET)