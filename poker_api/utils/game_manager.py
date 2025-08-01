# poker_api/utils/game_manager.py
import random
from .card_utils import Deck, Card
from .hand_evaluator import HandEvaluator
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class PokerGameManager:
    """
    Manages the state and flow of a poker game.
    """
    
    GAME_PHASES = ['PREFLOP', 'FLOP', 'TURN', 'RIVER', 'SHOWDOWN']
    PLAYER_ACTIONS = ['FOLD', 'CHECK', 'CALL', 'BET', 'RAISE']
    
    def __init__(self, table, players):
        """
        Initialize a new poker game.
        
        Args:
            table: A PokerTable instance
            players: List of Player instances
        """
        self.table = table
        self.players = players
        self.deck = Deck()
        self.community_cards = []
        self.phase = None
        self.pot = Decimal('0')
        self.current_bet = Decimal('0')
        self.player_hands = {}  # Maps player ID to their hole cards
        self.player_bets = {}  # Maps player ID to their current bet in this round
        self.player_total_bets = {}  # Maps player ID to their total bet in this hand
        self.active_players = []  # Players still in the hand
        self.dealer_position = 0
        self.small_blind_position = 0
        self.big_blind_position = 0
        self.current_player_position = 0
        self.last_raiser_position = -1
        
    def start_game(self):
        """Start a new poker game."""
        logger.info(f"Starting new game with {len(self.players)} players")
        
        # Reset game state
        self.deck = Deck()
        self.deck.shuffle()
        self.community_cards = []
        self.phase = None
        self.pot = Decimal('0')
        self.current_bet = Decimal('0')
        self.player_hands = {}
        self.player_bets = {}
        self.player_total_bets = {}
        
        # Initialize active players (all players with chips)
        self.active_players = [p for p in self.players if p.stack > 0]
        logger.debug(f"Active players: {len(self.active_players)}/{len(self.players)}")
        
        if len(self.active_players) < 2:
            logger.error(f"Cannot start game with {len(self.active_players)} players")
            raise ValueError("Not enough players to start a game")
        
        # Assign dealer button (randomly for new game or move to next player)
        if self.dealer_position == 0:
            self.dealer_position = random.randint(0, len(self.active_players) - 1)
            logger.debug(f"Initial dealer position set to {self.dealer_position}")
        else:
            old_position = self.dealer_position
            self.dealer_position = (self.dealer_position + 1) % len(self.active_players)
            logger.debug(f"Dealer position moved from {old_position} to {self.dealer_position}")
        
        # Assign blind positions
        num_players = len(self.active_players)
        self.small_blind_position = (self.dealer_position + 1) % num_players
        self.big_blind_position = (self.dealer_position + 2) % num_players
        logger.debug(f"Blind positions - Small: {self.small_blind_position}, Big: {self.big_blind_position}")
        
        # Post blinds
        self._post_blinds()
        
        # Deal hole cards to each player
        self._deal_hole_cards()
        
        # Set phase to preflop
        self.phase = 'PREFLOP'
        
        # Set the current player (player after big blind)
        self.current_player_position = (self.big_blind_position + 1) % num_players
        logger.debug(f"First to act: position {self.current_player_position}")
        
        logger.info(f"Game started - Phase: {self.phase}, Pot: ${self.pot}")
        # Return initial game state
        return self._get_game_state()
    
    def _post_blinds(self):
        """Post the small and big blinds."""
        # Get blind amounts from table
        small_blind = self.table.small_blind
        big_blind = self.table.big_blind
        logger.debug(f"Posting blinds - Small: ${small_blind}, Big: ${big_blind}")
        
        # Post small blind
        small_blind_player = self.active_players[self.small_blind_position]
        small_blind_amount = min(small_blind, small_blind_player.stack)
        small_blind_player.stack -= small_blind_amount
        self.player_bets[small_blind_player.id] = small_blind_amount
        self.player_total_bets[small_blind_player.id] = small_blind_amount
        logger.debug(f"Small blind posted: Player {small_blind_player.id} - ${small_blind_amount}")
        
        # Post big blind
        big_blind_player = self.active_players[self.big_blind_position]
        big_blind_amount = min(big_blind, big_blind_player.stack)
        big_blind_player.stack -= big_blind_amount
        self.player_bets[big_blind_player.id] = big_blind_amount
        self.player_total_bets[big_blind_player.id] = big_blind_amount
        logger.debug(f"Big blind posted: Player {big_blind_player.id} - ${big_blind_amount}")
        
        # Set current bet to big blind
        self.current_bet = big_blind_amount
        # Last raiser is big blind
        self.last_raiser_position = self.big_blind_position
        logger.debug(f"Current bet set to ${big_blind_amount}")
    
    def _deal_hole_cards(self):
        """Deal two hole cards to each active player."""
        logger.debug(f"Dealing hole cards to {len(self.active_players)} players")
        for player in self.active_players:
            cards = self.deck.deal(2)
            self.player_hands[player.id] = cards
            logger.debug(f"Dealt to Player {player.id}: {[str(c) for c in cards]}")
    
    def _deal_community_cards(self, count):
        """Deal specified number of community cards."""
        new_cards = self.deck.deal(count)
        if isinstance(new_cards, list):
            self.community_cards.extend(new_cards)
            logger.debug(f"Dealt {count} community cards: {[str(c) for c in new_cards]}")
        else:
            self.community_cards.append(new_cards)
            logger.debug(f"Dealt 1 community card: {str(new_cards)}")
    
    def process_action(self, player_id, action, amount=0):
        """
        Process a player's action.
        
        Args:
            player_id: ID of the player taking action
            action: One of 'FOLD', 'CHECK', 'CALL', 'BET', 'RAISE'
            amount: Amount to bet or raise (only used for BET and RAISE actions)
        
        Returns:
            Updated game state
        """
        # Validate the player is the current player
        current_player = self.active_players[self.current_player_position]
        if current_player.id != player_id:
            logger.warning(f"Player {player_id} tried to act but it's Player {current_player.id}'s turn")
            raise ValueError("Not your turn to act")
        
        amount_str = f" ${amount}" if amount else ""
        logger.info(f"Processing action: Player {player_id} - {action}{amount_str}")
        
        # Convert amount to Decimal for consistency
        if amount:
            amount = Decimal(str(amount))
            
        # Process the action
        try:
            if action == 'FOLD':
                self._handle_fold(current_player)
            elif action == 'CHECK':
                self._handle_check(current_player)
            elif action == 'CALL':
                self._handle_call(current_player)
            elif action == 'BET':
                self._handle_bet(current_player, amount)
            elif action == 'RAISE':
                self._handle_raise(current_player, amount)
            else:
                logger.error(f"Invalid action: {action} from Player {player_id}")
                raise ValueError(f"Invalid action: {action}")
            
            logger.debug(f"Action processed successfully: Player {player_id} - {action}")
        except Exception as e:
            logger.error(f"Error processing action {action} for Player {player_id}: {str(e)}")
            raise
        
        # Move to the next player or next phase
        self._advance_game()
        
        # Return updated game state
        return self._get_game_state()
    
    def _handle_fold(self, player):
        """Handle a fold action."""
        logger.debug(f"Player {player.id} folding")
        
        # Remove player from active players
        self.active_players.remove(player)
        
        # If only one player left, they win
        remaining_players = len(self.active_players)
        logger.debug(f"After fold: {remaining_players} players remain")
        
        if remaining_players == 1:
            logger.info(f"Only one player remaining, ending hand")
            self._end_hand()
    
    def _handle_check(self, player):
        """Handle a check action."""
        current_bet = self.player_bets.get(player.id, Decimal('0'))
        if current_bet < self.current_bet:
            raise ValueError("Cannot check when there is a bet to call")
    
    def _handle_call(self, player):
        """Handle a call action."""
        current_bet = self.player_bets.get(player.id, Decimal('0'))
        call_amount = min(self.current_bet - current_bet, player.stack)
        
        logger.debug(f"Player {player.id} calling ${call_amount} (current bet: ${current_bet}, required: ${self.current_bet})")
        
        # Deduct from player's stack
        player.stack -= call_amount
        
        # Update player's bet
        self.player_bets[player.id] = current_bet + call_amount
        self.player_total_bets[player.id] = self.player_total_bets.get(player.id, Decimal('0')) + call_amount
    
    def _handle_bet(self, player, amount):
        """Handle a bet action."""
        # Check if there's already a bet
        if self.current_bet > 0:
            logger.warning(f"Player {player.id} cannot bet when current bet is ${self.current_bet}")
            raise ValueError("Cannot bet when there is already a bet, use 'RAISE' instead")
        
        # Validate bet amount
        min_bet = self.table.big_blind
        if amount < min_bet:
            logger.warning(f"Player {player.id} bet ${amount} below minimum ${min_bet}")
            raise ValueError(f"Bet must be at least the big blind: {min_bet}")
        
        # Cap bet at player's stack
        bet_amount = min(amount, player.stack)
        if bet_amount < amount:
            logger.debug(f"Player {player.id} bet capped at ${bet_amount} (wanted ${amount})")
        
        logger.debug(f"Player {player.id} betting ${bet_amount}")
        
        # Deduct from player's stack
        player.stack -= bet_amount
        
        # Update player's bet and current bet
        self.player_bets[player.id] = bet_amount
        self.player_total_bets[player.id] = self.player_total_bets.get(player.id, Decimal('0')) + bet_amount
        self.current_bet = bet_amount
        
        # Update last raiser
        self.last_raiser_position = self.current_player_position
    
    def _handle_raise(self, player, amount):
        """Handle a raise action."""
        # Check if there's a bet to raise
        if self.current_bet == 0:
            logger.warning(f"Player {player.id} cannot raise when no bet exists")
            raise ValueError("Cannot raise when there is no bet, use 'BET' instead")
        
        current_bet = self.player_bets.get(player.id, Decimal('0'))
        raise_amount = amount - current_bet
        
        # Validate raise amount
        min_raise = self.current_bet * 2
        if amount < min_raise:
            logger.warning(f"Player {player.id} raise to ${amount} below minimum ${min_raise}")
            raise ValueError(f"Raise must be at least double the current bet: {min_raise}")
        
        # Cap raise at player's stack
        available_raise = min(raise_amount, player.stack)
        if available_raise < raise_amount:
            logger.debug(f"Player {player.id} raise capped at ${available_raise} (wanted ${raise_amount})")
        
        total_bet = current_bet + available_raise
        logger.debug(f"Player {player.id} raising ${available_raise} to total ${total_bet}")
        
        # Deduct from player's stack
        player.stack -= available_raise
        
        # Update player's bet and current bet
        self.player_bets[player.id] = total_bet
        self.player_total_bets[player.id] = self.player_total_bets.get(player.id, Decimal('0')) + available_raise
        self.current_bet = total_bet
        
        # Update last raiser
        self.last_raiser_position = self.current_player_position
    
    def _advance_game(self):
        """Advance the game to the next player or phase."""
        # If only one player left, end the hand
        if len(self.active_players) == 1:
            self._end_hand()
            return
        
        # Move to the next player
        self.current_player_position = (self.current_player_position + 1) % len(self.active_players)
        
        # Check if we've completed the betting round
        # This happens when we've come back to the last raiser or everyone has acted
        if self.current_player_position == self.last_raiser_position or self.last_raiser_position == -1:
            # Move to the next phase
            self._move_to_next_phase()
    
    def _move_to_next_phase(self):
        """Move to the next phase of the game."""
        logger.info(f"Moving from {self.phase} to next phase")
        
        # Add all bets to the pot
        total_bets = sum(self.player_bets.values())
        self.pot += total_bets
        logger.debug(f"Added ${total_bets} to pot, new pot: ${self.pot}")
        
        # Reset bets
        self.player_bets = {}
        self.current_bet = Decimal('0')
        self.last_raiser_position = -1
        
        # Determine next phase
        if self.phase == 'PREFLOP':
            self.phase = 'FLOP'
            # Deal the flop (3 community cards)
            self._deal_community_cards(3)
            logger.info(f"Flop dealt: {[str(c) for c in self.community_cards[-3:]]}")
        elif self.phase == 'FLOP':
            self.phase = 'TURN'
            # Deal the turn (1 community card)
            self._deal_community_cards(1)
            logger.info(f"Turn dealt: {str(self.community_cards[-1])}")
        elif self.phase == 'TURN':
            self.phase = 'RIVER'
            # Deal the river (1 community card)
            self._deal_community_cards(1)
            logger.info(f"River dealt: {str(self.community_cards[-1])}")
        elif self.phase == 'RIVER':
            self.phase = 'SHOWDOWN'
            logger.info(f"Moving to showdown")
            # Determine the winner
            self._showdown()
        elif self.phase == 'SHOWDOWN':
            # Start a new hand
            logger.info(f"Starting new hand")
            self.start_game()
        
        # Set current player to the first active player after the dealer
        if self.phase != 'SHOWDOWN':
            self.current_player_position = (self.dealer_position + 1) % len(self.active_players)
            logger.debug(f"First to act in {self.phase}: position {self.current_player_position}")
    
    def _showdown(self):
        """Determine the winner(s) at showdown."""
        logger.info(f"Starting showdown with {len(self.active_players)} players")
        
        # Evaluate each player's best 5-card hand
        player_best_hands = {}
        for player in self.active_players:
            # Combine hole cards and community cards
            all_cards = self.player_hands[player.id] + self.community_cards
            # Evaluate best hand
            hand_rank, hand_value, hand_name, best_cards = HandEvaluator.evaluate_hand(all_cards)
            player_best_hands[player.id] = (hand_rank, hand_value, hand_name, player)
            logger.debug(f"Player {player.id} has {hand_name} (rank {hand_rank})")
        
        # Sort by hand strength (lowest rank is best, then compare values)
        sorted_hands = sorted(player_best_hands.values(), key=lambda x: (x[0], x[1]))
        
        # Identify winners (players with the same best hand)
        best_hand = sorted_hands[0]
        winners = [player for rank, value, name, player in sorted_hands if (rank, value) == (best_hand[0], best_hand[1])]
        
        # Distribute pot evenly among winners
        pot_amount = self.pot
        win_amount = pot_amount / Decimal(len(winners))
        
        if len(winners) == 1:
            logger.info(f"Winner: Player {winners[0].id} with {best_hand[2]} wins ${pot_amount}")
        else:
            winner_ids = [str(w.id) for w in winners]
            logger.info(f"Split pot: Players {', '.join(winner_ids)} each win ${win_amount} with {best_hand[2]}")
        
        for winner in winners:
            winner.stack += win_amount
        
        # Reset pot
        self.pot = Decimal('0')
    
    def _end_hand(self):
        """End the current hand when only one player remains."""
        # Award pot to the last remaining player
        if self.active_players:
            winner = self.active_players[0]
            pot_amount = self.pot
            winner.stack += pot_amount
            logger.info(f"Hand ended: Player {winner.id} wins ${pot_amount} (all others folded)")
        
        # Reset pot
        self.pot = Decimal('0')
        
        # Move to showdown phase (which will start a new hand)
        self.phase = 'SHOWDOWN'
    
    def _get_game_state(self):
        """Get the current state of the game."""
        return {
            'table_id': self.table.id,
            'phase': self.phase,
            'pot': self.pot,
            'current_bet': self.current_bet,
            'community_cards': [str(card) for card in self.community_cards],
            'active_players': [p.id for p in self.active_players],
            'dealer_position': self.dealer_position,
            'current_player': self.active_players[self.current_player_position].id if self.active_players else None,
            'player_bets': self.player_bets,
            'player_total_bets': self.player_total_bets,
            'player_stacks': {p.id: p.stack for p in self.players},
            # Only include hole cards for the requesting player in a real API
            'player_hands': {p_id: [str(card) for card in cards] for p_id, cards in self.player_hands.items()}
        }