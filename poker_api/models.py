# poker_api/models.py
# 
# Database models for Texas Hold'em poker application.
# These models define the core data structures for managing poker tables,
# games, players, and all related game state information.

from django.db import models
from django.contrib.auth.models import User
import json

class PokerTable(models.Model):
    """
    Represents a poker table with betting limits and player capacity.
    
    A table defines the structure for poker games including:
    - Betting limits (small/big blinds)
    - Buy-in requirements (min/max amounts players can start with)
    - Player capacity (typically 2-9 players for Texas Hold'em)
    
    Multiple games can be played at the same table over time.
    """
    name = models.CharField(max_length=100)                                    # Human-readable table name
    max_players = models.IntegerField(default=9)                              # Maximum seats at table
    small_blind = models.DecimalField(max_digits=10, decimal_places=2)        # Small blind amount
    big_blind = models.DecimalField(max_digits=10, decimal_places=2)          # Big blind amount (min bet)
    min_buy_in = models.DecimalField(max_digits=10, decimal_places=2)         # Minimum chips to start
    max_buy_in = models.DecimalField(max_digits=10, decimal_places=2)         # Maximum chips to start
    created_at = models.DateTimeField(auto_now_add=True)                      # When table was created
    
    def __str__(self):
        """Returns the string representation of the poker table."""
        return self.name

