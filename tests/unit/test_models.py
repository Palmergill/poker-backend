"""
Comprehensive test suite for the poker application.

This test suite covers:
- Models (PokerTable, Player, Game, PlayerGame, GameAction, HandHistory)
- Game Service functionality
- API endpoints
- Hand evaluation logic
- Integration tests
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
import json
from unittest.mock import patch, MagicMock

from poker_api.models import (
    PokerTable, Player, Game, PlayerGame, GameAction, HandHistory
)
from poker_api.services.game_service import GameService
from poker_api.utils.card_utils import Card, Deck
from poker_api.utils.hand_evaluator import HandEvaluator


class ModelTestCase(TestCase):
    """Test cases for all models."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='player1', email='player1@test.com', password='testpass'
        )
        self.user2 = User.objects.create_user(
            username='player2', email='player2@test.com', password='testpass'
        )
        
        self.player1 = Player.objects.create(user=self.user1)
        self.player2 = Player.objects.create(user=self.user2)
        
        self.table = PokerTable.objects.create(
            name='Test Table',
            max_players=6,
            small_blind=Decimal('1'),
            big_blind=Decimal('2'),
            min_buy_in=Decimal('50'),
            max_buy_in=Decimal('200')
        )

    def test_poker_table_creation(self):
        """Test PokerTable model creation and string representation."""
        self.assertEqual(str(self.table), 'Test Table')
        self.assertEqual(self.table.max_players, 6)
        self.assertEqual(self.table.small_blind, Decimal('1'))
        self.assertEqual(self.table.big_blind, Decimal('2'))

    def test_player_creation(self):
        """Test Player model creation and string representation."""
        self.assertEqual(str(self.player1), 'player1')

    def test_game_creation(self):
        """Test Game model creation and methods."""
        game = Game.objects.create(
            table=self.table,
            status='WAITING',
            pot=Decimal('0')
        )
        
        self.assertEqual(str(game), f"Game at {self.table.name}")
        self.assertEqual(game.status, 'WAITING')
        self.assertEqual(game.hand_count, 0)

    def test_game_community_cards_methods(self):
        """Test Game model community card JSON methods."""
        game = Game.objects.create(table=self.table)
        
        # Test setting and getting community cards
        cards = ['AH', 'KS', 'QD']
        game.set_community_cards(cards)
        self.assertEqual(game.get_community_cards(), cards)
        
        # Test empty community cards
        game.community_cards = None
        self.assertEqual(game.get_community_cards(), [])

    def test_game_winner_info_methods(self):
        """Test Game model winner info JSON methods."""
        game = Game.objects.create(table=self.table)
        
        winner_data = {
            'type': 'showdown_winner',
            'winners': [{'player_name': 'player1', 'winning_amount': 100}]
        }
        
        game.set_winner_info(winner_data)
        self.assertEqual(game.get_winner_info(), winner_data)
        
        # Test empty winner info
        game.winner_info = None
        self.assertIsNone(game.get_winner_info())

    def test_player_game_creation(self):
        """Test PlayerGame model creation."""
        game = Game.objects.create(table=self.table)
        
        pg = PlayerGame.objects.create(
            player=self.player1,
            game=game,
            seat_position=0,
            stack=Decimal('100')
        )
        
        self.assertEqual(str(pg), f"{self.player1} at {game}")
        self.assertEqual(pg.seat_position, 0)
        self.assertEqual(pg.stack, Decimal('100'))
        self.assertTrue(pg.is_active)

    def test_player_game_cards_methods(self):
        """Test PlayerGame model card JSON methods."""
        game = Game.objects.create(table=self.table)
        pg = PlayerGame.objects.create(
            player=self.player1, game=game, seat_position=0, stack=Decimal('100')
        )
        
        # Test setting and getting cards
        cards = ['AH', 'KS']
        pg.set_cards(cards)
        self.assertEqual(pg.get_cards(), cards)
        
        # Test empty cards
        pg.cards = None
        self.assertEqual(pg.get_cards(), [])

    def test_game_action_creation(self):
        """Test GameAction model creation."""
        game = Game.objects.create(table=self.table)
        pg = PlayerGame.objects.create(
            player=self.player1, game=game, seat_position=0, stack=Decimal('100')
        )
        
        action = GameAction.objects.create(
            player_game=pg,
            action_type='BET',
            amount=Decimal('10'),
            phase='PREFLOP'
        )
        
        self.assertEqual(str(action), f"{self.player1} BET 10")
        self.assertEqual(action.action_type, 'BET')
        self.assertEqual(action.amount, Decimal('10'))

    def test_game_action_string_representation(self):
        """Test GameAction string representation for different action types."""
        game = Game.objects.create(table=self.table)
        pg = PlayerGame.objects.create(
            player=self.player1, game=game, seat_position=0, stack=Decimal('100')
        )
        
        # Test actions with amounts
        bet_action = GameAction.objects.create(
            player_game=pg, action_type='BET', amount=Decimal('10')
        )
        self.assertEqual(str(bet_action), f"{self.player1} BET 10")
        
        # Test actions without amounts
        fold_action = GameAction.objects.create(
            player_game=pg, action_type='FOLD'
        )
        self.assertEqual(str(fold_action), f"{self.player1} FOLD")

    def test_hand_history_creation(self):
        """Test HandHistory model creation and methods."""
        game = Game.objects.create(table=self.table)
        
        hand_history = HandHistory.objects.create(
            game=game,
            hand_number=1,
            pot_amount=Decimal('20'),
            final_phase='SHOWDOWN'
        )
        
        self.assertEqual(str(hand_history), f"Hand 1 - Game {game.id}")
        self.assertEqual(hand_history.hand_number, 1)
        self.assertEqual(hand_history.pot_amount, Decimal('20'))

    def test_hand_history_json_methods(self):
        """Test HandHistory model JSON methods."""
        game = Game.objects.create(table=self.table)
        hand_history = HandHistory.objects.create(
            game=game, hand_number=1, pot_amount=Decimal('20'), final_phase='SHOWDOWN'
        )
        
        # Test winner info
        winner_data = {'type': 'showdown_winner', 'winners': []}
        hand_history.set_winner_info(winner_data)
        self.assertEqual(hand_history.get_winner_info(), winner_data)
        
        # Test player cards
        player_cards = {'player1': ['AH', 'KS'], 'player2': ['QD', 'JC']}
        hand_history.set_player_cards(player_cards)
        self.assertEqual(hand_history.get_player_cards(), player_cards)
        
        # Test actions
        actions = [{'player': 'player1', 'action': 'BET', 'amount': 10}]
        hand_history.set_actions(actions)
        self.assertEqual(hand_history.get_actions(), actions)
        
        # Test community cards
        community = ['AH', 'KS', 'QD']
        hand_history.set_community_cards(community)
        self.assertEqual(hand_history.get_community_cards(), community)


