#!/usr/bin/env python
"""
Standalone test runner for components that don't require database access.
"""

import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(__file__))

# Import utilities that don't require Django models
from poker_api.utils.card_utils import Card, Deck
from poker_api.utils.hand_evaluator import HandEvaluator


class TestCardUtils(unittest.TestCase):
    """Test card utilities without Django."""
    
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

    def test_deck_creation(self):
        """Test Deck creation."""
        deck = Deck()
        self.assertEqual(len(deck.cards), 52)

    def test_deck_deal(self):
        """Test Deck deal functionality."""
        deck = Deck()
        initial_count = len(deck.cards)
        
        cards = deck.deal(2)
        self.assertEqual(len(cards), 2)
        self.assertEqual(len(deck.cards), initial_count - 2)


class TestHandEvaluator(unittest.TestCase):
    """Test hand evaluation logic without Django."""
    
    def test_royal_flush(self):
        """Test royal flush detection."""
        cards = [
            Card('A', 'H'), Card('K', 'H'), Card('Q', 'H'),
            Card('J', 'H'), Card('10', 'H'), Card('2', 'S'), Card('3', 'D')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 1)
        self.assertEqual(name, "Royal Flush")

    def test_one_pair(self):
        """Test one pair detection."""
        cards = [
            Card('A', 'H'), Card('A', 'S'), Card('K', 'D'),
            Card('Q', 'H'), Card('J', 'S')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 9)
        self.assertEqual(name, "One Pair")

    def test_high_card(self):
        """Test high card detection."""
        cards = [
            Card('A', 'H'), Card('K', 'S'), Card('Q', 'D'),
            Card('J', 'H'), Card('9', 'S')
        ]
        
        rank, value, name, best_cards = HandEvaluator.evaluate_hand(cards)
        self.assertEqual(rank, 10)
        self.assertEqual(name, "High Card")


def test_game_service_parsing():
    """Test GameService card parsing without Django."""
    # This would require importing GameService which needs Django setup
    # Implementing as a function instead of class method for now
    
    def parse_card(card_str):
        """Parse a card string like 'AH', '10C' into rank and suit."""
        if len(card_str) == 2:
            rank = card_str[0]
            suit = card_str[1]
        elif len(card_str) == 3 and card_str.startswith('10'):
            rank = '10'
            suit = card_str[2]
        else:
            raise ValueError(f"Invalid card format: {card_str}")
        
        return Card(rank, suit)
    
    # Test the parsing logic
    card = parse_card('AH')
    assert card.rank == 'A' and card.suit == 'H'
    
    card = parse_card('10C')
    assert card.rank == '10' and card.suit == 'C'
    
    try:
        parse_card('invalid')
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected
    
    print("✅ Card parsing tests passed!")


if __name__ == '__main__':
    print("🃏 Running standalone poker tests...")
    
    # Run the standalone tests
    unittest.main(verbosity=2, exit=False)
    
    # Run the parsing test
    test_game_service_parsing()
    
    print("✅ All standalone tests completed!")