class Player(models.Model):
    """
    Represents a poker player linked to a Django User account.
    
    This model extends the Django User model to store poker-specific
    player information. Each User can have one Player instance.
    Players can be either human users or AI bots.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)               # Link to Django auth user
    is_bot = models.BooleanField(default=False)                               # True if this is an AI bot player
    
    def __str__(self):
        """Returns the string representation of the player."""
        bot_prefix = "[BOT] " if self.is_bot else ""
        return f"{bot_prefix}{self.user.username}"

class BotPlayer(models.Model):
    """
    Represents an AI bot player with configurable difficulty and play style.
    
    This model stores bot-specific configuration that determines how the bot
    makes decisions during poker games.
    """
    DIFFICULTY_CHOICES = [
        ('BASIC', 'Basic'),           # Simple tight/aggressive play
        ('INTERMEDIATE', 'Intermediate'),  # Considers position and pot odds
        ('ADVANCED', 'Advanced'),     # Advanced strategy with bluffing
    ]
    
    PLAY_STYLE_CHOICES = [
        ('TIGHT_PASSIVE', 'Tight Passive'),      # Plays few hands, rarely bets aggressively
        ('TIGHT_AGGRESSIVE', 'Tight Aggressive'), # Plays few hands, bets aggressively with good hands
        ('LOOSE_PASSIVE', 'Loose Passive'),       # Plays many hands, calls frequently
        ('LOOSE_AGGRESSIVE', 'Loose Aggressive'), # Plays many hands, bets and raises frequently
    ]
    
    player = models.OneToOneField(Player, on_delete=models.CASCADE)           # Link to Player instance
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='BASIC')
    play_style = models.CharField(max_length=20, choices=PLAY_STYLE_CHOICES, default='TIGHT_AGGRESSIVE')
    aggression_factor = models.FloatField(default=0.5)                        # 0.0 = very passive, 1.0 = very aggressive
    bluff_frequency = models.FloatField(default=0.1)                          # Probability of bluffing (0.0-1.0)
    thinking_time_min = models.FloatField(default=1.0)                        # Minimum seconds to "think"
    thinking_time_max = models.FloatField(default=3.0)                        # Maximum seconds to "think"
    
    def __str__(self):
        """Returns the string representation of the bot player."""
        return f"Bot: {self.player.user.username} ({self.difficulty}/{self.play_style})"

class Game(models.Model):
    """
    Represents a single poker game instance with complete game state.
    
    This is the central model that tracks all aspects of an active poker game:
    - Game progression (status, phase, current player)
    - Betting state (pot, current bet amount)
    - Card dealing (community cards, dealer position)
    - Game history and results
    
    Key betting-related fields:
    - pot: Total money collected from all betting rounds
    - current_bet: Amount all players must match in current round
    - current_player: Whose turn it is to act
    """
    # Game status options
    GAME_STATUS_CHOICES = [
        ('WAITING', 'Waiting for players'),    # Game created but not started
        ('PLAYING', 'Game in progress'),       # Active game with hands being played
        ('FINISHED', 'Game finished'),         # Game completed, no more hands
    ]

    # Texas Hold'em phase progression
    GAME_PHASE_CHOICES = [
        ('PREFLOP', 'Pre-flop'),                       # Before community cards dealt
        ('FLOP', 'Flop'),                             # First 3 community cards dealt
        ('TURN', 'Turn'),                             # 4th community card dealt
        ('RIVER', 'River'),                           # 5th community card dealt
        ('SHOWDOWN', 'Showdown'),                     # Hand evaluation and winner determination
        ('WAITING_FOR_PLAYERS', 'Waiting for players to be ready'),  # Transitional state
    ]

    # Core game relationships and state
    table = models.ForeignKey(PokerTable, on_delete=models.CASCADE)          # Which table this game is at
    status = models.CharField(max_length=20, choices=GAME_STATUS_CHOICES, default='WAITING')
    phase = models.CharField(max_length=20, choices=GAME_PHASE_CHOICES, null=True, blank=True)
    
    # Critical betting state fields
    pot = models.DecimalField(max_digits=10, decimal_places=2, default=0)    # Total money in the pot
    current_bet = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Current bet to match
    
    # Player and dealing management
    dealer_position = models.IntegerField(default=0)                         # Dealer position (0-indexed)
    current_player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='games_to_play')
    
    # Card and result tracking (stored as JSON)
    community_cards = models.CharField(max_length=100, blank=True, null=True)  # 5 community cards
    winner_info = models.TextField(blank=True, null=True)                     # Hand winner details
    game_summary = models.TextField(blank=True, null=True)                    # Final game results
    
    # Game statistics and metadata
    hand_count = models.PositiveIntegerField(default=0)                       # Number of completed hands
    created_at = models.DateTimeField(auto_now_add=True)                      # When game was created
    
    def __str__(self):
        """Returns the string representation of the game."""
        return f"Game at {self.table.name}"
    
    def set_community_cards(self, cards_list):
        """Stores community cards as JSON string."""
        self.community_cards = json.dumps(cards_list)
    
    def get_community_cards(self):
        """Retrieves community cards from JSON string."""
        if self.community_cards:
            return json.loads(self.community_cards)
        return []
    
    def set_winner_info(self, winner_data):
        """Stores winner information as JSON string."""
        self.winner_info = json.dumps(winner_data)
    
    def get_winner_info(self):
        """Retrieves winner information from JSON string."""
        if self.winner_info:
            return json.loads(self.winner_info)
        return None
    
    def set_game_summary(self, summary_data):
        """Stores game summary as JSON string."""
        self.game_summary = json.dumps(summary_data)
    
    def get_game_summary(self):
        """Retrieves game summary from JSON string."""
        if self.game_summary:
            return json.loads(self.game_summary)
        return None
    
    def generate_game_summary(self):
        """Generate and store game summary when game ends."""
        from django.utils import timezone
        
        # Get all players who participated in this game
        all_players = PlayerGame.objects.filter(game=self)
        
        summary_data = {
            'game_id': self.id,
            'table_name': self.table.name,
            'completed_at': timezone.now().isoformat(),
            'total_hands': self.hand_count,
            'players': []
        }
        
        for pg in all_players:
            win_loss = pg.calculate_win_loss()
            player_data = {
                'player_name': pg.player.user.username,
                'player_id': pg.player.id,
                'starting_stack': float(pg.starting_stack) if pg.starting_stack else 0,
                'final_stack': float(pg.final_stack) if pg.final_stack is not None else float(pg.stack),
                'win_loss': float(win_loss) if win_loss is not None else 0,
                'status': pg.status
            }
            summary_data['players'].append(player_data)
        
        # Sort players by win/loss (highest to lowest)
        summary_data['players'].sort(key=lambda x: x['win_loss'], reverse=True)
        
        self.set_game_summary(summary_data)
        self.status = 'FINISHED'
        self.save()
        
        # Create persistent GameSummary that survives table deletion
        game_summary = GameSummary.objects.create(
            game_id=self.id,
            table_name=self.table.name
        )
        game_summary.set_summary_data(summary_data)
        game_summary.save()
        
        # Add all participants to the summary so they can access it
        participant_users = [pg.player.user for pg in all_players]
        game_summary.participants.set(participant_users)
        
        return summary_data

class PlayerGame(models.Model):
    """
    Represents a player's participation in a specific poker game.
    
    This model tracks all player-specific state for a single game including:
    - Seat position and chip stack management
    - Current betting state for active betting rounds  
    - Player status (active, folded, cashed out, left)
    - Hole cards and betting history
    
    Critical betting-related fields:
    - stack: Current available chips for betting
    - current_bet: Amount bet in current betting round (reset each round)
    - total_bet: Total amount bet in current hand (cumulative across rounds)
    - is_active: Whether player is still in current hand (false if folded)
    """
    # Core relationships
    player = models.ForeignKey(Player, on_delete=models.CASCADE)              # Which player
    game = models.ForeignKey(Game, on_delete=models.CASCADE)                  # Which game
    seat_position = models.IntegerField()                                     # Position at table (0-indexed)
    
    # Chip stack management
    stack = models.DecimalField(max_digits=10, decimal_places=2)             # Current available chips
    starting_stack = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Initial buy-in amount
    final_stack = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)     # Final amount when leaving
    
    # Player status flags
    is_active = models.BooleanField(default=True)                            # Still in current hand (false if folded)
    cashed_out = models.BooleanField(default=False)                          # Cashed out but observing
    left_table = models.BooleanField(default=False)                          # Completely left the game
    left_at = models.DateTimeField(null=True, blank=True)                    # Timestamp when player left
    
    # Card and betting state
    cards = models.CharField(max_length=50, blank=True, null=True)           # Player's hole cards (JSON)
    current_bet = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Bet in current round
    total_bet = models.DecimalField(max_digits=10, decimal_places=2, default=0)    # Total bet in current hand
    ready_for_next_hand = models.BooleanField(default=False)                 # Ready for next hand to start
    
    class Meta:
        unique_together = [
            ['game', 'seat_position'],  # Each seat can only be occupied by one player
            ['game', 'player']          # Each player can only join a game once
        ]
    
    def __str__(self):
        """Returns the string representation of the player game."""
        return f"{self.player} at {self.game}"
    
    def set_cards(self, cards_list):
        """Stores player's hole cards as JSON string."""
        self.cards = json.dumps(cards_list)
    
    def get_cards(self):
        """Retrieves player's hole cards from JSON string."""
        if self.cards:
            return json.loads(self.cards)
        return []
    
    def cash_out(self):
        """Cash out the player - they become inactive but stay at the table."""
        self.is_active = False
        self.cashed_out = True
        self.save()
    
    def buy_back_in(self, amount):
        """Buy back in - only available if player is cashed out."""
        if self.cashed_out:
            self.stack = amount
            self.is_active = True
            self.cashed_out = False
            self.save()
    
    def can_leave_table(self):
        """Check if player can leave the table (only if cashed out)."""
        return self.cashed_out
    
    def can_buy_back_in(self):
        """Check if player can buy back in (only if cashed out)."""
        return self.cashed_out
    
    @property
    def status(self):
        """Return the current status of the player."""
        if self.left_table:
            return 'LEFT_EARLY'
        elif self.cashed_out:
            return 'CASHED_OUT'
        elif self.is_active:
            return 'ACTIVE'
        else:
            return 'INACTIVE'
    
    def calculate_win_loss(self):
        """Calculate win/loss amount for this player in the game."""
        if self.starting_stack is None:
            return None
        
        # If still playing, use current stack
        if not self.cashed_out and self.final_stack is None:
            current_amount = self.stack
        else:
            # Use final stack if available, otherwise current stack
            current_amount = self.final_stack if self.final_stack is not None else self.stack
        
        return current_amount - self.starting_stack
    
