# poker_api/utils/bot_engine.py
# 
# AI decision engine for poker bot players.
# This module contains the logic for bots to make poker decisions based on
# their configuration, hand strength, position, and game situation.

import random
import logging
from decimal import Decimal
from ..utils.hand_evaluator import HandEvaluator
from ..utils.card_utils import Card

logger = logging.getLogger(__name__)

class BotDecisionEngine:
    """
    AI decision engine for poker bots.
    
    This class implements poker strategy algorithms for different difficulty levels
    and play styles. Bots make decisions based on:
    - Hand strength evaluation
    - Position at the table
    - Pot odds calculation
    - Betting patterns and opponent behavior
    - Configured play style and aggression level
    """
    
    def __init__(self, bot_player, game, player_game):
        """
        Initialize the decision engine for a specific bot.
        
        Args:
            bot_player: BotPlayer instance with configuration
            game: Current Game instance
            player_game: PlayerGame instance for this bot
        """
        self.bot_player = bot_player
        self.game = game
        self.player_game = player_game
        self.difficulty = bot_player.difficulty
        self.play_style = bot_player.play_style
        self.aggression_factor = bot_player.aggression_factor
        self.bluff_frequency = bot_player.bluff_frequency
        
        logger.debug(f"BotDecisionEngine initialized for {bot_player.player.user.username} "
                    f"({self.difficulty}/{self.play_style})")
    
    def make_decision(self, valid_actions):
        """
        Make a poker decision based on the current game state.
        
        Args:
            valid_actions: List of valid action types ('FOLD', 'CHECK', 'CALL', 'BET', 'RAISE')
        
        Returns:
            Tuple of (action_type, amount) where amount is 0 for non-betting actions
        """
        logger.debug(f"Bot {self.player_game.player.user.username} making decision. "
                    f"Valid actions: {valid_actions}")
        
        # Get current hand strength
        hand_strength = self._evaluate_hand_strength()
        position_factor = self._get_position_factor()
        pot_odds = self._calculate_pot_odds()
        
        logger.debug(f"Hand strength: {hand_strength:.2f}, Position factor: {position_factor:.2f}, "
                    f"Pot odds: {pot_odds:.2f}")
        
        # Determine if bot should bluff
        should_bluff = self._should_bluff(hand_strength)
        
        # Make decision based on difficulty level
        if self.difficulty == 'BASIC':
            return self._make_basic_decision(valid_actions, hand_strength, should_bluff)
        elif self.difficulty == 'INTERMEDIATE':
            return self._make_intermediate_decision(valid_actions, hand_strength, position_factor, pot_odds, should_bluff)
        else:  # ADVANCED
            return self._make_advanced_decision(valid_actions, hand_strength, position_factor, pot_odds, should_bluff)
    
    def _evaluate_hand_strength(self):
        """
        Evaluate the strength of the bot's current hand.
        
        Returns:
            Float between 0.0 (worst) and 1.0 (best) representing hand strength
        """
        if not self.player_game.get_cards():
            return 0.0
        
        # Convert card strings to Card objects
        hole_cards = [Card(card[:-1], card[-1]) for card in self.player_game.get_cards()]
        community_cards = [Card(card[:-1], card[-1]) for card in self.game.get_community_cards()]
        
        # Pre-flop evaluation (only hole cards)
        if not community_cards:
            return self._evaluate_preflop_strength(hole_cards)
        
        # Post-flop evaluation with community cards
        all_cards = hole_cards + community_cards
        if len(all_cards) >= 5:
            hand_rank, hand_value, hand_name, best_cards = HandEvaluator.evaluate_hand(all_cards)
            # Convert hand rank to strength (lower rank = stronger hand)
            # Normalize to 0.0-1.0 scale
            strength = 1.0 - (hand_rank - 1) / 9.0  # 9 possible hand ranks (1-10, excluding royal flush)
            
            # Add some randomness for uncertainty
            randomness = random.uniform(-0.05, 0.05)
            strength = max(0.0, min(1.0, strength + randomness))
            
            logger.debug(f"Hand evaluation: {hand_name} (rank {hand_rank}) -> strength {strength:.2f}")
            return strength
        
        return self._evaluate_preflop_strength(hole_cards)
    
    def _evaluate_preflop_strength(self, hole_cards):
        """
        Evaluate pre-flop hand strength using simplified hand rankings.
        
        Args:
            hole_cards: List of 2 Card objects
        
        Returns:
            Float between 0.0 and 1.0 representing hand strength
        """
        if len(hole_cards) != 2:
            return 0.0
        
        card1, card2 = hole_cards
        rank1, rank2 = card1.rank_value, card2.rank_value
        is_suited = card1.suit == card2.suit
        is_pair = rank1 == rank2
        
        # High pairs
        if is_pair and rank1 >= 10:  # TT+
            return random.uniform(0.8, 0.95)
        elif is_pair and rank1 >= 7:  # 77-99
            return random.uniform(0.6, 0.8)
        elif is_pair:  # 22-66
            return random.uniform(0.4, 0.6)
        
        # High cards
        high_card = max(rank1, rank2)
        low_card = min(rank1, rank2)
        
        if high_card == 14:  # Ace high
            if low_card >= 10:  # AK, AQ, AJ, AT
                return random.uniform(0.7, 0.9) if is_suited else random.uniform(0.6, 0.8)
            elif low_card >= 7:  # A9-A7
                return random.uniform(0.5, 0.7) if is_suited else random.uniform(0.4, 0.6)
            else:  # A6-A2
                return random.uniform(0.3, 0.5) if is_suited else random.uniform(0.2, 0.4)
        
        elif high_card == 13:  # King high
            if low_card >= 11:  # KQ, KJ
                return random.uniform(0.6, 0.8) if is_suited else random.uniform(0.5, 0.7)
            elif low_card >= 9:  # KT, K9
                return random.uniform(0.4, 0.6) if is_suited else random.uniform(0.3, 0.5)
        
        elif high_card >= 11 and low_card >= 10:  # QJ, QT, JT
            return random.uniform(0.5, 0.7) if is_suited else random.uniform(0.4, 0.6)
        
        # Connected cards (straights potential)
        if abs(rank1 - rank2) == 1:  # Connected
            return random.uniform(0.3, 0.5) if is_suited else random.uniform(0.2, 0.4)
        
        # Default for weak hands
        return random.uniform(0.1, 0.3)
    
    def _get_position_factor(self):
        """
        Calculate position factor (0.0 = worst position, 1.0 = best position).
        
        Returns:
            Float representing position strength
        """
        # Get all active players to determine relative position
        from ..models import PlayerGame
        active_players = PlayerGame.objects.filter(
            game=self.game, 
            is_active=True,
            cashed_out=False,
            left_table=False
        ).order_by('seat_position')
        
        if len(active_players) <= 2:
            return 0.5  # Heads up, position less critical
        
        # Find our position relative to dealer
        dealer_pos = self.game.dealer_position
        our_pos = self.player_game.seat_position
        num_players = len(active_players)
        
        # Calculate position relative to dealer (0 = on dealer, higher = later position)
        relative_pos = (our_pos - dealer_pos) % num_players
        
        # Later position is better (more information)
        position_factor = relative_pos / (num_players - 1)
        
        return position_factor
    
    def _calculate_pot_odds(self):
        """
        Calculate pot odds to determine if calling is profitable.
        
        Returns:
            Float representing pot odds ratio
        """
        pot_size = float(self.game.pot)
        call_amount = float(self.game.current_bet - self.player_game.current_bet)
        
        if call_amount <= 0:
            return float('inf')  # No cost to continue
        
        if pot_size <= 0:
            return 0.0
        
        # Pot odds = pot size / call amount
        pot_odds = pot_size / call_amount
        return pot_odds
    
    def _should_bluff(self, hand_strength):
        """
        Determine if the bot should bluff based on configuration and situation.
        
        Args:
            hand_strength: Current hand strength (0.0-1.0)
        
        Returns:
            Boolean indicating whether to bluff
        """
        # Only bluff with weak hands
        if hand_strength > 0.3:
            return False
        
        # Random chance based on bluff frequency
        return random.random() < self.bluff_frequency
    
    def _make_basic_decision(self, valid_actions, hand_strength, should_bluff):
        """
        Make decision using basic strategy (tight/aggressive).
        
        Args:
            valid_actions: List of valid actions
            hand_strength: Hand strength (0.0-1.0)
            should_bluff: Whether to attempt a bluff
        
        Returns:
            Tuple of (action_type, amount)
        """
        if should_bluff and 'BET' in valid_actions:
            bet_amount = self._calculate_bet_size(0.5)  # Small bluff bet
            return ('BET', bet_amount)
        
        if hand_strength >= 0.7:  # Strong hand
            if 'RAISE' in valid_actions:
                raise_amount = self._calculate_bet_size(self.aggression_factor)
                return ('RAISE', raise_amount)
            elif 'BET' in valid_actions:
                bet_amount = self._calculate_bet_size(self.aggression_factor)
                return ('BET', bet_amount)
            elif 'CALL' in valid_actions:
                return ('CALL', 0)
        
        elif hand_strength >= 0.4:  # Medium hand
            if 'CHECK' in valid_actions:
                return ('CHECK', 0)
            elif 'CALL' in valid_actions and self._calculate_pot_odds() > 2.0:
                return ('CALL', 0)
        
        # Weak hand or unfavorable odds
        if 'CHECK' in valid_actions:
            return ('CHECK', 0)
        else:
            return ('FOLD', 0)
    
    def _make_intermediate_decision(self, valid_actions, hand_strength, position_factor, pot_odds, should_bluff):
        """
        Make decision using intermediate strategy (considers position and pot odds).
        """
        # Adjust hand strength based on position
        adjusted_strength = hand_strength + (position_factor - 0.5) * 0.2
        adjusted_strength = max(0.0, min(1.0, adjusted_strength))
        
        if should_bluff and position_factor > 0.6 and 'BET' in valid_actions:
            bet_amount = self._calculate_bet_size(0.6)
            return ('BET', bet_amount)
        
        if adjusted_strength >= 0.6:  # Strong hand
            if 'RAISE' in valid_actions:
                raise_amount = self._calculate_bet_size(self.aggression_factor * (1 + position_factor * 0.3))
                return ('RAISE', raise_amount)
            elif 'BET' in valid_actions:
                bet_amount = self._calculate_bet_size(self.aggression_factor)
                return ('BET', bet_amount)
            elif 'CALL' in valid_actions:
                return ('CALL', 0)
        
        elif adjusted_strength >= 0.3:  # Medium hand
            if pot_odds > 3.0 and 'CALL' in valid_actions:
                return ('CALL', 0)
            elif 'CHECK' in valid_actions:
                return ('CHECK', 0)
            elif pot_odds > 2.0 and 'CALL' in valid_actions:
                return ('CALL', 0)
        
        # Weak hand
        if 'CHECK' in valid_actions:
            return ('CHECK', 0)
        else:
            return ('FOLD', 0)
    
    def _make_advanced_decision(self, valid_actions, hand_strength, position_factor, pot_odds, should_bluff):
        """
        Make decision using advanced strategy (includes sophisticated bluffing and reading).
        """
        # Advanced position adjustment
        adjusted_strength = hand_strength + (position_factor - 0.5) * 0.3
        
        # Consider play style more heavily in advanced mode
        if self.play_style == 'LOOSE_AGGRESSIVE':
            adjusted_strength += 0.1
        elif self.play_style == 'TIGHT_PASSIVE':
            adjusted_strength -= 0.1
        
        adjusted_strength = max(0.0, min(1.0, adjusted_strength))
        
        # Advanced bluffing based on position and opponents
        if should_bluff and position_factor > 0.7:
            if 'RAISE' in valid_actions and random.random() < 0.3:
                raise_amount = self._calculate_bet_size(0.8)
                return ('RAISE', raise_amount)
            elif 'BET' in valid_actions:
                bet_amount = self._calculate_bet_size(0.7)
                return ('BET', bet_amount)
        
        if adjusted_strength >= 0.7:  # Very strong hand
            aggression_multiplier = 1.0 + position_factor * 0.5
            if 'RAISE' in valid_actions:
                raise_amount = self._calculate_bet_size(self.aggression_factor * aggression_multiplier)
                return ('RAISE', raise_amount)
            elif 'BET' in valid_actions:
                bet_amount = self._calculate_bet_size(self.aggression_factor * aggression_multiplier)
                return ('BET', bet_amount)
            elif 'CALL' in valid_actions:
                return ('CALL', 0)
        
        elif adjusted_strength >= 0.5:  # Good hand
            if pot_odds > 2.5 and 'CALL' in valid_actions:
                return ('CALL', 0)
            elif position_factor > 0.6 and 'BET' in valid_actions:
                bet_amount = self._calculate_bet_size(self.aggression_factor * 0.7)
                return ('BET', bet_amount)
            elif 'CHECK' in valid_actions:
                return ('CHECK', 0)
        
        elif adjusted_strength >= 0.25:  # Marginal hand
            if pot_odds > 4.0 and 'CALL' in valid_actions:
                return ('CALL', 0)
            elif 'CHECK' in valid_actions:
                return ('CHECK', 0)
        
        # Weak hand
        if 'CHECK' in valid_actions:
            return ('CHECK', 0)
        else:
            return ('FOLD', 0)
    
    def _calculate_bet_size(self, aggression_multiplier):
        """
        Calculate appropriate bet size based on pot size and aggression.
        For raises, ensures the total amount is at least double the current bet.
        
        Args:
            aggression_multiplier: Factor to adjust bet size (0.0-2.0)
        
        Returns:
            Decimal bet amount (total amount to bet, not just the raise)
        """
        pot_size = self.game.pot
        stack_size = self.player_game.stack
        big_blind = self.game.table.big_blind
        current_bet = self.game.current_bet
        
        # Base bet size as fraction of pot
        base_bet_fraction = 0.5 + (aggression_multiplier * 0.3)
        base_bet = pot_size * Decimal(str(base_bet_fraction))
        
        # For raises, minimum is double the current bet
        if current_bet > 0:
            min_bet = current_bet * 2
        else:
            # For bets (no existing bet), minimum is big blind
            min_bet = big_blind
        
        # Maximum bet is our stack (all-in)
        max_bet = stack_size
        
        # Calculate final bet size
        bet_size = max(min_bet, min(base_bet, max_bet))
        
        # Round to nearest cent
        bet_size = bet_size.quantize(Decimal('0.01'))
        
        logger.debug(f"Calculated bet size: ${bet_size} (aggression: {aggression_multiplier:.2f}, "
                    f"pot: ${pot_size}, stack: ${stack_size})")
        
        return bet_size
    
    def get_thinking_time(self):
        """
        Get random thinking time for this bot.
        
        Returns:
            Float seconds the bot should "think" before acting
        """
        thinking_time = random.uniform(self.bot_player.thinking_time_min, self.bot_player.thinking_time_max)
        return thinking_time