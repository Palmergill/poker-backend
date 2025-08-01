# poker_api/utils/hand_evaluator.py
from poker_api.utils.card_utils import Card
import logging

logger = logging.getLogger(__name__)


class HandEvaluator:
    """
    Evaluates poker hands and determines their ranking.
    
    Hand Rankings (highest to lowest):
    1. Royal Flush
    2. Straight Flush
    3. Four of a Kind
    4. Full House
    5. Flush
    6. Straight
    7. Three of a Kind
    8. Two Pair
    9. One Pair
    10. High Card
    """
    
    @staticmethod
    def evaluate_hand(cards):
        """
        Evaluates a hand of 5-7 cards and returns a tuple of (hand_rank, hand_value, hand_name, best_hand_cards)
        Lower hand_rank value means stronger hand (1 is best, 10 is worst)
        hand_value is used to break ties within the same hand_rank
        best_hand_cards is a list of the 5 cards that make up the best hand
        """
        if len(cards) < 5:
            logger.error(f"Cannot evaluate hand with {len(cards)} cards, need at least 5")
            raise ValueError("Not enough cards to evaluate a hand")
        
        logger.debug(f"Evaluating hand with {len(cards)} cards: {[str(c) for c in cards]}")
            
        # Make a copy of the cards to avoid modifying the original
        cards = sorted(cards, reverse=True, key=lambda card: card.rank_value)
        
        # Check for each hand type from best to worst
        # Royal Flush
        royal_flush = HandEvaluator._check_royal_flush(cards)
        if royal_flush:
            logger.debug(f"Found Royal Flush: {[str(c) for c in royal_flush[0]]}")
            return (1, royal_flush[1], "Royal Flush", royal_flush[0])
            
        # Straight Flush
        straight_flush = HandEvaluator._check_straight_flush(cards)
        if straight_flush:
            logger.debug(f"Found Straight Flush: {[str(c) for c in straight_flush[0]]}")
            return (2, straight_flush[1], "Straight Flush", straight_flush[0])
            
        # Four of a Kind
        four_kind = HandEvaluator._check_four_of_a_kind(cards)
        if four_kind:
            logger.debug(f"Found Four of a Kind: {[str(c) for c in four_kind[0]]}")
            return (3, four_kind[1], "Four of a Kind", four_kind[0])
            
        # Full House
        full_house = HandEvaluator._check_full_house(cards)
        if full_house:
            logger.debug(f"Found Full House: {[str(c) for c in full_house[0]]}")
            return (4, full_house[1], "Full House", full_house[0])
            
        # Flush
        flush = HandEvaluator._check_flush(cards)
        if flush:
            logger.debug(f"Found Flush: {[str(c) for c in flush[0]]}")
            return (5, flush[1], "Flush", flush[0])
            
        # Straight
        straight = HandEvaluator._check_straight(cards)
        if straight:
            logger.debug(f"Found Straight: {[str(c) for c in straight[0]]}")
            return (6, straight[1], "Straight", straight[0])
            
        # Three of a Kind
        three_kind = HandEvaluator._check_three_of_a_kind(cards)
        if three_kind:
            logger.debug(f"Found Three of a Kind: {[str(c) for c in three_kind[0]]}")
            return (7, three_kind[1], "Three of a Kind", three_kind[0])
            
        # Two Pair
        two_pair = HandEvaluator._check_two_pair(cards)
        if two_pair:
            logger.debug(f"Found Two Pair: {[str(c) for c in two_pair[0]]}")
            return (8, two_pair[1], "Two Pair", two_pair[0])
            
        # One Pair
        one_pair = HandEvaluator._check_one_pair(cards)
        if one_pair:
            logger.debug(f"Found One Pair: {[str(c) for c in one_pair[0]]}")
            return (9, one_pair[1], "One Pair", one_pair[0])
            
        # High Card
        sorted_cards = sorted(cards, key=lambda card: card.rank_value, reverse=True)
        top_five = sorted_cards[:5]
        logger.debug(f"Found High Card: {[str(c) for c in top_five]}")
        return (10, HandEvaluator._get_high_card_value(cards), "High Card", top_five)
    
    @staticmethod
    def _check_royal_flush(cards):
        """Check for Royal Flush: A, K, Q, J, 10 of the same suit"""
        # First check if we have a flush
        flush = HandEvaluator._check_flush(cards)
        if not flush:
            return None
            
        # Check if the flush contains A, K, Q, J, 10
        flush_cards = flush[0]
        royal_ranks = {'A', 'K', 'Q', 'J', '10'}
        if all(card.rank in royal_ranks for card in flush_cards[:5]):
            return (flush_cards[:5], (14,))  # Value of the Ace
            
        return None
    
    @staticmethod
    def _check_straight_flush(cards):
        """Check for Straight Flush: Five consecutive cards of the same suit"""
        # Group cards by suit
        suits = {}
        for card in cards:
            if card.suit not in suits:
                suits[card.suit] = []
            suits[card.suit].append(card)
            
        # Check each suit group for a straight
        for suit, suited_cards in suits.items():
            if len(suited_cards) >= 5:
                straight = HandEvaluator._check_straight(sorted(suited_cards, reverse=True, key=lambda card: card.rank_value))
                if straight:
                    return (straight[0], straight[1])
                    
        return None
    
    @staticmethod
    def _check_four_of_a_kind(cards):
        """Check for Four of a Kind: Four cards of the same rank"""
        # Group cards by rank
        ranks = {}
        for card in cards:
            if card.rank not in ranks:
                ranks[card.rank] = []
            ranks[card.rank].append(card)
            
        # Find four of a kind
        for rank, cards_of_rank in sorted(ranks.items(), key=lambda x: Card.RANKS[x[0]], reverse=True):
            if len(cards_of_rank) == 4:
                four_kind = cards_of_rank
                # Find the highest kicker
                kickers = [card for card in cards if card.rank != rank]
                kickers.sort(key=lambda card: card.rank_value, reverse=True)
                
                # Return the four of a kind plus the highest kicker
                return (four_kind + kickers[:1], (Card.RANKS[rank], kickers[0].rank_value if kickers else 0))
                
        return None
    
    @staticmethod
    def _check_full_house(cards):
        """Check for Full House: Three cards of one rank and two of another"""
        # Group cards by rank
        ranks = {}
        for card in cards:
            if card.rank not in ranks:
                ranks[card.rank] = []
            ranks[card.rank].append(card)
            
        # Find three of a kind and pair
        three_kind_rank = None
        pair_rank = None
        
        # Look for the highest three of a kind
        for rank, cards_of_rank in sorted(ranks.items(), key=lambda x: Card.RANKS[x[0]], reverse=True):
            if len(cards_of_rank) >= 3 and three_kind_rank is None:
                three_kind_rank = rank
                
        # If we found three of a kind, look for the highest pair
        if three_kind_rank is not None:
            for rank, cards_of_rank in sorted(ranks.items(), key=lambda x: Card.RANKS[x[0]], reverse=True):
                if rank != three_kind_rank and len(cards_of_rank) >= 2 and pair_rank is None:
                    pair_rank = rank
                    
        if three_kind_rank is not None and pair_rank is not None:
            three_kind = ranks[three_kind_rank][:3]
            pair = ranks[pair_rank][:2]
            return (three_kind + pair, (Card.RANKS[three_kind_rank], Card.RANKS[pair_rank]))
            
        return None
    
    @staticmethod
    def _check_flush(cards):
        """Check for Flush: Five cards of the same suit"""
        # Group cards by suit
        suits = {}
        for card in cards:
            if card.suit not in suits:
                suits[card.suit] = []
            suits[card.suit].append(card)
            
        # Check if any suit has at least 5 cards
        for suit, suited_cards in suits.items():
            if len(suited_cards) >= 5:
                # Sort by rank and take the highest 5
                suited_cards.sort(key=lambda card: card.rank_value, reverse=True)
                flush_cards = suited_cards[:5]
                # Value is the values of all 5 cards
                value = tuple(card.rank_value for card in flush_cards)
                return (flush_cards, value)
                
        return None
    
    @staticmethod
    def _check_straight(cards):
        """Check for Straight: Five consecutive cards of any suit"""
        # Remove duplicates by rank
        unique_ranks = {}
        for card in cards:
            if card.rank_value not in unique_ranks or card.rank_value > unique_ranks[card.rank_value].rank_value:
                unique_ranks[card.rank_value] = card
                
        # Sort unique rank cards
        unique_cards = sorted(unique_ranks.values(), key=lambda card: card.rank_value, reverse=True)
        
        # Check for A-5-4-3-2 straight
        if len(unique_cards) >= 5:
            # Check if we have an ace
            has_ace = any(card.rank == 'A' for card in unique_cards)
            
            # If we have an ace, check for 5-4-3-2
            if has_ace:
                low_straight = True
                for rank_value in range(2, 6):
                    if not any(card.rank_value == rank_value for card in unique_cards):
                        low_straight = False
                        break
                        
                if low_straight:
                    # Find the cards for the straight
                    straight_cards = [card for card in unique_cards if card.rank_value in [14, 5, 4, 3, 2]]
                    # For A-5-4-3-2 straight, the value is 5 (not A)
                    return (straight_cards, (5,))
        
        # Check for normal straights
        for i in range(len(unique_cards) - 4):
            if unique_cards[i].rank_value - unique_cards[i+4].rank_value == 4:
                straight_cards = unique_cards[i:i+5]
                # Value is the highest card
                return (straight_cards, (straight_cards[0].rank_value,))
                
        return None
    
    @staticmethod
    def _check_three_of_a_kind(cards):
        """Check for Three of a Kind: Three cards of the same rank"""
        # Group cards by rank
        ranks = {}
        for card in cards:
            if card.rank not in ranks:
                ranks[card.rank] = []
            ranks[card.rank].append(card)
            
        # Find three of a kind
        for rank, cards_of_rank in sorted(ranks.items(), key=lambda x: Card.RANKS[x[0]], reverse=True):
            if len(cards_of_rank) == 3:
                three_kind = cards_of_rank
                # Find the highest kickers
                kickers = [card for card in cards if card.rank != rank]
                kickers.sort(key=lambda card: card.rank_value, reverse=True)
                
                # Return the three of a kind plus the two highest kickers
                return (three_kind + kickers[:2], (Card.RANKS[rank], kickers[0].rank_value if kickers else 0, kickers[1].rank_value if len(kickers) > 1 else 0))
                
        return None
    
    @staticmethod
    def _check_two_pair(cards):
        """Check for Two Pair: Two cards of one rank and two of another"""
        # Group cards by rank
        ranks = {}
        for card in cards:
            if card.rank not in ranks:
                ranks[card.rank] = []
            ranks[card.rank].append(card)
            
        # Find pairs
        pairs = []
        for rank, cards_of_rank in ranks.items():
            if len(cards_of_rank) >= 2:
                pairs.append((rank, cards_of_rank[:2]))
                
        # Sort pairs by rank (highest first)
        pairs.sort(key=lambda x: Card.RANKS[x[0]], reverse=True)
        
        if len(pairs) >= 2:
            high_pair = pairs[0][1]
            second_pair = pairs[1][1]
            
            # Find the highest kicker
            kickers = [card for card in cards if card.rank != pairs[0][0] and card.rank != pairs[1][0]]
            kickers.sort(key=lambda card: card.rank_value, reverse=True)
            
            # Return the two pairs plus the highest kicker
            return (high_pair + second_pair + kickers[:1], (Card.RANKS[pairs[0][0]], Card.RANKS[pairs[1][0]], kickers[0].rank_value if kickers else 0))
            
        return None
    
    @staticmethod
    def _check_one_pair(cards):
        """Check for One Pair: Two cards of the same rank"""
        # Group cards by rank
        ranks = {}
        for card in cards:
            if card.rank not in ranks:
                ranks[card.rank] = []
            ranks[card.rank].append(card)
            
        # Find a pair
        for rank, cards_of_rank in sorted(ranks.items(), key=lambda x: Card.RANKS[x[0]], reverse=True):
            if len(cards_of_rank) == 2:
                pair = cards_of_rank
                # Find the highest kickers
                kickers = [card for card in cards if card.rank != rank]
                kickers.sort(key=lambda card: card.rank_value, reverse=True)
                
                # Return the pair plus the three highest kickers
                return (pair + kickers[:3], (Card.RANKS[rank], kickers[0].rank_value if kickers else 0, 
                       kickers[1].rank_value if len(kickers) > 1 else 0, kickers[2].rank_value if len(kickers) > 2 else 0))
                
        return None
    
    @staticmethod
    def _get_high_card_value(cards):
        """Return the value of a high card hand"""
        # Sort cards by rank (highest first)
        sorted_cards = sorted(cards, key=lambda card: card.rank_value, reverse=True)
        # Take the top 5 cards
        top_five = sorted_cards[:5]
        # Return a tuple of their values
        return tuple(card.rank_value for card in top_five)
