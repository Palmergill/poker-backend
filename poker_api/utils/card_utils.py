# poker_api/utils/card_utils.py
import logging

logger = logging.getLogger(__name__)

class Card:
    """Represents a playing card with rank and suit."""
    SUITS = {'S': 'Spades', 'H': 'Hearts', 'D': 'Diamonds', 'C': 'Clubs'}
    RANKS = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    
    def __init__(self, rank, suit):
        """Initialize a card with rank and suit."""
        self.rank = rank
        self.suit = suit
        self.rank_value = self.RANKS[rank]
    
    def __str__(self):
        """Return string representation of the card."""
        return f"{self.rank}{self.suit}"
    
    def __repr__(self):
        """Return string representation for debugging."""
        return self.__str__()
    
    def __eq__(self, other):
        """Check if two cards are equal by rank and suit."""
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit
    
    def __lt__(self, other):
        """Compare cards by rank value for sorting."""
        return self.rank_value < other.rank_value

class Deck:
    """Represents a standard 52-card deck."""
    def __init__(self):
        """Initialize a new deck of cards."""
        self.cards = []
        self.reset()
    
    def reset(self):
        """Reset deck to full 52 cards."""
        self.cards = []
        for suit in Card.SUITS:
            for rank in Card.RANKS:
                self.cards.append(Card(rank, suit))
        logger.debug(f"Deck reset to {len(self.cards)} cards")
    
    def shuffle(self):
        """Randomly shuffle the deck."""
        import random
        cards_before = len(self.cards)
        random.shuffle(self.cards)
        logger.debug(f"Shuffled deck with {cards_before} cards")
    
    def deal(self, num_cards=1):
        """Deal specified number of cards from the deck."""
        if num_cards > len(self.cards):
            logger.error(f"Cannot deal {num_cards} cards, only {len(self.cards)} remaining in deck")
            raise ValueError("Not enough cards in deck")
        
        dealt_cards = []
        for _ in range(num_cards):
            dealt_cards.append(self.cards.pop())
        
        logger.debug(f"Dealt {num_cards} cards: {[str(card) for card in dealt_cards]}")
        return dealt_cards if num_cards > 1 else dealt_cards[0]
    
    def __len__(self):
        """Return number of cards remaining in deck."""
        return len(self.cards)