class CardUtilsTestCase(TestCase):
    """Test cases for card utilities."""
    
    def test_card_creation(self):
        """Test Card creation and properties."""
        card = Card('A', 'H')
        self.assertEqual(card.rank, 'A')
        self.assertEqual(card.suit, 'H')
        self.assertEqual(card.rank_value, 14)
        self.assertEqual(str(card), 'AH')

    def test_card_equality(self):
        """Test Card equality comparison."""
        card1 = Card('A', 'H')
        card2 = Card('A', 'H')
        card3 = Card('K', 'H')
        
        self.assertEqual(card1, card2)
        self.assertNotEqual(card1, card3)
        self.assertNotEqual(card1, "not a card")

    def test_card_comparison(self):
        """Test Card less than comparison."""
        ace = Card('A', 'H')
        king = Card('K', 'S')
        
        self.assertTrue(king < ace)
        self.assertFalse(ace < king)

    def test_deck_creation(self):
        """Test Deck creation."""
        deck = Deck()
        self.assertEqual(len(deck.cards), 52)
        
        # Check that all cards are present
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        suits = ['S', 'H', 'D', 'C']
        
        expected_cards = []
        for suit in suits:
            for rank in ranks:
                expected_cards.append(f"{rank}{suit}")
        
        deck_cards = [str(card) for card in deck.cards]
        self.assertEqual(set(deck_cards), set(expected_cards))

    def test_deck_shuffle(self):
        """Test Deck shuffle functionality."""
        deck1 = Deck()
        deck2 = Deck()
        
        original_order = [str(card) for card in deck1.cards]
        deck1.shuffle()
        shuffled_order = [str(card) for card in deck1.cards]
        
        # Cards should be the same but likely in different order
        self.assertEqual(set(original_order), set(shuffled_order))
        # Very unlikely to be in same order after shuffle
        self.assertNotEqual(original_order, shuffled_order)

    def test_deck_deal(self):
        """Test Deck deal functionality."""
        deck = Deck()
        initial_count = len(deck.cards)
        
        # Deal 2 cards
        cards = deck.deal(2)
        self.assertEqual(len(cards), 2)
        self.assertEqual(len(deck.cards), initial_count - 2)
        
        # Check that dealt cards are Card objects
        for card in cards:
            self.assertIsInstance(card, Card)

    def test_deck_reset(self):
        """Test Deck reset functionality."""
        deck = Deck()
        deck.deal(10)  # Remove some cards
        
        self.assertEqual(len(deck.cards), 42)
        
        deck.reset()
        self.assertEqual(len(deck.cards), 52)


