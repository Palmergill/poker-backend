# tests/unit/test_bot_functionality.py
"""
Unit tests for bot player functionality.
"""

import unittest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from poker_api.models import PokerTable, Player, Game, PlayerGame, BotPlayer
from poker_api.services.game_service import GameService
from poker_api.utils.bot_engine import BotDecisionEngine


class BotPlayerTestCase(TestCase):
    """Test basic bot player creation and configuration."""
    
    def setUp(self):
        """Set up test data."""
        self.table = PokerTable.objects.create(
            name="Bot Test Table",
            max_players=6,
            small_blind=Decimal('1.00'),
            big_blind=Decimal('2.00'),
            min_buy_in=Decimal('20.00'),
            max_buy_in=Decimal('200.00')
        )
    
    def test_create_bot_player(self):
        """Test creating a bot player."""
        bot_player = GameService.create_bot_player(
            difficulty='INTERMEDIATE',
            play_style='LOOSE_AGGRESSIVE',
            aggression_factor=0.8,
            bluff_frequency=0.2
        )
        
        # Verify bot player was created correctly
        self.assertIsInstance(bot_player, BotPlayer)
        self.assertTrue(bot_player.player.is_bot)
        self.assertEqual(bot_player.difficulty, 'INTERMEDIATE')
        self.assertEqual(bot_player.play_style, 'LOOSE_AGGRESSIVE')
        self.assertEqual(bot_player.aggression_factor, 0.8)
        self.assertEqual(bot_player.bluff_frequency, 0.2)
        
        # Verify user account was created
        self.assertIsInstance(bot_player.player.user, User)
        # Bot names are randomly chosen from a list, so just verify it's not empty
        self.assertTrue(len(bot_player.player.user.username) > 0)
    
    def test_bot_player_str_representation(self):
        """Test string representation of bot player."""
        bot_player = GameService.create_bot_player()
        
        expected_format = f"Bot: {bot_player.player.user.username} (BASIC/TIGHT_AGGRESSIVE)"
        self.assertEqual(str(bot_player), expected_format)
        
        player_str = str(bot_player.player)
        self.assertTrue(player_str.startswith("[BOT]"))
    
    def test_add_bot_to_table(self):
        """Test adding a bot to a table."""
        # Create a waiting game
        human_user = User.objects.create_user(username='testuser', email='test@example.com')
        human_player = Player.objects.create(user=human_user)
        
        game = GameService.create_game(self.table, [(human_player, Decimal('100.00'))])
        
        # Add bot to table
        bot_player = GameService.add_bot_to_table(
            self.table, 
            Decimal('50.00'), 
            difficulty='BASIC',
            play_style='TIGHT_PASSIVE'
        )
        
        # Verify bot was added to the game
        bot_game = PlayerGame.objects.get(game=game, player=bot_player.player)
        self.assertEqual(bot_game.stack, Decimal('50.00'))
        self.assertEqual(bot_game.starting_stack, Decimal('50.00'))
        self.assertTrue(bot_game.is_active)
        self.assertFalse(bot_game.cashed_out)
    
    def test_get_available_bots(self):
        """Test getting available bots not in games."""
        # Create some bots
        bot1 = GameService.create_bot_player(difficulty='BASIC')
        bot2 = GameService.create_bot_player(difficulty='INTERMEDIATE')
        bot3 = GameService.create_bot_player(difficulty='ADVANCED')
        
        # All bots should be available initially
        available_bots = GameService.get_available_bots()
        initial_count = available_bots.count()
        self.assertGreaterEqual(initial_count, 3)  # At least our 3 bots
        
        # Create a game first
        human_user = User.objects.create_user(username='testuser2', email='test2@example.com')
        human_player = Player.objects.create(user=human_user)
        game = GameService.create_game(self.table, [(human_player, Decimal('100.00'))])
        
        # Add one bot to the existing game
        GameService.add_bot_to_table(self.table, Decimal('100.00'))
        
        # The new bot should not be available (it's in a game)
        available_bots = GameService.get_available_bots()
        self.assertEqual(available_bots.count(), initial_count)  # Same count since the new bot is in a game
    
    def test_bot_game_stats(self):
        """Test getting bot game statistics."""
        bot_player = GameService.create_bot_player()
        
        # Initially no games
        stats = GameService.get_bot_game_stats(bot_player)
        expected_stats = {
            'total_games': 0,
            'total_winnings': 0,
            'avg_winnings_per_game': 0,
            'win_rate': 0
        }
        self.assertEqual(stats, expected_stats)


