# poker_api/management/commands/debug_bot_games.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from poker_api.models import Game, PlayerGame, Player, BotPlayer
from poker_api.services.game_service import GameService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Debug bot-related game issues and provide diagnostics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--game-id',
            type=int,
            help='Specific game ID to debug'
        )
        parser.add_argument(
            '--list-stuck',
            action='store_true',
            help='List games that might be stuck waiting for bot actions'
        )
        parser.add_argument(
            '--fix-stuck',
            action='store_true',
            help='Attempt to fix stuck bot games'
        )
        parser.add_argument(
            '--bot-stats',
            action='store_true',
            help='Show statistics for all bot players'
        )

    def handle(self, *args, **options):
        if options['game_id']:
            self.debug_specific_game(options['game_id'])
        elif options['list_stuck']:
            self.list_stuck_games()
        elif options['fix_stuck']:
            self.fix_stuck_games()
        elif options['bot_stats']:
            self.show_bot_stats()
        else:
            self.show_overall_status()

    def debug_specific_game(self, game_id):
        """Debug a specific game in detail."""
        self.stdout.write(f"\n🔍 Debugging Game {game_id}")
        self.stdout.write("=" * 50)
        
        try:
            game = Game.objects.get(id=game_id)
            
            # Basic game info
            self.stdout.write(f"Status: {game.status}")
            self.stdout.write(f"Phase: {game.phase}")
            self.stdout.write(f"Pot: ${game.pot}")
            self.stdout.write(f"Current Bet: ${game.current_bet}")
            self.stdout.write(f"Dealer Position: {game.dealer_position}")
            
            # Current player info
            if game.current_player:
                current_player = game.current_player
                self.stdout.write(f"\nCurrent Player: {current_player.user.username}")
                self.stdout.write(f"Is Bot: {current_player.is_bot}")
                
                if current_player.is_bot:
                    try:
                        bot_player = BotPlayer.objects.get(player=current_player)
                        self.stdout.write(f"Bot Config: {bot_player.difficulty} {bot_player.play_style}")
                        self.stdout.write(f"Aggression: {bot_player.aggression_factor}, Bluff: {bot_player.bluff_frequency}")
                    except BotPlayer.DoesNotExist:
                        self.stdout.write(self.style.ERROR("❌ Bot configuration missing!"))
            else:
                self.stdout.write("\nCurrent Player: None")
            
            # Player details
            self.stdout.write(f"\n👥 Players:")
            players = PlayerGame.objects.filter(game=game).order_by('seat_position')
            for pg in players:
                status_icons = []
                if pg.is_active:
                    status_icons.append("🟢")
                if pg.cashed_out:
                    status_icons.append("💰")
                if pg.left_table:
                    status_icons.append("🚪")
                if pg.player.is_bot:
                    status_icons.append("🤖")
                    
                status = "".join(status_icons) or "⚪"
                self.stdout.write(f"  Seat {pg.seat_position}: {status} {pg.player.user.username} - Stack: ${pg.stack}, Bet: ${pg.current_bet}")
            
            # Check for potential issues
            self.stdout.write(f"\n🔧 Diagnostics:")
            
            if game.status == 'PLAYING' and game.current_player and game.current_player.is_bot:
                self.stdout.write("⚠️  Game is waiting for bot action")
                
                # Check if bot has valid actions
                try:
                    player_game = PlayerGame.objects.get(game=game, player=game.current_player, is_active=True, cashed_out=False)
                    valid_actions = GameService._get_valid_actions(game, player_game)
                    self.stdout.write(f"   Valid actions: {valid_actions}")
                except PlayerGame.DoesNotExist:
                    self.stdout.write(self.style.ERROR("   ❌ Bot player game entry not found!"))
            
            active_players = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).count()
            if active_players < 2:
                self.stdout.write(f"⚠️  Only {active_players} active players - game should end")
            
        except Game.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Game {game_id} not found"))

    def list_stuck_games(self):
        """List games that might be stuck waiting for bot actions."""
        self.stdout.write("\n🔍 Checking for stuck bot games...")
        self.stdout.write("=" * 50)
        
        # Find games in PLAYING status where current player is a bot
        stuck_games = Game.objects.filter(
            status='PLAYING',
            current_player__is_bot=True
        )
        
        if not stuck_games.exists():
            self.stdout.write("✅ No games appear to be stuck on bot turns")
            return
        
        for game in stuck_games:
            self.stdout.write(f"\n🎮 Game {game.id} - Table: {game.table.name}")
            self.stdout.write(f"   Phase: {game.phase}, Pot: ${game.pot}")
            self.stdout.write(f"   Bot: {game.current_player.user.username}")
            
            # Check how long since last action
            from poker_api.models import GameAction
            last_action = GameAction.objects.filter(player_game__game=game).order_by('-timestamp').first()
            if last_action:
                time_since = timezone.now() - last_action.timestamp
                self.stdout.write(f"   Last action: {time_since.total_seconds():.0f}s ago")
                
                if time_since.total_seconds() > 60:  # More than 1 minute
                    self.stdout.write(self.style.WARNING("   ⚠️  Potentially stuck (>60s since last action)"))

    def fix_stuck_games(self):
        """Attempt to fix games stuck on bot turns."""
        self.stdout.write("\n🔧 Attempting to fix stuck bot games...")
        self.stdout.write("=" * 50)
        
        stuck_games = Game.objects.filter(
            status='PLAYING',
            current_player__is_bot=True
        )
        
        fixed_count = 0
        for game in stuck_games:
            self.stdout.write(f"\n🎮 Fixing Game {game.id}...")
            
            # Try to schedule bot action
            try:
                success = GameService._schedule_bot_action(game.id)
                if success:
                    self.stdout.write(f"   ✅ Bot action scheduled for {game.current_player.user.username}")
                    fixed_count += 1
                else:
                    # Try fallback mechanism
                    success = GameService._handle_bot_action_failure(game.id, "Manual fix attempt")
                    if success:
                        self.stdout.write(f"   🆘 Used fallback action for {game.current_player.user.username}")
                        fixed_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"   ❌ Could not fix game {game.id}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Error fixing game {game.id}: {str(e)}"))
        
        self.stdout.write(f"\n🎯 Fixed {fixed_count} games")

    def show_bot_stats(self):
        """Show statistics for all bot players."""
        self.stdout.write("\n🤖 Bot Player Statistics")
        self.stdout.write("=" * 50)
        
        bots = BotPlayer.objects.all().order_by('difficulty', 'play_style')
        
        if not bots.exists():
            self.stdout.write("No bot players found")
            return
        
        for bot in bots:
            stats = GameService.get_bot_game_stats(bot)
            
            self.stdout.write(f"\n🤖 {bot.player.user.username}")
            self.stdout.write(f"   Config: {bot.difficulty} {bot.play_style}")
            self.stdout.write(f"   Games: {stats['total_games']}")
            self.stdout.write(f"   Winnings: ${stats['total_winnings']:.2f}")
            self.stdout.write(f"   Win Rate: {stats['win_rate']:.1%}")
            
            # Check if bot is currently in any games
            current_games = PlayerGame.objects.filter(
                player=bot.player,
                game__status__in=['WAITING', 'PLAYING'],
                cashed_out=False,
                left_table=False
            ).count()
            
            if current_games > 0:
                self.stdout.write(f"   Status: In {current_games} active game(s)")
            else:
                self.stdout.write(f"   Status: Available")

    def show_overall_status(self):
        """Show overall bot and game status."""
        self.stdout.write("\n🎮 Poker Bot System Status")
        self.stdout.write("=" * 50)
        
        # Game counts
        total_games = Game.objects.count()
        active_games = Game.objects.filter(status__in=['WAITING', 'PLAYING']).count()
        bot_games = Game.objects.filter(
            status__in=['WAITING', 'PLAYING'],
            playergame__player__is_bot=True
        ).distinct().count()
        
        self.stdout.write(f"📊 Games: {total_games} total, {active_games} active, {bot_games} with bots")
        
        # Bot counts
        total_bots = BotPlayer.objects.count()
        active_bots = PlayerGame.objects.filter(
            player__is_bot=True,
            game__status__in=['WAITING', 'PLAYING'],
            cashed_out=False,
            left_table=False
        ).count()
        
        self.stdout.write(f"🤖 Bots: {total_bots} total, {active_bots} in active games")
        
        # Check for potential issues
        stuck_games = Game.objects.filter(
            status='PLAYING',
            current_player__is_bot=True
        ).count()
        
        if stuck_games > 0:
            self.stdout.write(self.style.WARNING(f"⚠️  {stuck_games} games waiting for bot actions"))
            self.stdout.write("   Run with --list-stuck to see details")
            self.stdout.write("   Run with --fix-stuck to attempt fixes")
        else:
            self.stdout.write("✅ No games appear stuck on bot turns")
        
        self.stdout.write(f"\n💡 Use --game-id <id> to debug specific games")
        self.stdout.write(f"💡 Use --bot-stats to see bot performance")