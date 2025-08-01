"""
Django management command to create a test poker table with 8 players for mobile layout testing.

This command creates:
- 8 test users with varied names (to test name abbreviation)  
- A poker table configured for 8 players
- A game in progress with all 8 players at different states
- Realistic game state with community cards, pot, and betting
- Players with different stack sizes and bet amounts
- Some players folded, active, and at different turn positions

Usage:
    USE_SQLITE=true python manage.py create_test_table
    USE_SQLITE=true python manage.py create_test_table --table-name "Test Table 2"
    USE_SQLITE=true python manage.py create_test_table --clean  # Remove existing test data first
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from decimal import Decimal
import json

from poker_api.models import PokerTable, Player, Game, PlayerGame, GameAction


class Command(BaseCommand):
    help = 'Create a test poker table with 8 players for mobile layout testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--table-name',
            type=str,
            default='Mobile Test Table',
            help='Name for the test table (default: "Mobile Test Table")'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Remove existing test data before creating new data'
        )
        parser.add_argument(
            '--small-blind',
            type=float,
            default=1.00,
            help='Small blind amount (default: 1.00)'
        )
        parser.add_argument(
            '--big-blind',
            type=float,
            default=2.00,
            help='Big blind amount (default: 2.00)'
        )

    def handle(self, *args, **options):
        table_name = options['table_name']
        clean = options['clean']
        small_blind = Decimal(str(options['small_blind']))
        big_blind = Decimal(str(options['big_blind']))

        self.stdout.write(self.style.SUCCESS(
            f'Creating test poker table: {table_name}'
        ))

        try:
            with transaction.atomic():
                # Clean up existing test data if requested
                if clean:
                    self._clean_test_data(table_name)

                # Create test users and players
                test_players = self._create_test_users()

                # Create poker table
                table = self._create_poker_table(table_name, small_blind, big_blind)

                # Create game in progress
                game = self._create_game(table)

                # Add players to the game with varied states
                self._add_players_to_game(game, test_players)

                # Set up game state (community cards, pot, etc.)
                self._setup_game_state(game)

                self.stdout.write(self.style.SUCCESS(
                    f'Successfully created test table "{table_name}" with ID {table.id}'
                ))
                self.stdout.write(self.style.SUCCESS(
                    f'Game ID: {game.id}'
                ))
                self.stdout.write(self.style.SUCCESS(
                    f'8 test players created and seated'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Error creating test table: {str(e)}'
            ))
            raise CommandError(f'Failed to create test table: {str(e)}')

    def _clean_test_data(self, table_name):
        """Remove existing test data."""
        self.stdout.write('Cleaning existing test data...')
        
        # Delete existing table and related data
        PokerTable.objects.filter(name=table_name).delete()
        
        # Clean up test users (those with test_ prefix)
        test_usernames = [
            'test_alice', 'test_bob_smith', 'test_charlie_johnson', 
            'test_diana_williams', 'test_edward_brown', 'test_fiona_davis',
            'test_george_miller', 'test_helena_wilson'
        ]
        User.objects.filter(username__in=test_usernames).delete()

    def _create_test_users(self):
        """Create 8 test users with varied names for testing name abbreviation."""
        test_users_data = [
            {'username': 'test_alice', 'first_name': 'Alice', 'last_name': 'Smith'},
            {'username': 'test_bob_smith', 'first_name': 'Bob', 'last_name': 'Smith'},
            {'username': 'test_charlie_johnson', 'first_name': 'Charlie', 'last_name': 'Johnson'},
            {'username': 'test_diana_williams', 'first_name': 'Diana', 'last_name': 'Williams'},
            {'username': 'test_edward_brown', 'first_name': 'Edward', 'last_name': 'Brown'},
            {'username': 'test_fiona_davis', 'first_name': 'Fiona', 'last_name': 'Davis'},
            {'username': 'test_george_miller', 'first_name': 'George', 'last_name': 'Miller'},
            {'username': 'test_helena_wilson', 'first_name': 'Helena', 'last_name': 'Wilson'},
        ]

        test_players = []
        for user_data in test_users_data:
            # Create or get user
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'email': f"{user_data['username']}@test.com",
                }
            )
            
            # Create or get player
            player, created = Player.objects.get_or_create(user=user)
            test_players.append(player)
            
            if created:
                self.stdout.write(f'Created test user: {user.username}')

        return test_players

    def _create_poker_table(self, table_name, small_blind, big_blind):
        """Create a poker table for 8 players."""
        table, created = PokerTable.objects.get_or_create(
            name=table_name,
            defaults={
                'max_players': 8,
                'small_blind': small_blind,
                'big_blind': big_blind,
                'min_buy_in': big_blind * 50,  # 100 BB min
                'max_buy_in': big_blind * 200,  # 400 BB max
            }
        )
        
        if created:
            self.stdout.write(f'Created poker table: {table_name}')
        else:
            self.stdout.write(f'Using existing table: {table_name}')
            
        return table

    def _create_game(self, table):
        """Create a game in progress."""
        # Check if there's already an active game
        existing_game = Game.objects.filter(
            table=table,
            status__in=['WAITING', 'PLAYING']
        ).first()
        
        if existing_game:
            self.stdout.write(f'Using existing game: {existing_game.id}')
            return existing_game

        game = Game.objects.create(
            table=table,
            status='PLAYING',
            phase='FLOP',  # Game in progress on the flop
            pot=Decimal('47.50'),  # Realistic pot size
            current_bet=Decimal('8.00'),  # Current bet to call
            dealer_position=2,  # Dealer at seat 2
            hand_count=12,  # Some hands have been played
        )
        
        self.stdout.write(f'Created game in progress: {game.id}')
        return game

    def _add_players_to_game(self, game, players):
        """Add all 8 players to the game with realistic states."""
        
        # Player configurations - mix of active, folded, different stack sizes
        player_configs = [
            {  # Seat 0 - Alice (Active, current turn, good stack)
                'seat': 0, 'stack': Decimal('156.75'), 'current_bet': Decimal('8.00'),
                'total_bet': Decimal('13.00'), 'is_active': True, 'cards': ['AS', 'KH']
            },
            {  # Seat 1 - Bob (Active, called, medium stack)  
                'seat': 1, 'stack': Decimal('89.25'), 'current_bet': Decimal('8.00'),
                'total_bet': Decimal('13.00'), 'is_active': True, 'cards': ['QC', 'JD']
            },
            {  # Seat 2 - Charlie (Dealer, folded this hand)
                'seat': 2, 'stack': Decimal('203.50'), 'current_bet': Decimal('0.00'),
                'total_bet': Decimal('2.00'), 'is_active': False, 'cards': ['7H', '2C']
            },
            {  # Seat 3 - Diana (Small blind, active, short stack)
                'seat': 3, 'stack': Decimal('34.75'), 'current_bet': Decimal('8.00'),
                'total_bet': Decimal('9.00'), 'is_active': True, 'cards': ['10S', '9S']
            },
            {  # Seat 4 - Edward (Big blind, raised, big stack)
                'seat': 4, 'stack': Decimal('287.25'), 'current_bet': Decimal('8.00'),
                'total_bet': Decimal('10.00'), 'is_active': True, 'cards': ['AH', 'AC']
            },
            {  # Seat 5 - Fiona (Folded, medium stack)
                'seat': 5, 'stack': Decimal('122.00'), 'current_bet': Decimal('0.00'),
                'total_bet': Decimal('5.00'), 'is_active': False, 'cards': ['5D', '3H']
            },
            {  # Seat 6 - George (Active, called, decent stack) 
                'seat': 6, 'stack': Decimal('98.50'), 'current_bet': Decimal('8.00'),
                'total_bet': Decimal('13.00'), 'is_active': True, 'cards': ['KD', 'QS']
            },
            {  # Seat 7 - Helena (Folded, low stack)
                'seat': 7, 'stack': Decimal('67.25'), 'current_bet': Decimal('0.00'),
                'total_bet': Decimal('0.00'), 'is_active': False, 'cards': ['8C', '4S']
            }
        ]

        for i, config in enumerate(player_configs):
            player_game = PlayerGame.objects.create(
                player=players[i],
                game=game,
                seat_position=config['seat'],
                stack=config['stack'],
                starting_stack=Decimal('200.00'),  # Everyone started with $200
                current_bet=config['current_bet'],
                total_bet=config['total_bet'],
                is_active=config['is_active'],
            )
            
            # Set player's hole cards
            player_game.set_cards(config['cards'])
            player_game.save()

        # Set current player to seat 0 (Alice's turn)
        game.current_player = players[0]
        game.save()

        self.stdout.write('Added 8 players to game with varied states')

    def _setup_game_state(self, game):
        """Set up realistic game state with community cards."""
        
        # Community cards for the flop (3 cards showing)
        community_cards = ['KS', '9H', '2D']  # King high flop
        game.set_community_cards(community_cards)
        
        # Create some realistic game actions for this hand
        player_games = PlayerGame.objects.filter(game=game).order_by('seat_position')
        
        # Pre-flop actions
        actions = [
            # Edward (seat 4, big blind) checks
            {'player': player_games[4], 'action': 'CHECK', 'amount': 0, 'phase': 'PREFLOP'},
            # Fiona (seat 5) raises to $5
            {'player': player_games[5], 'action': 'RAISE', 'amount': 5, 'phase': 'PREFLOP'},
            # George (seat 6) calls $5  
            {'player': player_games[6], 'action': 'CALL', 'amount': 5, 'phase': 'PREFLOP'},
            # Helena (seat 7) folds
            {'player': player_games[7], 'action': 'FOLD', 'amount': 0, 'phase': 'PREFLOP'},
            # Alice (seat 0) calls $5
            {'player': player_games[0], 'action': 'CALL', 'amount': 5, 'phase': 'PREFLOP'},
            # Bob (seat 1) calls $5
            {'player': player_games[1], 'action': 'CALL', 'amount': 5, 'phase': 'PREFLOP'},
            # Charlie (seat 2) folds  
            {'player': player_games[2], 'action': 'FOLD', 'amount': 0, 'phase': 'PREFLOP'},
            # Diana (seat 3, small blind) calls $4 more
            {'player': player_games[3], 'action': 'CALL', 'amount': 4, 'phase': 'PREFLOP'},
            # Edward (seat 4) calls $3 more
            {'player': player_games[4], 'action': 'CALL', 'amount': 3, 'phase': 'PREFLOP'},
            
            # Flop actions (current betting round)
            # Diana (small blind) checks
            {'player': player_games[3], 'action': 'CHECK', 'amount': 0, 'phase': 'FLOP'},
            # Edward bets $8
            {'player': player_games[4], 'action': 'BET', 'amount': 8, 'phase': 'FLOP'},
            # Fiona folds
            {'player': player_games[5], 'action': 'FOLD', 'amount': 0, 'phase': 'FLOP'},
            # George calls $8
            {'player': player_games[6], 'action': 'CALL', 'amount': 8, 'phase': 'FLOP'},
            # Alice calls $8  
            {'player': player_games[0], 'action': 'CALL', 'amount': 8, 'phase': 'FLOP'},
            # Bob calls $8
            {'player': player_games[1], 'action': 'CALL', 'amount': 8, 'phase': 'FLOP'},
            # Diana calls $8 (all in or close to it)
            {'player': player_games[3], 'action': 'CALL', 'amount': 8, 'phase': 'FLOP'},
        ]

        # Create GameAction records
        for action_data in actions:
            GameAction.objects.create(
                player_game=action_data['player'],
                action_type=action_data['action'],
                amount=Decimal(str(action_data['amount'])),
                phase=action_data['phase']
            )

        game.save()
        self.stdout.write('Set up realistic game state with community cards and actions')