class BotDecisionEngineTestCase(TestCase):
    """Test bot decision making engine."""
    
    def setUp(self):
        """Set up test data."""
        self.table = PokerTable.objects.create(
            name="Decision Test Table",
            max_players=6,
            small_blind=Decimal('1.00'),
            big_blind=Decimal('2.00'),
            min_buy_in=Decimal('20.00'),
            max_buy_in=Decimal('200.00')
        )
        
        # Create a bot player
        self.bot_player = GameService.create_bot_player(
            difficulty='BASIC',
            play_style='TIGHT_AGGRESSIVE'
        )
        
        # Create a game with the bot
        self.game = GameService.create_game(
            self.table, 
            [(self.bot_player.player, Decimal('100.00'))]
        )
        
        self.player_game = PlayerGame.objects.get(
            game=self.game, 
            player=self.bot_player.player
        )
    
    def test_decision_engine_initialization(self):
        """Test initializing the decision engine."""
        engine = BotDecisionEngine(self.bot_player, self.game, self.player_game)
        
        self.assertEqual(engine.bot_player, self.bot_player)
        self.assertEqual(engine.game, self.game)
        self.assertEqual(engine.player_game, self.player_game)
        self.assertEqual(engine.difficulty, 'BASIC')
        self.assertEqual(engine.play_style, 'TIGHT_AGGRESSIVE')
    
    def test_hand_strength_evaluation_no_cards(self):
        """Test hand strength evaluation with no cards."""
        engine = BotDecisionEngine(self.bot_player, self.game, self.player_game)
        strength = engine._evaluate_hand_strength()
        self.assertEqual(strength, 0.0)
    
    def test_get_thinking_time(self):
        """Test getting thinking time for bot."""
        engine = BotDecisionEngine(self.bot_player, self.game, self.player_game)
        thinking_time = engine.get_thinking_time()
        
        # Should be between min and max thinking time
        self.assertGreaterEqual(thinking_time, self.bot_player.thinking_time_min)
        self.assertLessEqual(thinking_time, self.bot_player.thinking_time_max)
    
    def test_make_decision_with_basic_actions(self):
        """Test making decisions with basic actions."""
        engine = BotDecisionEngine(self.bot_player, self.game, self.player_game)
        
        # Test with check/fold options
        valid_actions = ['CHECK', 'FOLD']
        action_type, amount = engine.make_decision(valid_actions)
        
        self.assertIn(action_type, valid_actions)
        if action_type in ['CHECK', 'FOLD']:
            self.assertEqual(amount, 0)
    
    def test_calculate_bet_size(self):
        """Test bet size calculation."""
        # Set up game state
        self.game.pot = Decimal('10.00')
        self.player_game.stack = Decimal('100.00')
        
        engine = BotDecisionEngine(self.bot_player, self.game, self.player_game)
        
        # Test with different aggression levels
        bet_size_low = engine._calculate_bet_size(0.2)
        bet_size_high = engine._calculate_bet_size(0.8)
        
        # Higher aggression should result in larger bets
        self.assertGreater(bet_size_high, bet_size_low)
        
        # Bet size should not exceed stack
        self.assertLessEqual(bet_size_high, self.player_game.stack)
        
        # Bet size should be at least the big blind
        self.assertGreaterEqual(bet_size_low, self.table.big_blind)


if __name__ == '__main__':
    unittest.main()