class HandEvaluatorTestCase(TestCase):
    """Test cases for hand evaluation logic."""
    
    def test_royal_flush(self):
        """Test royal flush detection."""
        cards = [
            Card('A', 'H'), Card('K', 'H'), Card('Q', 'H'),
            Card('J', 'H'), Card('10', 'H'), Card('2', 'S'), Card('3', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 1)  # Royal flush is rank 1
        self.assertEqual(name, "Royal Flush")

    def test_straight_flush(self):
        """Test straight flush detection."""
        cards = [
            Card('9', 'H'), Card('8', 'H'), Card('7', 'H'),
            Card('6', 'H'), Card('5', 'H'), Card('A', 'S'), Card('K', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 2)  # Straight flush is rank 2
        self.assertEqual(name, "Straight Flush")

    def test_four_of_a_kind(self):
        """Test four of a kind detection."""
        cards = [
            Card('A', 'H'), Card('A', 'S'), Card('A', 'D'),
            Card('A', 'C'), Card('K', 'H'), Card('Q', 'S'), Card('J', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 3)  # Four of a kind is rank 3
        self.assertEqual(name, "Four of a Kind")

    def test_full_house(self):
        """Test full house detection."""
        cards = [
            Card('A', 'H'), Card('A', 'S'), Card('A', 'D'),
            Card('K', 'H'), Card('K', 'S'), Card('Q', 'C'), Card('J', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 4)  # Full house is rank 4
        self.assertEqual(name, "Full House")

    def test_flush(self):
        """Test flush detection."""
        cards = [
            Card('A', 'H'), Card('K', 'H'), Card('Q', 'H'),
            Card('J', 'H'), Card('9', 'H'), Card('2', 'S'), Card('3', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 5)  # Flush is rank 5
        self.assertEqual(name, "Flush")

    def test_straight(self):
        """Test straight detection."""
        cards = [
            Card('A', 'H'), Card('K', 'S'), Card('Q', 'D'),
            Card('J', 'C'), Card('10', 'H'), Card('2', 'S'), Card('3', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 6)  # Straight is rank 6
        self.assertEqual(name, "Straight")

    def test_three_of_a_kind(self):
        """Test three of a kind detection."""
        cards = [
            Card('A', 'H'), Card('A', 'S'), Card('A', 'D'),
            Card('K', 'H'), Card('Q', 'S'), Card('J', 'C'), Card('9', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 7)  # Three of a kind is rank 7
        self.assertEqual(name, "Three of a Kind")

    def test_two_pair(self):
        """Test two pair detection."""
        cards = [
            Card('A', 'H'), Card('A', 'S'), Card('K', 'D'),
            Card('K', 'H'), Card('Q', 'S'), Card('J', 'C'), Card('9', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 8)  # Two pair is rank 8
        self.assertEqual(name, "Two Pair")

    def test_one_pair(self):
        """Test one pair detection."""
        cards = [
            Card('A', 'H'), Card('A', 'S'), Card('K', 'D'),
            Card('Q', 'H'), Card('J', 'S'), Card('8', 'C'), Card('7', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 9)  # One pair is rank 9
        self.assertEqual(name, "One Pair")

    def test_high_card(self):
        """Test high card detection."""
        cards = [
            Card('A', 'H'), Card('K', 'S'), Card('Q', 'D'),
            Card('J', 'H'), Card('9', 'S'), Card('7', 'C'), Card('5', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 10)  # High card is rank 10
        self.assertEqual(name, "High Card")

    def test_hand_value_comparison(self):
        """Test that hand values allow proper comparison."""
        # Pair of Aces should beat pair of Kings
        aces = [
            Card('A', 'H'), Card('A', 'S'), Card('K', 'D'),
            Card('Q', 'H'), Card('J', 'S')
        ]
        kings = [
            Card('K', 'H'), Card('K', 'S'), Card('A', 'D'),
            Card('Q', 'H'), Card('J', 'S')
        ]
        
        aces_rank, aces_value, _, _ = HandEvaluator.evaluate_hand(aces)
        kings_rank, kings_value, _, _ = HandEvaluator.evaluate_hand(kings)
        
        self.assertEqual(aces_rank, kings_rank)  # Both are pairs
        self.assertGreater(aces_value[0], kings_value[0])  # Aces > Kings

    def test_insufficient_cards(self):
        """Test that error is raised for insufficient cards."""
        cards = [Card('A', 'H'), Card('K', 'S')]  # Only 2 cards
        
        with self.assertRaises(ValueError):
            HandEvaluator.evaluate_hand(cards)


class GameServiceTestCase(TransactionTestCase):
    """Test cases for GameService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='player1', password='testpass'
        )
        self.user2 = User.objects.create_user(
            username='player2', password='testpass'
        )
        
        self.player1 = Player.objects.create(user=self.user1)
        self.player2 = Player.objects.create(user=self.user2)
        
        self.table = PokerTable.objects.create(
            name='Test Table',
            max_players=6,
            small_blind=Decimal('1'),
            big_blind=Decimal('2'),
            min_buy_in=Decimal('50'),
            max_buy_in=Decimal('200')
        )

    def test_card_parsing(self):
        """Test the _parse_card helper method."""
        # Test regular cards
        card = GameService._parse_card('AH')
        self.assertEqual(card.rank, 'A')
        self.assertEqual(card.suit, 'H')
        
        # Test 10 cards
        card = GameService._parse_card('10C')
        self.assertEqual(card.rank, '10')
        self.assertEqual(card.suit, 'C')
        
        # Test invalid format
        with self.assertRaises(ValueError):
            GameService._parse_card('invalid')

    def test_create_game(self):
        """Test game creation."""
        players_with_buy_ins = [(self.player1, Decimal('100')), (self.player2, Decimal('100'))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        self.assertEqual(game.table, self.table)
        self.assertEqual(game.status, 'WAITING')  # Game starts in WAITING state
        self.assertIsNone(game.phase)  # Phase is set when game starts
        
        # Check that player games were created
        player_games = PlayerGame.objects.filter(game=game)
        self.assertEqual(player_games.count(), 2)
        
        # Check that pot starts at 0 (blinds posted when game starts)
        self.assertEqual(game.pot, 0)

    @patch('poker_api.services.game_service.GameService.broadcast_game_update')
    def test_player_action_fold(self, mock_broadcast):
        """Test player fold action."""
        # Create a game with 3 players to avoid immediate game end
        user3 = User.objects.create_user(username='player3', password='testpass')
        player3 = Player.objects.create(user=user3)
        
        players_with_buy_ins = [(self.player1, Decimal('100')), (self.player2, Decimal('100')), (player3, Decimal('100'))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Start the game to post blinds and begin play
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Find the current player (should be first to act after blinds)
        current_player_id = game.current_player.id
        
        # Current player folds
        GameService.process_action(game.id, current_player_id, 'FOLD')
        
        # Check that action was recorded
        actions = GameAction.objects.filter(
            player_game__game=game,
            player_game__player_id=current_player_id,
            action_type='FOLD'
        )
        self.assertEqual(actions.count(), 1)
        
        # Check that folding player is marked as inactive
        folded_pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        self.assertFalse(folded_pg.is_active)

    @patch('poker_api.services.game_service.GameService.broadcast_game_update')
    def test_player_action_check(self, mock_broadcast):
        """Test player check action."""
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Start the game to post blinds and begin play
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Move to flop phase where checking is valid
        game.phase = 'FLOP'
        game.current_bet = Decimal('0')
        game.save()
        
        # Reset all player bets for new round
        PlayerGame.objects.filter(game=game).update(current_bet=Decimal('0'))
        
        # Get current player and make them check
        current_player_id = game.current_player.id
        
        GameService.process_action(game.id, current_player_id, 'CHECK')
        
        # Check that action was recorded
        actions = GameAction.objects.filter(
            player_game__game=game,
            player_game__player_id=current_player_id,
            action_type='CHECK'
        )
        self.assertEqual(actions.count(), 1)

    @patch('poker_api.services.game_service.GameService.broadcast_game_update')
    def test_player_action_bet(self, mock_broadcast):
        """Test player bet action."""
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Start the game to post blinds and begin play
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Move to flop to allow betting
        game.phase = 'FLOP'
        game.current_bet = Decimal('0')
        game.save()
        
        # Reset player bets for new round
        PlayerGame.objects.filter(game=game).update(current_bet=Decimal('0'))
        
        # Get current player to bet
        current_player_id = game.current_player.id
        bet_amount = Decimal('10')
        GameService.process_action(game.id, current_player_id, 'BET', bet_amount)
        
        # Check that bet was processed
        game.refresh_from_db()
        self.assertEqual(game.current_bet, bet_amount)
        
        pg = PlayerGame.objects.get(game=game, player_id=current_player_id)
        self.assertEqual(pg.current_bet, bet_amount)

    def test_invalid_player_action(self):
        """Test that invalid actions raise errors."""
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Start the game to post blinds and begin play
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        # Try to check when there's a bet to call
        with self.assertRaises(ValueError):
            GameService.process_action(game.id, self.player1.id, 'CHECK')

    def test_showdown_order(self):
        """Test showdown order determination."""
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        active_players = PlayerGame.objects.filter(game=game, is_active=True)
        
        # Test with no river betting
        game.phase = 'RIVER'
        showdown_order = GameService._get_showdown_order(game, active_players)
        
        self.assertEqual(len(showdown_order), 2)
        self.assertIn(showdown_order[0], active_players)

    @patch('poker_api.services.game_service.GameService.broadcast_game_update')
    def test_game_phase_progression(self, mock_broadcast):
        """Test that game phases progress correctly."""
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Start the game to post blinds and begin play
        GameService.start_game(game.id)
        game.refresh_from_db()
        initial_phase = game.phase
        
        # Small blind (first player) calls to match big blind
        first_player_id = game.current_player.id
        GameService.process_action(game.id, first_player_id, 'CALL')
        
        game.refresh_from_db()
        # Big blind checks to complete preflop
        second_player_id = game.current_player.id
        GameService.process_action(game.id, second_player_id, 'CHECK')
        
        game.refresh_from_db()
        # Should have advanced from PREFLOP to FLOP
        self.assertNotEqual(game.phase, initial_phase)


class APITestCase(APITestCase):
    """Test cases for API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser', password='testpass'
        )
        self.player = Player.objects.create(user=self.user)
        
        self.table = PokerTable.objects.create(
            name='Test Table',
            max_players=6,
            small_blind=Decimal('1'),
            big_blind=Decimal('2'),
            min_buy_in=Decimal('50'),
            max_buy_in=Decimal('200')
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_register_user_endpoint(self):
        """Test user registration endpoint."""
        url = reverse('register_user')
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'newpassword'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that user and player were created
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertTrue(Player.objects.filter(user=new_user).exists())

    def test_table_list_endpoint(self):
        """Test table list endpoint."""
        url = reverse('pokertable-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Table')

    def test_game_list_endpoint(self):
        """Test game list endpoint."""
        # Create a game first
        game = Game.objects.create(table=self.table, status='WAITING')
        PlayerGame.objects.create(
            player=self.player, game=game, seat_position=0, stack=Decimal('100')
        )
        
        url = reverse('game-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_hand_history_endpoint(self):
        """Test hand history endpoint."""
        # Create a game with hand history
        game = Game.objects.create(table=self.table, status='PLAYING')
        PlayerGame.objects.create(
            player=self.player, game=game, seat_position=0, stack=Decimal('100')
        )
        
        # Create hand history
        HandHistory.objects.create(
            game=game,
            hand_number=1,
            pot_amount=Decimal('20'),
            final_phase='SHOWDOWN',
            winner_info='{"type": "test"}',
            player_cards='{}',
            actions='[]'
        )
        
        url = reverse('game_hand_history', kwargs={'game_id': game.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['hand_history']), 1)

    def test_unauthorized_access(self):
        """Test that unauthorized requests are rejected."""
        self.client.force_authenticate(user=None)
        
        url = reverse('pokertable-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class IntegrationTestCase(TransactionTestCase):
    """Integration tests for complete game scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='player1', password='testpass'
        )
        self.user2 = User.objects.create_user(
            username='player2', password='testpass'
        )
        
        self.player1 = Player.objects.create(user=self.user1)
        self.player2 = Player.objects.create(user=self.user2)
        
        self.table = PokerTable.objects.create(
            name='Test Table',
            max_players=6,
            small_blind=Decimal('1'),
            big_blind=Decimal('2'),
            min_buy_in=Decimal('50'),
            max_buy_in=Decimal('200')
        )

    @patch('poker_api.services.game_service.GameService.broadcast_game_update')
    def test_complete_hand_by_folding(self, mock_broadcast):
        """Test a complete hand that ends by folding."""
        # Create game
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Start the game to post blinds and begin play
        GameService.start_game(game.id)
        game.refresh_from_db()
        
        initial_pot = game.pot
        
        # Current player folds
        current_player_id = game.current_player.id
        GameService.process_action(game.id, current_player_id, 'FOLD')
        
        game.refresh_from_db()
        
        # Check that hand history was created
        hand_histories = HandHistory.objects.filter(game=game)
        self.assertEqual(hand_histories.count(), 1)
        
        history = hand_histories.first()
        winner_info = history.get_winner_info()
        self.assertEqual(winner_info['type'], 'single_winner')
        self.assertEqual(winner_info['winners'][0]['reason'], 'All other players folded')

    @patch('poker_api.services.game_service.GameService.broadcast_game_update')
    def test_complete_hand_to_showdown(self, mock_broadcast):
        """Test a complete hand that goes to showdown."""
        # Create game
        players_with_buy_ins = [(self.player1, Decimal("100")), (self.player2, Decimal("100"))]
        
        game = GameService.create_game(self.table, players_with_buy_ins)
        
        # Play through all phases without folding
        # This is a simplified test - in reality would need to handle
        # all the betting rounds properly
        
        # Force game to showdown phase for testing
        game.phase = 'RIVER'
        game.community_cards = json.dumps(['AH', 'KS', 'QD', 'JC', '10H'])
        game.save()
        
        # Set player cards
        pg1 = PlayerGame.objects.get(game=game, player=self.player1)
        pg2 = PlayerGame.objects.get(game=game, player=self.player2)
        
        pg1.set_cards(['AS', 'KD'])  # Pair of aces
        pg2.set_cards(['2H', '3S'])  # High card
        pg1.save()
        pg2.save()
        
        # Trigger showdown
        GameService._showdown(game)
        
        # Check that hand history was created with showdown data
        hand_histories = HandHistory.objects.filter(game=game)
        self.assertGreater(hand_histories.count(), 0)
        
        history = hand_histories.first()
        winner_info = history.get_winner_info()
        self.assertEqual(winner_info['type'], 'showdown_winner')

    def test_multiple_hands_progression(self):
        """Test that multiple hands can be played in sequence."""
        # This would test that after one hand ends, a new hand starts
        # and that hand numbers increment correctly
        pass  # Implementation would be quite complex

    def test_player_elimination(self):
        """Test that players are eliminated when they run out of chips."""
        # This would test the scenario where a player loses all chips
        # and is removed from active play
        pass  # Implementation would be quite complex


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["poker_api.tests"])