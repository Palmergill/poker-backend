# poker_api/services/game_service.py
# 
# Core game logic service for Texas Hold'em poker games.
# This service handles all game state management, betting logic, and hand progression.
# 
# Key Features:
# - Game creation and player management
# - Betting round processing with delayed pot collection
# - Hand evaluation and winner determination
# - WebSocket notifications for real-time updates
# - Transaction-safe operations for data consistency

from django.db import transaction
from ..models import Game, PlayerGame, GameAction, Player, HandHistory, BotPlayer
from ..utils.card_utils import Deck, Card
from ..utils.hand_evaluator import HandEvaluator
from ..utils.bot_engine import BotDecisionEngine
import random
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from decimal import Decimal
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import logging

logger = logging.getLogger(__name__)

class GameService:
    """
    Central service for managing Texas Hold'em poker games.
    
    This service implements the complete poker game flow including:
    - Game initialization with blinds and card dealing
    - Player action processing (fold, check, call, bet, raise)
    - Betting round management with proper pot collection timing
    - Hand progression through pre-flop, flop, turn, river, showdown
    - Winner determination and chip distribution
    - Real-time updates via WebSocket broadcasting
    
    Key Design Decisions:
    - Bets are collected to pot only when betting rounds end (not immediately)
    - All database operations are wrapped in transactions for consistency
    - WebSocket notifications keep all players synchronized
    - Comprehensive logging for debugging and game analysis
    """
    
    @staticmethod
    @transaction.atomic
    def create_game(table, players_with_buy_ins):
        """
        Create a new game at the specified table with the given players and their buy-ins.
        
        Args:
            table: PokerTable instance
            players_with_buy_ins: List of tuples (Player instance, buy_in_amount)
        
        Returns:
            Game instance
        """
        logger.info(f"Creating new game at table '{table.name}' with {len(players_with_buy_ins)} players")
        
        # Create new game
        game = Game.objects.create(
            table=table,
            status='WAITING',
            pot=0,
            current_bet=0,
            dealer_position=0,
        )
        
        logger.debug(f"Game {game.id} created with status WAITING")
        
        # Add players to the game
        player_names = []
        for i, (player, buy_in) in enumerate(players_with_buy_ins):
            PlayerGame.objects.create(
                player=player,
                game=game,
                seat_position=i,
                stack=buy_in,
                starting_stack=buy_in,  # Record initial stack for win/loss tracking
                is_active=True
            )
            player_names.append(f"{player.user.username} (${buy_in})")
            logger.debug(f"Added player {player.user.username} to seat {i} with stack ${buy_in}")
        
        logger.info(f"Game {game.id} created successfully with players: {', '.join(player_names)}")
        return game
    
    @staticmethod
    @transaction.atomic
    def start_game(game_id):
        """
        Start a poker game.
        
        Args:
            game_id: ID of the game to start
        
        Returns:
            Updated Game instance
        """
        logger.info(f"Starting game {game_id}")
        game = Game.objects.get(id=game_id)
        
        # Check if game can be started
        if game.status != 'WAITING':
            logger.warning(f"Cannot start game {game_id}: status is {game.status}, not WAITING")
            raise ValueError("Game has already started or finished")
        
        player_games = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False)
        player_count = player_games.count()
        if player_count < 2:
            logger.warning(f"Cannot start game {game_id}: only {player_count} players, need at least 2")
            raise ValueError("Not enough players to start the game")
        
        logger.debug(f"Game {game_id} validation passed: {player_count} players ready")
        
        # Initialize the deck and prepare for first hand
        deck = Deck()
        deck.shuffle()
        logger.debug("Deck created and shuffled for new game")
        
        # Randomly assign dealer position (only among non-cashed-out players)
        # The dealer position rotates clockwise after each hand
        num_players = player_games.count()
        game.dealer_position = random.randint(0, num_players - 1)
        logger.debug(f"Dealer position set to {game.dealer_position} (0-indexed out of {num_players} players)")
        
        # Set game status and phase to begin first hand
        game.status = 'PLAYING'
        game.phase = 'PREFLOP'
        logger.info(f"Game {game_id} status changed to PLAYING, phase PREFLOP")
        
        # Determine blind positions according to Texas Hold'em rules
        # Small blind is immediately to the left of dealer (clockwise)
        # Big blind is two seats to the left of dealer
        small_blind_pos = (game.dealer_position + 1) % num_players
        big_blind_pos = (game.dealer_position + 2) % num_players
        logger.debug(f"Blind positions - Small: {small_blind_pos}, Big: {big_blind_pos}")
        
        # Get ordered list of players by seat position for blind assignment
        player_games_list = list(player_games.order_by('seat_position'))
        
        # Post mandatory blinds before dealing cards
        # Blinds are forced bets that ensure there's always money in the pot
        small_blind_player = player_games_list[small_blind_pos]
        big_blind_player = player_games_list[big_blind_pos]
        logger.debug(f"Blind players - Small: {small_blind_player.player.user.username}, Big: {big_blind_player.player.user.username}")
        
        # Post small blind (typically half the big blind amount)
        # If player doesn't have enough chips, they go all-in
        # NOTE: Stack deduction is delayed until first betting action to allow proper cash-out amounts
        small_blind_amount = min(game.table.small_blind, small_blind_player.stack)
        small_blind_player.current_bet = small_blind_amount  # Track current bet for betting round
        small_blind_player.total_bet = small_blind_amount    # Track total bet for this hand
        small_blind_player.save()
        logger.debug(f"Small blind posted: {small_blind_player.player.user.username} - ${small_blind_amount} (stack deduction delayed)")
        
        # Post big blind (the minimum bet for this table)
        # If player doesn't have enough chips, they go all-in
        # NOTE: Stack deduction is delayed until first betting action to allow proper cash-out amounts
        big_blind_amount = min(game.table.big_blind, big_blind_player.stack)
        big_blind_player.current_bet = big_blind_amount  # Track current bet for betting round
        big_blind_player.total_bet = big_blind_amount    # Track total bet for this hand
        big_blind_player.save()
        logger.debug(f"Big blind posted: {big_blind_player.player.user.username} - ${big_blind_amount} (stack deduction delayed)")
        
        # Important: Blinds are NOT added to pot immediately
        # They will be collected when the pre-flop betting round ends
        # This prevents double-counting when _collect_bets_to_pot() runs
        total_blinds = small_blind_amount + big_blind_amount
        logger.debug(f"Total blinds ${total_blinds} posted, will be added to pot when betting round ends")
        
        # Set the current bet that all players must match or exceed
        # This is the big blind amount for pre-flop betting
        game.current_bet = big_blind_amount
        logger.debug(f"Current bet set to ${big_blind_amount}")
        
        # Deal cards to players (only active, non-cashed-out players)
        logger.debug("Dealing hole cards to players")
        for player_game in player_games:
            cards = deck.deal(2)
            card_strings = [str(card) for card in cards]
            player_game.set_cards(card_strings)
            player_game.save()
            logger.debug(f"Dealt cards to {player_game.player.user.username}: {card_strings}")
        
        # Set current player (after big blind)
        current_player_pos = (big_blind_pos + 1) % num_players
        current_player = player_games_list[current_player_pos].player
        game.current_player = current_player
        logger.debug(f"First to act: {current_player.user.username} (position {current_player_pos})")
        
        # Save game state
        game.save()
        logger.info(f"Game {game_id} started successfully - Pot: ${game.pot}, Current bet: ${game.current_bet}")
        
        # Check if the current player is a bot and schedule their action
        if game.current_player and game.current_player.is_bot:
            logger.info(f"🤖 First player to act is bot {game.current_player.user.username} - scheduling action")
            GameService._schedule_bot_action(game.id)
        
        # Schedule broadcast after transaction commits
        transaction.on_commit(lambda: GameService.broadcast_game_update(game_id))
        
        return game
    
    @staticmethod
    @transaction.atomic
    def process_action(game_id, player_id, action_type, amount=0):
        """
        Process a player's action in the game.
        
        Args:
            game_id: ID of the game
            player_id: ID of the player taking action
            action_type: Type of action ('FOLD', 'CHECK', 'CALL', 'BET', 'RAISE')
            amount: Amount for bet or raise (only used for BET and RAISE)
        
        Returns:
            Updated Game instance
        """
        game = Game.objects.get(id=game_id)
        
        # Get player name for logging
        try:
            player_name = Player.objects.get(id=player_id).user.username
        except Player.DoesNotExist:
            player_name = f"Player#{player_id}"
        
        amount_str = f" ${amount}" if amount else ""
        logger.info(f"Processing action: {player_name} - {action_type}{amount_str} (Game: {game_id}, Phase: {game.phase})")
        
        # Validate game is in progress
        if game.status != 'PLAYING':
            logger.warning(f"Action rejected - game {game_id} status is {game.status}, not PLAYING")
            raise ValueError("Game is not in progress")
        
        # Validate it's the player's turn
        if game.current_player_id != player_id:
            current_player_name = game.current_player.user.username if game.current_player else "None"
            logger.warning(f"Action rejected - not {player_name}'s turn, current player is {current_player_name}")
            raise ValueError("Not your turn to act")
        
        # Get player's game entry (must be active and not cashed out)
        try:
            player_game = PlayerGame.objects.get(game=game, player_id=player_id, is_active=True, cashed_out=False)
        except PlayerGame.DoesNotExist:
            logger.warning(f"Action rejected - {player_name} not found in active, non-cashed-out players for game {game_id}")
            raise ValueError("Player not in this game, not active, or has cashed out")
        
        logger.debug(f"Action validation passed for {player_name} - Stack: ${player_game.stack}, Current bet: ${player_game.current_bet}")
        
        # Convert amount to Decimal for consistency
        if amount:
            amount = Decimal(str(amount))
            
        # Process the action and capture actual amount processed
        actual_amount = 0
        try:
            if action_type == 'FOLD':
                GameService._handle_fold(game, player_game)
            elif action_type == 'CHECK':
                GameService._handle_check(game, player_game)
            elif action_type == 'CALL':
                actual_amount = GameService._handle_call(game, player_game)
            elif action_type == 'BET':
                GameService._handle_bet(game, player_game, amount)
                actual_amount = amount
            elif action_type == 'RAISE':
                GameService._handle_raise(game, player_game, amount)
                actual_amount = amount
            else:
                logger.error(f"Invalid action type: {action_type} from {player_name}")
                raise ValueError(f"Invalid action: {action_type}")
            
            logger.debug(f"Action processed successfully: {player_name} - {action_type}")
        except Exception as e:
            logger.error(f"Error processing action {action_type} for {player_name}: {str(e)}")
            raise
        
        # Record the action with actual amount processed
        action_amount = actual_amount if action_type in ['BET', 'RAISE', 'CALL'] else 0
        GameAction.objects.create(
            player_game=player_game,
            action_type=action_type,
            amount=action_amount,
            phase=game.phase
        )
        logger.debug(f"Action recorded: {player_name} - {action_type} ${action_amount} in {game.phase}")
        
        # Move to next player or phase
        GameService._advance_game(game)
        
        logger.info(f"Action complete: {player_name} - {action_type}{amount_str} | Pot: ${game.pot} | Phase: {game.phase}")
        return game
    
    @staticmethod
    def _handle_fold(game, player_game):
        """Handle a fold action."""
        player_name = player_game.player.user.username
        logger.debug(f"Handling fold: {player_name} folding")
        
        player_game.is_active = False
        player_game.save()
        
        active_count = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).count()
        logger.debug(f"After fold: {active_count} players remain active")
        
        # Note: Don't call _end_hand here - let the betting round logic
        # naturally progress to _showdown which handles single winner cases
    
    @staticmethod
    def _handle_check(game, player_game):
        """
        Handle a check action (passing without betting).
        
        A player can only check if:
        1. No one has bet in this round (current_bet = 0), OR
        2. They have already matched the current bet amount
        
        Common scenarios:
        - Pre-flop: Big blind can check if no one raised
        - Post-flop: First to act can check with no bets
        - Any round: Player who called earlier can check if no raises
        """
        # Validate that player is allowed to check
        # Player can check if they've already matched the current bet
        # This allows big blind to check pre-flop and players to check after calling
        if player_game.current_bet != game.current_bet:
            raise ValueError("Cannot check when there is a bet to call")
    
    @staticmethod
    def _handle_call(game, player_game):
        """
        Handle a call action (matching the current bet).
        
        Call logic:
        1. Calculate how much more the player needs to contribute
        2. Deduct from their stack (up to their available chips)
        3. Update their current_bet and total_bet tracking
        4. DO NOT add to pot yet - this happens at end of betting round
        
        If player doesn't have enough chips, they go all-in for less.
        """
        player_name = player_game.player.user.username
        
        # Convert all values to Decimal for consistent mathematical operations
        current_bet = game.current_bet
        player_current_bet = player_game.current_bet
        player_stack = player_game.stack
        
        # Calculate call amount: difference between current bet and what player has already bet
        # If player doesn't have enough chips, they can only call for their remaining stack
        call_amount = min(current_bet - player_current_bet, player_stack)
        logger.debug(f"Call calculation: {player_name} calling ${call_amount} (bet: ${current_bet}, player bet: ${player_current_bet})")
        
        # Update player's bet tracking (stack deduction delayed until betting round ends)
        player_game.current_bet += call_amount             # Update current betting round total
        player_game.total_bet += call_amount               # Update hand total for tracking
        player_game.save()
        
        # Important: Call amount is NOT added to pot immediately and stack not deducted yet
        # Both will happen when the betting round ends via _collect_bets_to_pot()
        logger.debug(f"Call processed: {player_name} called ${call_amount}, stack deduction and pot addition delayed until betting round ends")
        
        return call_amount
    
    @staticmethod
    def _handle_bet(game, player_game, amount):
        """
        Handle a bet action (first aggressive action in a betting round).
        
        Bet requirements:
        1. No one else has bet this round (current_bet must be 0)
        2. Bet amount must be at least the big blind
        3. Player must have sufficient chips (or go all-in)
        
        This function:
        - Validates bet is legal
        - Deducts chips from player's stack
        - Sets the new current_bet amount others must match
        - Does NOT add to pot immediately (collected at round end)
        """
        player_name = player_game.player.user.username
        
        # Validate no existing bet (if there is, player should raise instead)
        if game.current_bet > 0:
            logger.warning(f"Bet rejected: {player_name} cannot bet when current bet is ${game.current_bet}")
            raise ValueError("Cannot bet when there is already a bet, use 'RAISE' instead")
        
        # Validate minimum bet amount (must be at least big blind)
        min_bet = game.table.big_blind
        if amount < min_bet:
            logger.warning(f"Bet rejected: {player_name} bet ${amount} is below minimum ${min_bet}")
            raise ValueError(f"Bet must be at least the big blind: {min_bet}")
        
        # Calculate actual bet amount (limited by player's available chips)
        bet_amount = min(amount, player_game.stack)
        if bet_amount < amount:
            logger.debug(f"Bet capped: {player_name} wanted ${amount} but only has ${player_game.stack}")
        
        # Update player's bet tracking (stack deduction delayed until betting round ends)
        player_game.current_bet = bet_amount              # Set current round bet
        player_game.total_bet += bet_amount               # Add to hand total
        player_game.save()
        
        # Set the new current bet that all other players must match or exceed
        # Important: Bet amount is NOT added to pot immediately and stack not deducted yet
        # Both will happen when betting round ends via _collect_bets_to_pot()
        game.current_bet = bet_amount
        logger.debug(f"Bet processed: {player_name} bet ${bet_amount}, stack deduction and pot addition delayed until betting round ends, current bet: ${bet_amount}")
        game.save()
    
    @staticmethod
    def _handle_raise(game, player_game, amount):
        """
        Handle a raise action (increasing an existing bet).
        
        Raise requirements:
        1. There must be an existing bet to raise (current_bet > 0)
        2. Raise must be at least double the current bet (min_raise rule)
        3. Player must have sufficient chips (or go all-in)
        
        Raise calculation:
        - 'amount' parameter is the TOTAL amount player wants to bet
        - We calculate how much additional chips they need to contribute
        - Example: current bet $10, player has bet $5, wants to raise to $20
          -> raise_amount = $20 - $5 = $15 additional chips needed
        """
        player_name = player_game.player.user.username
        
        # Validate there's an existing bet to raise
        if game.current_bet == 0:
            logger.warning(f"Raise rejected: {player_name} cannot raise when current bet is 0")
            raise ValueError("Cannot raise when there is no bet, use 'BET' instead")
        
        # Calculate how much additional chips the player needs to contribute
        # 'amount' is the total they want to bet, not the raise amount
        total_amount = amount
        current_player_bet = player_game.current_bet
        raise_amount = total_amount - current_player_bet
        
        # Validate minimum raise (typically double the current bet)
        min_raise = game.current_bet * 2
        if total_amount < min_raise:
            logger.warning(f"Raise rejected: {player_name} raise to ${total_amount} is below minimum ${min_raise}")
            raise ValueError(f"Raise must be at least double the current bet: {min_raise}")
        
        # Cap raise at player's available chips (all-in protection)
        available_raise = min(raise_amount, player_game.stack)
        if available_raise < raise_amount:
            logger.debug(f"Raise capped: {player_name} wanted ${raise_amount} but only has ${player_game.stack}")
        
        # Calculate final total bet amount for this player
        total_bet = current_player_bet + available_raise
        
        # Update player's bet tracking (stack deduction delayed until betting round ends)
        player_game.current_bet = total_bet               # Update current round total
        player_game.total_bet += available_raise          # Add to hand total
        player_game.save()
        
        # Set the new current bet that all other players must match or exceed
        # Important: Raise amount is NOT added to pot immediately and stack not deducted yet
        # Both will happen when betting round ends via _collect_bets_to_pot()
        game.current_bet = total_bet
        logger.debug(f"Raise processed: {player_name} raised ${available_raise}, stack deduction and pot addition delayed until betting round ends, current bet: ${total_bet}")
        game.save()
    
    @staticmethod
    def _collect_bets_to_pot(game):
        """
        Collect all current bets from players and add them to the pot.
        
        This critical function is called at the END of each betting round to:
        1. Sum up all player's current_bet amounts
        2. Add the total to the game pot
        3. Log the collection for transparency
        
        This delayed collection prevents double-counting issues and ensures
        the pot only grows when betting rounds actually complete.
        
        Called by: _move_to_next_phase() when advancing game phases
        """
        # Get all players who haven't cashed out (includes folded players who may have blinds to collect)
        all_players = PlayerGame.objects.filter(game=game, cashed_out=False)
        total_collected = Decimal('0')
        
        # Sum up all current bets from all players and deduct from stacks
        # This includes blinds, calls, bets, and raises from the current round
        for player_game in all_players:
            if player_game.current_bet > 0:
                total_collected += player_game.current_bet
                # Deduct the bet from player's stack (delayed from when bet was made)
                player_game.stack -= player_game.current_bet
                player_game.save()
                logger.debug(f"Collecting ${player_game.current_bet} from {player_game.player.user.username}, stack now ${player_game.stack}")
        
        # Add collected bets to the pot (if any)
        if total_collected > 0:
            old_pot = game.pot
            game.pot += total_collected
            logger.info(f"Betting round ended: collected ${total_collected} from all players, pot ${old_pot} -> ${game.pot}")
            game.save()
        else:
            logger.debug("No bets to collect this round")
    
    @staticmethod
    def _advance_game(game):
        """Advance the game to the next player or phase."""
        active_players = list(PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).order_by('seat_position'))
        logger.debug(f"Advancing game {game.id}: {len(active_players)} active players")
        
        # Check if only one player left
        if len(active_players) == 1:
            # Only one player left - skip to showdown
            logger.info(f"Only one player remaining, moving to showdown")
            GameService._move_to_next_phase(game)
            return
        
        # Check if betting round is complete
        betting_complete = GameService._is_betting_round_complete(game, active_players)
        logger.debug(f"Betting round complete: {betting_complete}")
        
        if betting_complete:
            logger.info(f"Betting round complete for {game.phase}, moving to next phase")
            GameService._move_to_next_phase(game)
            return
        
        # Find current player's position in the active players list
        current_pos = None
        current_player_name = game.current_player.user.username if game.current_player else "None"
        
        for i, pg in enumerate(active_players):
            if pg.player_id == game.current_player_id:
                current_pos = i
                break
        
        # If current player is not found in active players (e.g., they just folded),
        # find the next active player by seat position
        if current_pos is None:
            logger.debug(f"Current player {current_player_name} not in active players, finding next by seat position")
            # Get the current player's seat position
            try:
                current_player_game = PlayerGame.objects.get(game=game, player_id=game.current_player_id)
                current_seat = current_player_game.seat_position
                
                # Find the next active player by seat position
                next_player = None
                for pg in active_players:
                    if pg.seat_position > current_seat:
                        next_player = pg
                        break
                
                # If no player found after current seat, wrap around to first active player
                if next_player is None:
                    next_player = active_players[0]
                    
                game.current_player = next_player.player
                logger.debug(f"Next player by seat position: {next_player.player.user.username}")
            except PlayerGame.DoesNotExist:
                # Fallback: set to first active player
                game.current_player = active_players[0].player
                logger.debug(f"Fallback to first active player: {active_players[0].player.user.username}")
        else:
            # Move to next player in the active players list
            next_pos = (current_pos + 1) % len(active_players)
            next_player = active_players[next_pos]
            game.current_player = next_player.player
            logger.debug(f"Next player in sequence: {next_player.player.user.username} (position {next_pos})")
        
        game.save()
        
        # Check if the current player is a bot and schedule their action
        if game.current_player and game.current_player.is_bot:
            GameService._schedule_bot_action(game.id)
    
    @staticmethod
    def _schedule_bot_action(game_id, retry_count=0):
        """
        Schedule a bot action with thinking delay and comprehensive error handling.
        Includes retry logic and fallback mechanisms for reliability.
        """
        import time
        import threading
        from django.conf import settings
        from django.db import transaction
        
        MAX_RETRIES = 3
        RETRY_DELAY = 1.0  # seconds
        
        logger.info(f"Scheduling bot action for game {game_id} (attempt {retry_count + 1}/{MAX_RETRIES + 1})")
        
        try:
            # Ensure we have the latest game state with transaction isolation
            with transaction.atomic():
                # Get fresh game state with select_for_update to prevent race conditions
                try:
                    game = Game.objects.select_for_update().get(id=game_id)
                except Game.DoesNotExist:
                    logger.error(f"Bot action cancelled - game {game_id} no longer exists")
                    return False
                
                # Double-check it's still the bot's turn (prevent race conditions)
                if not game.current_player or not game.current_player.is_bot:
                    logger.warning(f"Bot action cancelled - current player is not a bot in game {game_id}")
                    logger.info(f"Current player: {game.current_player.user.username if game.current_player else 'None'}, is_bot: {game.current_player.is_bot if game.current_player else 'N/A'}")
                    return False
                
                # Check game is still in playable state
                if game.status != 'PLAYING':
                    logger.warning(f"Bot action cancelled - game {game_id} status is {game.status}, not PLAYING")
                    return False
                
                bot_username = game.current_player.user.username
                logger.info(f"Bot {bot_username} confirmed as current player in game {game_id}")
                
                # Get bot configuration
                try:
                    bot_player = BotPlayer.objects.get(player=game.current_player)
                    logger.info(f"Found bot configuration: {bot_username} ({bot_player.difficulty}/{bot_player.play_style})")
                except BotPlayer.DoesNotExist:
                    logger.error(f"Bot player configuration not found for {bot_username}")
                    # Try to skip this bot's turn as fallback
                    return GameService._handle_bot_action_failure(game_id, "Missing bot configuration")
                
                # Calculate thinking time
                try:
                    thinking_time = BotDecisionEngine(bot_player, game, None).get_thinking_time()
                    logger.info(f"Bot {bot_username} thinking for {thinking_time:.1f} seconds")
                except Exception as e:
                    logger.error(f"Error calculating thinking time for bot {bot_username}: {str(e)}")
                    thinking_time = 2.0  # Fallback thinking time
            
            # Use threading only in production, synchronous in development
            use_threading = getattr(settings, 'USE_THREADING_FOR_BOTS', not settings.DEBUG)
            
            if use_threading:
                # Threading approach for production with timeout
                def delayed_bot_action():
                    try:
                        time.sleep(thinking_time)
                        
                        # Create timeout wrapper for bot action
                        import signal
                        
                        def timeout_handler(signum, frame):
                            raise TimeoutError(f"Bot action timed out after 30 seconds")
                        
                        def bot_action_with_timeout():
                            # Set timeout signal (only works on Unix-like systems)
                            if hasattr(signal, 'SIGALRM'):
                                signal.signal(signal.SIGALRM, timeout_handler)
                                signal.alarm(30)  # 30 second timeout
                            
                            try:
                                success = GameService._process_bot_action(game_id, retry_count)
                                return success
                            finally:
                                # Clear timeout
                                if hasattr(signal, 'SIGALRM'):
                                    signal.alarm(0)
                        
                        try:
                            success = bot_action_with_timeout()
                        except TimeoutError as e:
                            logger.error(f"🤖⏰ Bot action timeout for game {game_id}: {str(e)}")
                            GameService._handle_bot_action_failure(game_id, f"Bot action timeout: {str(e)}")
                            return
                        
                        if not success and retry_count < MAX_RETRIES:
                            # Schedule retry after delay
                            time.sleep(RETRY_DELAY)
                            GameService._schedule_bot_action(game_id, retry_count + 1)
                    except Exception as e:
                        logger.error(f"Error in threaded bot action for game {game_id}: {str(e)}")
                        if retry_count < MAX_RETRIES:
                            time.sleep(RETRY_DELAY)
                            GameService._schedule_bot_action(game_id, retry_count + 1)
                        else:
                            GameService._handle_bot_action_failure(game_id, f"Threading error after {MAX_RETRIES} retries: {str(e)}")
                
                thread = threading.Thread(target=delayed_bot_action)
                thread.daemon = True
                thread.start()
                logger.info(f"Started bot action thread for game {game_id} with 30s timeout")
                return True
            else:
                # Synchronous approach for development with timeout
                logger.info(f"Processing bot action synchronously for development")
                time.sleep(thinking_time)
                
                # Simple timeout for synchronous mode (less sophisticated than signal-based)
                import time as time_module
                start_time = time_module.time()
                
                try:
                    success = GameService._process_bot_action(game_id, retry_count)
                    elapsed_time = time_module.time() - start_time
                    
                    if elapsed_time > 30:  # 30 second timeout
                        logger.warning(f"🤖⏰ Bot action took {elapsed_time:.1f}s (> 30s timeout)")
                    
                except Exception as e:
                    elapsed_time = time_module.time() - start_time
                    if elapsed_time > 30:
                        logger.error(f"🤖⏰ Bot action timeout in sync mode after {elapsed_time:.1f}s")
                        return GameService._handle_bot_action_failure(game_id, f"Sync bot action timeout: {elapsed_time:.1f}s")
                    raise
                
                if not success and retry_count < MAX_RETRIES:
                    logger.info(f"Retrying bot action for game {game_id} in {RETRY_DELAY}s")
                    time.sleep(RETRY_DELAY)
                    return GameService._schedule_bot_action(game_id, retry_count + 1)
                elif not success:
                    return GameService._handle_bot_action_failure(game_id, f"Bot action failed after {MAX_RETRIES} retries")
                
                return True
                
        except Exception as e:
            logger.error(f"Critical error in bot action scheduling for game {game_id}: {str(e)}")
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying bot action scheduling for game {game_id}")
                time.sleep(RETRY_DELAY)
                return GameService._schedule_bot_action(game_id, retry_count + 1)
            else:
                return GameService._handle_bot_action_failure(game_id, f"Scheduling error after {MAX_RETRIES} retries: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def _handle_bot_action_failure(game_id, error_reason):
        """
        Handle bot action failures by skipping the bot's turn and advancing the game.
        This prevents games from getting stuck when bots fail to act.
        """
        logger.error(f"Handling bot action failure for game {game_id}: {error_reason}")
        
        try:
            # Get current game state
            game = Game.objects.select_for_update().get(id=game_id)
            
            if not game.current_player or game.status != 'PLAYING':
                logger.warning(f"Cannot handle bot failure - game {game_id} not in valid state")
                return False
            
            bot_username = game.current_player.user.username
            logger.warning(f"🤖❌ Bot {bot_username} failed to act in game {game_id}: {error_reason}")
            
            # Find what actions were available to the bot
            try:
                player_game = PlayerGame.objects.get(game=game, player=game.current_player, is_active=True, cashed_out=False)
                valid_actions = GameService._get_valid_actions(game, player_game)
                logger.info(f"Bot {bot_username} had valid actions: {valid_actions}")
                
                # Choose a safe default action (fold if possible, otherwise check)
                if 'FOLD' in valid_actions:
                    fallback_action = 'FOLD'
                    fallback_amount = 0
                elif 'CHECK' in valid_actions:
                    fallback_action = 'CHECK' 
                    fallback_amount = 0
                elif 'CALL' in valid_actions:
                    fallback_action = 'CALL'
                    fallback_amount = 0
                else:
                    # This shouldn't happen, but if it does, we can't recover
                    logger.error(f"No valid fallback action for bot {bot_username} - game may be stuck")
                    return False
                
                logger.warning(f"🤖🆘 Executing fallback action for bot {bot_username}: {fallback_action}")
                
                # Execute the fallback action
                GameService.process_action(game_id, game.current_player.id, fallback_action, fallback_amount)
                logger.warning(f"🤖✅ Fallback action completed for bot {bot_username}")
                
                return True
                
            except PlayerGame.DoesNotExist:
                logger.error(f"Bot {bot_username} not found in active players for game {game_id}")
                return False
            except Exception as e:
                logger.error(f"Error executing fallback action for bot {bot_username}: {str(e)}")
                return False
                
        except Game.DoesNotExist:
            logger.error(f"Game {game_id} not found when handling bot failure")
            return False
        except Exception as e:
            logger.error(f"Critical error handling bot failure for game {game_id}: {str(e)}")
            return False
    
    @staticmethod
    @transaction.atomic
    def _process_bot_action(game_id, retry_count=0):
        """
        Process a bot's action based on their AI decision engine.
        Includes comprehensive error handling and returns success status.
        """
        import traceback
        
        logger.info(f"🤖🎮 Starting bot action processing for game {game_id} (attempt {retry_count + 1})")
        
        try:
            # Get fresh game state with row-level locking to prevent race conditions
            game = Game.objects.select_for_update().get(id=game_id)
            logger.info(f"🤖📊 Retrieved game {game_id}: status={game.status}, phase={game.phase}")
            
            # Verify game is still in valid state
            if game.status != 'PLAYING':
                logger.warning(f"🤖❌ Bot action cancelled - game {game_id} status is {game.status}, not PLAYING")
                return False
            
            # Verify it's still the bot's turn (critical check for race conditions)
            if not game.current_player or not game.current_player.is_bot:
                logger.warning(f"🤖❌ Bot action cancelled - current player is not a bot in game {game_id}")
                if game.current_player:
                    logger.info(f"Current player: {game.current_player.user.username}, is_bot: {game.current_player.is_bot}")
                else:
                    logger.info("Current player is None")
                return False
            
            bot_username = game.current_player.user.username
            logger.info(f"🤖✅ Confirmed bot {bot_username} is current player")
            
            # Get player game entry with latest data
            try:
                player_game = PlayerGame.objects.select_for_update().get(
                    game=game, 
                    player=game.current_player, 
                    is_active=True, 
                    cashed_out=False
                )
                logger.info(f"🤖💰 Bot {bot_username}: stack=${player_game.stack}, current_bet=${player_game.current_bet}, total_bet=${player_game.total_bet}")
            except PlayerGame.DoesNotExist:
                logger.error(f"🤖❌ Bot {bot_username} not found in active players for game {game_id}")
                return False
            
            # Get bot configuration
            try:
                bot_player = BotPlayer.objects.get(player=game.current_player)
                logger.info(f"🤖⚙️ Bot {bot_username}: {bot_player.difficulty} {bot_player.play_style} (aggr: {bot_player.aggression_factor}, bluff: {bot_player.bluff_frequency})")
            except BotPlayer.DoesNotExist:
                logger.error(f"🤖❌ Bot configuration not found for {bot_username}")
                return False
            
            # Determine valid actions based on current game state
            valid_actions = GameService._get_valid_actions(game, player_game)
            logger.info(f"🤖🎯 Valid actions for bot {bot_username}: {valid_actions}")
            
            if not valid_actions:
                logger.error(f"🤖❌ No valid actions for bot {bot_username} - this should not happen")
                return False
            
            # Create decision engine and get bot decision
            logger.debug(f"🤖🧠 Creating decision engine for bot {bot_username}")
            try:
                decision_engine = BotDecisionEngine(bot_player, game, player_game)
                action_type, amount = decision_engine.make_decision(valid_actions)
                
                # Log detailed decision info
                amount_str = f" ${amount}" if amount and amount > 0 else ""
                logger.info(f"🤖💭 Bot {bot_username} decision: {action_type}{amount_str}")
                logger.debug(f"🤖📈 Decision context: pot=${game.pot}, current_bet=${game.current_bet}, phase={game.phase}")
                
            except Exception as e:
                logger.error(f"🤖❌ Error in bot decision making for {bot_username}: {str(e)}")
                logger.debug(f"🤖🔍 Decision engine traceback: {traceback.format_exc()}")
                return False
            
            # Validate the bot's decision
            if action_type not in valid_actions:
                logger.error(f"🤖❌ Bot {bot_username} chose invalid action {action_type}, valid: {valid_actions}")
                return False
            
            # Additional validation for betting actions
            if action_type in ['BET', 'RAISE'] and (not amount or amount <= 0):
                logger.error(f"🤖❌ Bot {bot_username} chose {action_type} but amount is invalid: {amount}")
                return False
            
            # Process the action through the main game service
            logger.info(f"🤖⚡ Processing bot action: {bot_username} -> {action_type}{amount_str}")
            try:
                GameService.process_action(game_id, game.current_player.id, action_type, amount)
                logger.info(f"🤖✅ Bot action processed successfully: {bot_username} -> {action_type}{amount_str}")
                return True
                
            except ValueError as e:
                logger.error(f"🤖❌ Bot action validation failed for {bot_username}: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"🤖❌ Error processing bot action for {bot_username}: {str(e)}")
                logger.debug(f"🤖🔍 Action processing traceback: {traceback.format_exc()}")
                return False
            
        except Game.DoesNotExist:
            logger.error(f"🤖❌ Game {game_id} not found for bot action")
            return False
        except Exception as e:
            logger.error(f"🤖❌ Critical error processing bot action for game {game_id}: {str(e)}")
            logger.error(f"🤖🔍 Critical error traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def _get_valid_actions(game, player_game):
        """
        Determine what actions are valid for a player in the current game state.
        
        Returns:
            List of valid action strings ('FOLD', 'CHECK', 'CALL', 'BET', 'RAISE')
        """
        valid_actions = []
        
        # FOLD is always available (except when already all-in)
        if player_game.stack > 0:
            valid_actions.append('FOLD')
        
        current_bet_to_call = game.current_bet - player_game.current_bet
        
        # CHECK is available when no bet to call
        if current_bet_to_call == 0:
            valid_actions.append('CHECK')
        
        # CALL is available when there's a bet to call and player has chips
        if current_bet_to_call > 0 and player_game.stack >= current_bet_to_call:
            valid_actions.append('CALL')
        
        # BET is available when no current bet and player has chips
        if game.current_bet == 0 and player_game.stack > 0:
            valid_actions.append('BET')
        
        # RAISE is available when there's a current bet and player has enough chips
        if game.current_bet > 0 and player_game.stack > current_bet_to_call:
            valid_actions.append('RAISE')
        
        return valid_actions
    
    @staticmethod
    def _is_betting_round_complete(game, active_players):
        """Check if the current betting round is complete."""
        current_bet = game.current_bet
        
        # Rule 1: All active players must have matched the current bet or be all-in
        for pg in active_players:
            if pg.current_bet < current_bet and pg.stack > 0:
                return False
        
        # Rule 2: Every active player with chips must have had a chance to act in this phase
        # Get all actions in current phase from the current hand only
        # Filter actions to only include those from the current hand (after the last hand history)
        last_hand_history = HandHistory.objects.filter(game=game).order_by('-completed_at').first()
        if last_hand_history:
            current_hand_start = last_hand_history.completed_at
            phase_actions = GameAction.objects.filter(
                player_game__game=game,
                player_game__in=active_players,
                phase=game.phase,
                timestamp__gt=current_hand_start
            )
        else:
            # First hand of the game
            phase_actions = GameAction.objects.filter(
                player_game__game=game,
                player_game__in=active_players,
                phase=game.phase
            )
        
        # Special case for PREFLOP: everyone needs to act, including blind posters
        if game.phase == 'PREFLOP':
            # In preflop, every player (including blinds) must have acted
            for pg in active_players:
                if pg.stack == 0:  # All-in players don't need to act
                    continue
                    
                # Check if this player has taken any action in preflop
                player_actions = phase_actions.filter(player_game=pg)
                if not player_actions.exists():
                    # This player hasn't acted yet
                    return False
        else:
            # For FLOP, TURN, RIVER: all players with chips must have acted
            for pg in active_players:
                if pg.stack == 0:  # All-in players don't need to act
                    continue
                    
                # Check if this player has taken any action in this phase
                player_actions = phase_actions.filter(player_game=pg)
                if not player_actions.exists():
                    # This player hasn't acted yet
                    return False
        
        # Rule 3: If there was a bet/raise, all other players must have responded after it
        last_aggressive_action = phase_actions.filter(
            action_type__in=['BET', 'RAISE']
        ).order_by('-timestamp').first()
        
        if last_aggressive_action:
            # All other active players with chips must have acted after this bet/raise
            for pg in active_players:
                if pg == last_aggressive_action.player_game or pg.stack == 0:
                    continue  # Skip the aggressor and all-in players
                
                # Check if this player has acted after the bet/raise
                response_actions = GameAction.objects.filter(
                    player_game=pg,
                    phase=game.phase,
                    timestamp__gt=last_aggressive_action.timestamp
                )
                
                if not response_actions.exists():
                    return False
        
        return True
    
    @staticmethod
    @transaction.atomic
    def _move_to_next_phase(game):
        """Move to the next phase of the game."""
        logger.info(f"Moving from {game.phase} to next phase in game {game.id}")
        
        active_players = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False)
        active_count = active_players.count()
        
        # Collect all current bets and add them to the pot
        GameService._collect_bets_to_pot(game)
        
        # If only one player left, skip to showdown
        if active_count == 1:
            logger.info(f"Only {active_count} player left, moving to showdown")
            game.phase = 'SHOWDOWN'
            GameService._showdown(game)
            return
            
        # Reset current bets after collecting them to pot
        for pg in active_players:
            pg.current_bet = 0
            pg.save()
        
        # Reset current bet
        game.current_bet = 0
        
        # Clear actions from previous phase to reset action tracking
        # Note: We keep actions for history but track per-phase actions differently
        
        # Deal community cards based on current phase
        if game.phase == 'PREFLOP':
            # Deal the flop (3 cards)
            deck = GameService._get_game_deck(game)
            flop_cards = [str(card) for card in deck.deal(3)]
            game.set_community_cards(flop_cards)
            game.phase = 'FLOP'
            logger.info(f"Flop dealt: {', '.join(flop_cards)}")
        elif game.phase == 'FLOP':
            # Deal the turn (1 card)
            deck = GameService._get_game_deck(game)
            community_cards = game.get_community_cards()
            turn_card = str(deck.deal())
            community_cards.append(turn_card)
            game.set_community_cards(community_cards)
            game.phase = 'TURN'
            logger.info(f"Turn dealt: {turn_card}")
        elif game.phase == 'TURN':
            # Deal the river (1 card)
            deck = GameService._get_game_deck(game)
            community_cards = game.get_community_cards()
            river_card = str(deck.deal())
            community_cards.append(river_card)
            game.set_community_cards(community_cards)
            game.phase = 'RIVER'
            logger.info(f"River dealt: {river_card}")
        elif game.phase == 'RIVER':
            # Move to showdown
            game.phase = 'SHOWDOWN'
            logger.info(f"Moving to showdown")
            # Evaluate hands and determine winner
            GameService._showdown(game)
        
        # Set the first active player after the dealer to act first
        if game.phase != 'SHOWDOWN':
            dealer_pos = game.dealer_position
            active_players = list(active_players.order_by('seat_position'))
            
            # Find the first active player after the dealer
            for i in range(1, len(active_players) + 1):
                next_pos = (dealer_pos + i) % len(active_players)
                first_to_act = active_players[next_pos].player
                game.current_player = first_to_act
                logger.debug(f"First to act in {game.phase}: {first_to_act.user.username}")
                break
        
        game.save()
        logger.info(f"Phase transition complete: now in {game.phase}")
        
        # Check if the current player is a bot and schedule their action
        if game.current_player and game.current_player.is_bot:
            GameService._schedule_bot_action(game.id)
        
        # Schedule broadcast after transaction commits
        transaction.on_commit(lambda: GameService.broadcast_game_update(game.id))
    
    @staticmethod
    def _get_game_deck(game):
        """Get a deck with the appropriate cards removed."""
        # Create a new deck and shuffle it for randomness
        deck = Deck()
        deck.shuffle()
        
        # Remove community cards
        community_cards = game.get_community_cards()
        for card_str in community_cards:
            # Handle parsing - rank can be 1-2 characters, suit is always last
            rank = card_str[:-1]
            suit = card_str[-1]
            card = Card(rank, suit)
            if card in deck.cards:
                deck.cards.remove(card)
        
        # Remove player cards
        player_games = PlayerGame.objects.filter(game=game)
        for pg in player_games:
            for card_str in pg.get_cards():
                # Handle parsing - rank can be 1-2 characters, suit is always last
                rank = card_str[:-1]
                suit = card_str[-1]
                card = Card(rank, suit)
                if card in deck.cards:
                    deck.cards.remove(card)
        
        return deck
    
    @staticmethod
    def _get_showdown_order(game, active_players):
        """Determine the order players should show their cards at showdown.
        
        Rules from CLAUDE.md:
        1. The last player to bet or raise shows their cards first
        2. If there was no betting on the river, player closest to left of dealer shows first
        """
        # Find the last bet or raise action on the river (only from non-cashed-out players)
        last_aggressive_action = GameAction.objects.filter(
            player_game__game=game,
            player_game__is_active=True,
            player_game__cashed_out=False,
            phase='RIVER',
            action_type__in=['BET', 'RAISE']
        ).order_by('-timestamp').first()
        
        if last_aggressive_action:
            # Last aggressive player shows first
            first_to_show = last_aggressive_action.player_game
        else:
            # No betting on river - find player closest to left of dealer
            dealer_pos = game.dealer_position
            active_players_list = list(active_players.order_by('seat_position'))
            
            # Find first active player after dealer
            first_to_show = None
            for i in range(1, len(active_players_list) + 1):
                next_pos = (dealer_pos + i) % len(active_players_list)
                candidate = None
                for pg in active_players_list:
                    if pg.seat_position == next_pos:
                        candidate = pg
                        break
                if candidate:
                    first_to_show = candidate
                    break
            
            if not first_to_show:
                first_to_show = active_players.first()
        
        # Create ordered list starting with first_to_show
        ordered_players = [first_to_show]
        remaining_players = [pg for pg in active_players if pg != first_to_show]
        ordered_players.extend(remaining_players)
        
        return ordered_players
    
    @staticmethod
    def _showdown(game):
        """Determine the winner(s) at showdown."""
        logger.info(f"Starting showdown for game {game.id}")
        
        # Get active players (excluding cashed out players)
        active_players = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False)
        active_count = active_players.count()
        logger.debug(f"Showdown with {active_count} active players")
        
        # Determine showdown order according to Texas Hold'em rules
        showdown_order = GameService._get_showdown_order(game, active_players)
        
        # If only one active player, they win
        if active_count == 1:
            winner = active_players.first()
            winner_name = winner.player.user.username
            pot_amount = game.pot
            logger.info(f"Single winner: {winner_name} wins ${pot_amount}")
            
            winner.stack += pot_amount
            winner.save()
            
            # Get all players' money changes for this hand
            all_players_money_changes = []
            for pg in PlayerGame.objects.filter(game=game):
                all_players_money_changes.append({
                    'player_name': pg.player.user.username,
                    'player_id': pg.player.id,
                    'total_bet_this_hand': float(pg.total_bet),
                    'current_stack': float(pg.stack),
                    'was_active': pg.is_active
                })

            # Store winner information
            winner_data = {
                'type': 'single_winner',
                'winners': [{
                    'player_name': winner.player.user.username,
                    'player_id': winner.player.id,
                    'winning_amount': float(game.pot),
                    'reason': 'All other players folded'
                }],
                'pot_amount': float(game.pot),
                'money_changes': all_players_money_changes
            }
            game.set_winner_info(winner_data)
            
            # Save hand history BEFORE resetting pot
            original_pot = game.pot
            GameService._save_hand_history(game, original_pot)
            
            game.pot = 0
            game.phase = 'WAITING_FOR_PLAYERS'  # Set to waiting state so popup can show
            game.save()
            
            # Auto-ready all bot players and check if we can start next hand
            GameService._auto_ready_bots(game)
            if not GameService._check_and_start_next_hand(game):
                # If next hand didn't start automatically, broadcast winner info for popup
                GameService.broadcast_game_update(game.id)
            return
        
        # Evaluate each player's hand
        community_cards = [GameService._parse_card(card) for card in game.get_community_cards()]
        logger.debug(f"Community cards for evaluation: {[str(c) for c in community_cards]}")
        
        best_hands = {}
        for pg in active_players:
            player_name = pg.player.user.username
            # Convert string cards to Card objects
            hole_cards = [GameService._parse_card(card) for card in pg.get_cards()]
            logger.debug(f"Evaluating {player_name}'s hand: {[str(c) for c in hole_cards]}")
            
            # Combine with community cards
            all_cards = hole_cards + community_cards
            
            # Evaluate best hand
            hand_rank, hand_value, hand_name, best_hand_cards = HandEvaluator.evaluate_hand(all_cards)
            best_hands[pg.id] = (hand_rank, hand_value, hand_name, best_hand_cards, pg)
            logger.debug(f"{player_name} has {hand_name} (rank {hand_rank})")
        
        # Sort by hand strength (lower rank is better, higher value within rank is better)
        sorted_hands = sorted(best_hands.values(), key=lambda x: (x[0], [-v for v in x[1]]))
        
        # Find winners (players with the same best hand)
        best_hand = sorted_hands[0]
        winners = [pg for rank, value, name, best_cards, pg in sorted_hands if (rank, value) == (best_hand[0], best_hand[1])]
        
        # Split pot among winners
        pot_amount = game.pot
        win_amount = pot_amount / Decimal(len(winners))
        
        if len(winners) == 1:
            logger.info(f"Showdown winner: {winners[0].player.user.username} with {best_hand[2]} wins ${pot_amount}")
        else:
            winner_names = [w.player.user.username for w in winners]
            logger.info(f"Split pot: {', '.join(winner_names)} each win ${win_amount} with {best_hand[2]}")
        
        for winner in winners:
            winner.stack += win_amount
            winner.save()
        
        # Get all players' money changes for this hand
        all_players_money_changes = []
        for pg in PlayerGame.objects.filter(game=game):
            all_players_money_changes.append({
                'player_name': pg.player.user.username,
                'player_id': pg.player.id,
                'total_bet_this_hand': float(pg.total_bet),
                'current_stack': float(pg.stack),
                'was_active': pg.is_active
            })

        # Store winner information
        winner_data = {
            'type': 'showdown_winner',
            'winners': [{
                'player_name': winner.player.user.username,
                'player_id': winner.player.id,
                'winning_amount': float(win_amount),
                'hand_name': best_hand[2],
                'hole_cards': winner.get_cards(),
                'best_hand_cards': [str(card) for card in best_hand[3]]
            } for winner in winners],
            'pot_amount': float(game.pot),
            'community_cards': game.get_community_cards(),
            'showdown_order': [{
                'player_name': pg.player.user.username,
                'player_id': pg.player.id,
                'show_order': idx + 1
            } for idx, pg in enumerate(showdown_order)],
            'all_hands': [{
                'player_name': pg.player.user.username,
                'hand_name': hand_name,
                'hole_cards': pg.get_cards(),
                'hand_rank': hand_rank,
                'best_hand_cards': [str(card) for card in best_cards]
            } for hand_rank, hand_value, hand_name, best_cards, pg in sorted_hands],
            'money_changes': all_players_money_changes
        }
        game.set_winner_info(winner_data)
        
        # Save hand history BEFORE resetting pot
        original_pot = game.pot
        GameService._save_hand_history(game, original_pot)
        
        # Reset pot but keep winner info for popup
        game.pot = 0
        game.phase = 'WAITING_FOR_PLAYERS'  # Set to waiting state instead of auto-starting
        game.save()
        
        # Auto-ready all bot players and check if we can start next hand
        GameService._auto_ready_bots(game)
        if not GameService._check_and_start_next_hand(game):
            # If next hand didn't start automatically, broadcast winner info for popup
            GameService.broadcast_game_update(game.id)
    
    @staticmethod
    def _end_hand(game):
        """End the current hand when only one player remains."""
        # Award pot to the last remaining player (excluding cashed out players)
        winner = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).first()
        if winner:
            winner.stack += game.pot
            winner.save()
            
            # Get all players' money changes for this hand
            all_players_money_changes = []
            for pg in PlayerGame.objects.filter(game=game):
                all_players_money_changes.append({
                    'player_name': pg.player.user.username,
                    'player_id': pg.player.id,
                    'total_bet_this_hand': float(pg.total_bet),
                    'current_stack': float(pg.stack),
                    'was_active': pg.is_active
                })

            # Store winner information
            winner_data = {
                'type': 'single_winner',
                'winners': [{
                    'player_name': winner.player.user.username,
                    'player_id': winner.player.id,
                    'winning_amount': float(game.pot),
                    'reason': 'All other players folded'
                }],
                'pot_amount': float(game.pot),
                'money_changes': all_players_money_changes
            }
            game.set_winner_info(winner_data)
        
        # Save hand history BEFORE resetting pot
        original_pot = game.pot
        GameService._save_hand_history(game, original_pot)
        
        # Reset pot but keep winner info for popup
        game.pot = 0
        game.phase = 'WAITING_FOR_PLAYERS'  # Set to waiting state instead of auto-starting
        game.save()
        
        # Auto-ready all bot players and check if we can start next hand
        GameService._auto_ready_bots(game)
        if not GameService._check_and_start_next_hand(game):
            # If next hand didn't start automatically, broadcast winner info for popup
            GameService.broadcast_game_update(game.id)

    @staticmethod
    def _parse_card(card_str):
        """Parse a card string like 'AH', '10C', 'KS' into a Card object."""
        if len(card_str) == 2:
            # Single character rank like 'A', 'K', 'Q', 'J', '2'-'9'
            rank = card_str[0]
            suit = card_str[1]
        elif len(card_str) == 3 and card_str.startswith('10'):
            # Special case for '10'
            rank = '10'
            suit = card_str[2]
        else:
            raise ValueError(f"Invalid card format: {card_str}")
        
        return Card(rank, suit)

    @staticmethod
    def _save_hand_history(game, pot_amount=None):
        """Save the completed hand to history before starting a new hand."""
        if not game.winner_info:
            return
        
        # Get current hand number
        current_hand_number = game.hand_count + 1
        
        # Check if hand history already exists for this hand
        existing_history = HandHistory.objects.filter(game=game, hand_number=current_hand_number).first()
        if existing_history:
            logger.warning(f"Hand history already exists for game {game.id}, hand {current_hand_number}")
            return
        
        # Collect all player cards
        player_cards = {}
        for pg in PlayerGame.objects.filter(game=game):
            if pg.cards:
                player_cards[pg.player.user.username] = pg.get_cards()
        
        # Collect all actions for this hand (since last hand history save)
        actions = []
        last_hand_history = HandHistory.objects.filter(game=game).order_by('-hand_number').first()
        if last_hand_history:
            # Get actions since the last hand history was saved
            actions_query = GameAction.objects.filter(
                player_game__game=game,
                timestamp__gt=last_hand_history.completed_at
            ).order_by('timestamp')
        else:
            # This is the first hand, get all actions
            actions_query = GameAction.objects.filter(
                player_game__game=game
            ).order_by('timestamp')
        
        for action in actions_query:
            actions.append({
                'player': action.player_game.player.user.username,
                'action': action.action_type,
                'amount': float(action.amount) if action.amount else 0,
                'phase': action.phase,
                'timestamp': action.timestamp.isoformat()
            })
        
        # Create hand history record
        hand_history = HandHistory.objects.create(
            game=game,
            hand_number=current_hand_number,
            pot_amount=pot_amount if pot_amount is not None else game.pot,
            final_phase=game.phase,
            completed_at=timezone.now()
        )
        
        # Set JSON data
        hand_history.set_winner_info(game.get_winner_info())
        hand_history.set_player_cards(player_cards)
        hand_history.set_actions(actions)
        if game.community_cards:
            hand_history.set_community_cards(game.get_community_cards())
        
        hand_history.save()
        
        # Increment hand count
        game.hand_count = current_hand_number
        game.save()
        
        # Log the completed hand history
        winner_info = hand_history.get_winner_info()
        logger.info(f"\n{'='*60}")
        logger.info(f"HAND #{current_hand_number} COMPLETED - Table: {game.table.name}")
        logger.info(f"{'='*60}")
        logger.info(f"Pot Amount: ${hand_history.pot_amount}")
        logger.info(f"Final Phase: {hand_history.final_phase}")
        logger.info(f"Completed: {hand_history.completed_at}")
        
        # Winner information
        if winner_info and 'winners' in winner_info:
            logger.info(f"WINNER(S):")
            for i, winner in enumerate(winner_info['winners'], 1):
                logger.info(f"   {i}. {winner['player_name']} - ${winner['winning_amount']}")
                if 'hand_name' in winner:
                    logger.info(f"      Hand: {winner['hand_name']}")
                if 'reason' in winner:
                    logger.info(f"      Reason: {winner['reason']}")
        
        # Community cards
        community_cards = hand_history.get_community_cards()
        if community_cards:
            logger.info(f"Community Cards: {', '.join(community_cards)}")
        
        # Player hole cards
        player_cards = hand_history.get_player_cards()
        if player_cards:
            logger.info(f"Player Hole Cards:")
            for player_name, cards in player_cards.items():
                logger.info(f"   {player_name}: {', '.join(cards)}")
        
        # Actions summary
        actions = hand_history.get_actions()
        if actions:
            logger.info(f"Actions Summary ({len(actions)} total):")
            current_phase = None
            for action in actions:
                if action['phase'] != current_phase:
                    current_phase = action['phase']
                    logger.info(f"   {current_phase}:")
                amount_str = f" ${action['amount']}" if action['amount'] > 0 else ""
                logger.info(f"     {action['player']}: {action['action']}{amount_str}")
        
        logger.info(f"{'='*60}")
        logger.info(f"Game continues... Next hand will be #{current_hand_number + 1}")
        logger.info(f"{'='*60}")

    @staticmethod
    @transaction.atomic
    def _start_new_hand(game):
        """Start a new hand after the previous one ended."""
        logger.info(f"Starting new hand for game {game.id}")
        
        # Check if we have enough players with money to continue (excluding cashed out players)
        player_games = PlayerGame.objects.filter(game=game)
        players_with_money = [pg for pg in player_games if pg.stack > 0 and not pg.cashed_out]
        
        if len(players_with_money) < 2:
            # End the game if not enough players have money
            logger.info(f"Game {game.id} ended: only {len(players_with_money)} players with money")
            game.status = 'FINISHED'
            game.save()
            return
        
        # Reset players who have money to active and clear their cards (exclude cashed out players)
        for pg in player_games:
            if pg.stack > 0 and not pg.cashed_out:
                pg.is_active = True
                pg.cards = None
                pg.current_bet = 0
                pg.total_bet = 0
                pg.ready_for_next_hand = False  # Reset readiness status
                pg.save()
            elif not pg.cashed_out:  # Only deactivate if not cashed out (cashed out players remain at table as spectators)
                pg.is_active = False
                pg.ready_for_next_hand = False  # Reset readiness status
                pg.save()
        
        # Get active players (those with money and not cashed out)
        active_players = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).order_by('seat_position')
        active_count = active_players.count()
        
        if active_count >= 2:
            current_dealer_pos = game.dealer_position
            next_dealer_pos = (current_dealer_pos + 1) % active_count
            game.dealer_position = next_dealer_pos
            logger.debug(f"Dealer position moved from {current_dealer_pos} to {next_dealer_pos}")
            
            # Reset game state
            game.phase = 'PREFLOP'
            game.community_cards = None
            game.current_bet = 0
            game.winner_info = None
            
            # Deal new cards
            deck = Deck()
            deck.shuffle()
            
            # Deal cards to players
            logger.debug(f"Dealing new cards to {active_count} players")
            for pg in active_players:
                cards = deck.deal(2)
                card_strings = [str(card) for card in cards]
                pg.set_cards(card_strings)
                pg.save()
                logger.debug(f"Dealt to {pg.player.user.username}: {card_strings}")
            
            # Post blinds
            num_players = active_players.count()
            small_blind_pos = (game.dealer_position + 1) % num_players
            big_blind_pos = (game.dealer_position + 2) % num_players
            
            active_players_list = list(active_players)
            
            # Post small blind (stack deduction delayed until betting round ends)
            small_blind_player = active_players_list[small_blind_pos]
            small_blind_amount = min(game.table.small_blind, small_blind_player.stack)
            small_blind_player.current_bet = small_blind_amount
            small_blind_player.total_bet = small_blind_amount
            small_blind_player.save()
            
            # Post big blind (stack deduction delayed until betting round ends)
            big_blind_player = active_players_list[big_blind_pos]
            big_blind_amount = min(game.table.big_blind, big_blind_player.stack)
            big_blind_player.current_bet = big_blind_amount
            big_blind_player.total_bet = big_blind_amount
            big_blind_player.save()
            
            # Note: Blinds will be added to pot when first betting round ends
            
            # Set current bet to big blind
            game.current_bet = big_blind_amount
            
            # Set current player (after big blind)
            current_player_pos = (big_blind_pos + 1) % num_players
            current_player = active_players_list[current_player_pos].player
            game.current_player = current_player
            logger.debug(f"First to act in new hand: {current_player.user.username}")
            
            # Increment hand count for the new hand
            game.hand_count += 1
            game.save()
            logger.info(f"New hand started - Hand #{game.hand_count}, {active_count} players, pot: ${game.pot}")
            
            # Check if the current player is a bot and schedule their action
            if game.current_player and game.current_player.is_bot:
                GameService._schedule_bot_action(game.id)

    @staticmethod
    def broadcast_game_update(game_id):
        """
        Broadcast game update to all connected clients.
        For card visibility, we'll send all data and let the frontend handle visibility.
        """
        from ..serializers import GameSerializer
        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            logger.error(f"Cannot broadcast update - game {game_id} not found")
            return
        
        # Log the broadcast details
        player_count = game.playergame_set.filter(is_active=True, cashed_out=False).count()
        logger.info(f"Broadcasting update for game {game_id} - Status: {game.status}, Phase: {game.phase}, Active players: {player_count}")
        
        # Check if this is a hand completion broadcast
        if hasattr(game, 'winner_info') and game.winner_info:
            winner_info = game.get_winner_info()  # Use the method to get parsed JSON
            if winner_info and winner_info.get('winners'):
                winner_names = [w.get('player_name', 'Unknown') for w in winner_info['winners']]
                if len(winner_names) == 1:
                    logger.info(f"Broadcasting hand completion - Winner: {winner_names[0]}")
                else:
                    logger.info(f"Broadcasting hand completion - Winners: {', '.join(winner_names)}")
        
        # Create serializer without user context - cards will be handled on frontend
        serializer = GameSerializer(game)
        
        # Convert to JSON and back to ensure Decimal objects are properly serialized
        # This prevents msgpack serialization errors in channels-redis
        serialized_data = json.loads(json.dumps(serializer.data, cls=DjangoJSONEncoder))
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'game_{game_id}',
            {
                'type': 'game_update', 
                'data': serialized_data
            }
        )
        
        logger.debug(f"Broadcast completed for game {game_id}")

    @staticmethod
    def broadcast_game_summary_available(game_id, summary_data):
        """
        Broadcast special notification that a game summary is available to all connected clients.
        This is sent when all players have cashed out and the game summary has been generated.
        """
        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            logger.error(f"Cannot broadcast game summary - game {game_id} not found")
            return
        
        logger.info(f"Broadcasting game summary availability for game {game_id}")
        
        # Create broadcast message with game summary data
        broadcast_data = {
            'type': 'game_summary_available',
            'game_id': game_id,
            'game_summary': summary_data,
            'message': 'Game summary is now available - all players have cashed out',
            'game_status': game.status,
            'total_hands': game.hand_count
        }
        
        # Convert to JSON and back to ensure Decimal objects are properly serialized
        # This prevents msgpack serialization errors in channels-redis
        serialized_broadcast_data = json.loads(json.dumps(broadcast_data, cls=DjangoJSONEncoder))
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'game_{game_id}',
            {
                'type': 'game_summary_notification',
                'data': serialized_broadcast_data
            }
        )
        
        logger.info(f"Game summary broadcast completed for game {game_id} - {len(summary_data.get('players', []))} players included")

        # Call this method after game state changes, for example:
        # At the end of process_action
        # At the end of start_game
        # At the end of _move_to_next_phase
        # At the end of _showdown
        # At the end of _end_hand
    
    # Bot Management Functions
    
    @staticmethod
    def _auto_ready_bots(game):
        """
        Automatically mark all bot players as ready for the next hand.
        Called after a hand ends to ensure bots don't block game progression.
        """
        # Get all eligible bot players (not cashed out, have stack > 0)
        bot_players = PlayerGame.objects.filter(
            game=game, 
            player__is_bot=True, 
            cashed_out=False,
            stack__gt=0
        )
        
        bot_count = 0
        for bot_pg in bot_players:
            if not bot_pg.ready_for_next_hand:
                bot_pg.ready_for_next_hand = True
                bot_pg.save()
                bot_count += 1
                logger.info(f"🤖 Bot {bot_pg.player.user.username} auto-readied for next hand")
        
        if bot_count > 0:
            logger.info(f"🤖 Auto-readied {bot_count} bot players for next hand in game {game.id}")
        
        return bot_count
    
    @staticmethod
    def _check_and_start_next_hand(game):
        """
        Check if all eligible players are ready and start the next hand if so.
        Called after bots are auto-readied to seamlessly continue the game.
        """
        # Get all eligible players (not cashed out, have stack > 0)
        all_eligible_players = PlayerGame.objects.filter(
            game=game, 
            cashed_out=False,
            stack__gt=0
        )
        ready_eligible_players = all_eligible_players.filter(ready_for_next_hand=True)
        
        total_count = all_eligible_players.count()
        ready_count = ready_eligible_players.count()
        
        logger.info(f"📊 Ready check: {ready_count}/{total_count} eligible players ready for next hand")
        
        # If all eligible players are ready and we have enough for a hand, start next hand
        if total_count > 1 and ready_count == total_count:
            logger.info(f"🎯 All players ready! Auto-starting next hand for game {game.id}")
            
            # Clear winner info first
            game.winner_info = None
            game.save()
            
            # Start the new hand
            GameService._start_new_hand(game)
            
            # Broadcast update to show new hand started
            GameService.broadcast_game_update(game.id)
            return True
        
        return False
    
    @staticmethod
    def _auto_cash_out_all_bots(game):
        """
        Automatically cash out all remaining bot players when only bots remain.
        Called when a human cashes out and only bots are left playing.
        """
        # Get all bot players who haven't cashed out yet (regardless of active status)
        # because bots may be inactive after folding but still need to be cashed out
        bot_players = PlayerGame.objects.filter(
            game=game, 
            player__is_bot=True, 
            cashed_out=False,
            left_table=False
        )
        
        cashed_out_count = 0
        for bot_pg in bot_players:
            # Cash out the bot with their current stack
            bot_pg.cashed_out = True
            bot_pg.is_active = False
            bot_pg.final_stack = bot_pg.stack  # Record final stack for tracking
            bot_pg.save()
            cashed_out_count += 1
            logger.info(f"🤖💰 Bot {bot_pg.player.user.username} auto-cashed out with ${bot_pg.stack}")
        
        if cashed_out_count > 0:
            logger.info(f"🤖💰 Auto-cashed out {cashed_out_count} bot players - game ending")
            
            # End the game since no active players remain
            game.status = 'FINISHED'
            game.save()
            logger.info(f"🏁 Game {game.id} ended - only bots remained, all auto-cashed out")
        
        return cashed_out_count
    
    @staticmethod
    @transaction.atomic
    def create_bot_player(difficulty='BASIC', play_style='TIGHT_AGGRESSIVE', 
                         aggression_factor=0.5, bluff_frequency=0.1):
        """
        Create a new bot player with the specified configuration.
        
        Args:
            difficulty: Bot difficulty level ('BASIC', 'INTERMEDIATE', 'ADVANCED')
            play_style: Bot play style ('TIGHT_PASSIVE', 'TIGHT_AGGRESSIVE', 'LOOSE_PASSIVE', 'LOOSE_AGGRESSIVE')
            aggression_factor: Aggression level (0.0-1.0)
            bluff_frequency: Bluffing frequency (0.0-1.0)
        
        Returns:
            Created BotPlayer instance
        """
        from django.contrib.auth.models import User
        import random
        
        # Generate unique bot name
        bot_names = [
            'PokerBot', 'ChipChaser', 'BluffMaster', 'CardShark', 'AceHunter',
            'FullHouseBot', 'RiverRat', 'FlopFlopper', 'AllInAnnie', 'CheckChase',
            'BetBot', 'CallCarl', 'RaiseRay', 'FoldFred', 'PotPusher'
        ]
        
        # Find an available bot name
        base_name = random.choice(bot_names)
        counter = 1
        username = base_name
        
        while User.objects.filter(username=username).exists():
            username = f"{base_name}{counter}"
            counter += 1
        
        # Create user account for the bot
        user = User.objects.create_user(
            username=username,
            email=f"{username}@bots.example.com",
            password='bot_password_unused',
            first_name='Bot',
            last_name=username
        )
        
        # Create player instance
        player = Player.objects.create(
            user=user,
            is_bot=True
        )
        
        # Create bot configuration
        bot_player = BotPlayer.objects.create(
            player=player,
            difficulty=difficulty,
            play_style=play_style,
            aggression_factor=aggression_factor,
            bluff_frequency=bluff_frequency
        )
        
        logger.info(f"Created bot player: {username} ({difficulty}/{play_style})")
        return bot_player
    
    @staticmethod
    @transaction.atomic
    def add_bot_to_table(table, buy_in_amount, difficulty='BASIC', play_style='TIGHT_AGGRESSIVE'):
        """
        Add a bot player to a poker table.
        
        Args:
            table: PokerTable instance to add bot to
            buy_in_amount: Amount of chips for the bot to buy in with
            difficulty: Bot difficulty level
            play_style: Bot play style
        
        Returns:
            Created BotPlayer instance
        """
        # Check if table has space
        current_game = Game.objects.filter(table=table, status='WAITING').first()
        if current_game:
            current_players = PlayerGame.objects.filter(game=current_game).count()
            if current_players >= table.max_players:
                raise ValueError("Table is full")
        
        # Create bot player
        bot_player = GameService.create_bot_player(
            difficulty=difficulty,
            play_style=play_style
        )
        
        # If there's a waiting game, add the bot to it
        if current_game:
            # Find next available seat
            occupied_seats = set(
                PlayerGame.objects.filter(game=current_game)
                .values_list('seat_position', flat=True)
            )
            seat_position = 0
            while seat_position in occupied_seats:
                seat_position += 1
            
            PlayerGame.objects.create(
                player=bot_player.player,
                game=current_game,
                seat_position=seat_position,
                stack=buy_in_amount,
                starting_stack=buy_in_amount,
                is_active=True
            )
            
            logger.info(f"Added bot {bot_player.player.user.username} to existing game {current_game.id} "
                       f"at seat {seat_position} with ${buy_in_amount}")
        
        return bot_player
    
    @staticmethod
    @transaction.atomic
    def remove_bot_from_game(game, bot_player):
        """
        Remove a bot player from a game.
        
        Args:
            game: Game instance
            bot_player: BotPlayer instance to remove
        """
        try:
            player_game = PlayerGame.objects.get(game=game, player=bot_player.player)
            
            # If game is in progress, cash out the bot
            if game.status == 'PLAYING':
                player_game.cash_out()
                logger.info(f"Cashed out bot {bot_player.player.user.username} from game {game.id}")
            else:
                # If game hasn't started, just remove the bot
                player_game.delete()
                logger.info(f"Removed bot {bot_player.player.user.username} from waiting game {game.id}")
                
        except PlayerGame.DoesNotExist:
            logger.warning(f"Bot {bot_player.player.user.username} not found in game {game.id}")
    
    @staticmethod
    def get_available_bots():
        """
        Get a list of available bot players not currently in any active games.
        
        Returns:
            QuerySet of BotPlayer instances
        """
        # Get bots that are not in any active games
        active_bot_ids = PlayerGame.objects.filter(
            game__status__in=['WAITING', 'PLAYING'],
            player__is_bot=True,
            cashed_out=False,
            left_table=False
        ).values_list('player_id', flat=True)
        
        available_bots = BotPlayer.objects.exclude(player_id__in=active_bot_ids)
        return available_bots
    
    @staticmethod
    def delete_bot_player(bot_player):
        """
        Permanently delete a bot player and their associated user account.
        
        Args:
            bot_player: BotPlayer instance to delete
        """
        username = bot_player.player.user.username
        user = bot_player.player.user
        
        # Remove from any games first
        active_games = Game.objects.filter(
            playergame__player=bot_player.player,
            status__in=['WAITING', 'PLAYING']
        )
        
        for game in active_games:
            GameService.remove_bot_from_game(game, bot_player)
        
        # Delete the user account (this will cascade to Player and BotPlayer)
        user.delete()
        
        logger.info(f"Deleted bot player: {username}")
    
    @staticmethod
    def get_bot_game_stats(bot_player):
        """
        Get game statistics for a bot player.
        
        Args:
            bot_player: BotPlayer instance
        
        Returns:
            Dictionary with bot statistics
        """
        # Get all completed games for this bot
        player_games = PlayerGame.objects.filter(
            player=bot_player.player,
            game__status='FINISHED'
        )
        
        total_games = player_games.count()
        if total_games == 0:
            return {
                'total_games': 0,
                'total_winnings': 0,
                'avg_winnings_per_game': 0,
                'win_rate': 0
            }
        
        total_winnings = sum(
            pg.calculate_win_loss() or 0 for pg in player_games
        )
        avg_winnings = total_winnings / total_games
        wins = len([pg for pg in player_games if (pg.calculate_win_loss() or 0) > 0])
        win_rate = wins / total_games if total_games > 0 else 0
        
        return {
            'total_games': total_games,
            'total_winnings': float(total_winnings),
            'avg_winnings_per_game': float(avg_winnings),
            'win_rate': win_rate
        }