class GameAction(models.Model):
    """Represents a player's action during a poker game."""
    ACTION_CHOICES = [
        ('FOLD', 'Fold'),
        ('CHECK', 'Check'),
        ('CALL', 'Call'),
        ('BET', 'Bet'),
        ('RAISE', 'Raise'),
    ]
    
    PHASE_CHOICES = [
        ('PREFLOP', 'Pre-flop'),
        ('FLOP', 'Flop'),
        ('TURN', 'Turn'),
        ('RIVER', 'River'),
    ]
    
    player_game = models.ForeignKey(PlayerGame, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default='PREFLOP')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        """Returns the string representation of the game action."""
        if self.action_type in ['BET', 'RAISE']:
            return f"{self.player_game.player} {self.action_type} {self.amount}"
        return f"{self.player_game.player} {self.action_type}"

class HandHistory(models.Model):
    """Stores historical data for completed poker hands."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='hand_history')
    hand_number = models.PositiveIntegerField()
    winner_info = models.TextField()  # JSON data with winner details
    pot_amount = models.DecimalField(max_digits=10, decimal_places=2)
    community_cards = models.CharField(max_length=100, blank=True, null=True)  # JSON
    final_phase = models.CharField(max_length=20, choices=Game.GAME_PHASE_CHOICES)
    player_cards = models.TextField()  # JSON data with all player hole cards
    actions = models.TextField()  # JSON data with all actions taken during hand
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['game', 'hand_number']
        ordering = ['-completed_at']
    
    def __str__(self):
        """Returns the string representation of the hand history."""
        return f"Hand {self.hand_number} - Game {self.game.id}"
    
    def set_winner_info(self, winner_data):
        """Stores winner information as JSON string."""
        self.winner_info = json.dumps(winner_data)
    
    def get_winner_info(self):
        """Retrieves winner information from JSON string."""
        if self.winner_info:
            return json.loads(self.winner_info)
        return None
    
    def set_player_cards(self, cards_data):
        """Stores all players' hole cards as JSON string."""
        self.player_cards = json.dumps(cards_data)
    
    def get_player_cards(self):
        """Retrieves all players' hole cards from JSON string."""
        if self.player_cards:
            return json.loads(self.player_cards)
        return {}
    
    def set_actions(self, actions_data):
        """Stores all game actions as JSON string."""
        self.actions = json.dumps(actions_data)
    
    def get_actions(self):
        """Retrieves all game actions from JSON string."""
        if self.actions:
            return json.loads(self.actions)
        return []
    
    def set_community_cards(self, cards_list):
        """Stores community cards as JSON string."""
        self.community_cards = json.dumps(cards_list)
    
    def get_community_cards(self):
        """Retrieves community cards from JSON string."""
        if self.community_cards:
            return json.loads(self.community_cards)
        return []


class GameSummary(models.Model):
    """Persistent storage for game summaries that survive table deletion."""
    game_id = models.IntegerField()  # Original game ID (not foreign key since game may be deleted)
    table_name = models.CharField(max_length=100)
    summary_data = models.TextField()  # JSON string containing the complete summary
    created_at = models.DateTimeField(auto_now_add=True)
    participants = models.ManyToManyField(User, related_name='game_summaries')  # Users who can access this summary
    
    class Meta:
        ordering = ['-created_at']
    
    def set_summary_data(self, data):
        """Stores summary data as JSON string."""
        self.summary_data = json.dumps(data)
    
    def get_summary_data(self):
        """Retrieves summary data from JSON string."""
        if self.summary_data:
            return json.loads(self.summary_data)
        return None
    
    def __str__(self):
        return f"Game Summary - {self.table_name} (Game {self.game_id})"


# class Card(models.Model):
#     SUIT_CHOICES = [
#         ('S', 'Spades'),
#         ('H', 'Hearts'),
#         ('D', 'Diamonds'),
#         ('C', 'Clubs'),
#     ]
#     RANK_CHOICES = [
#         ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'), ('7', '7'),
#         ('8', '8'), ('9', '9'), ('10', '10'), ('J', 'Jack'), ('Q', 'Queen'),
#         ('K', 'King'), ('A', 'Ace'),
#     ]
#     suit = models.CharField(max_length=1, choices=SUIT_CHOICES)
#     rank = models.CharField(max_length=2, choices=RANK_CHOICES)
    
#     def __str__(self):
#         return f"{self.rank}{self.suit}"