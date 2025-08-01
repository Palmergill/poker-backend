# poker_api/views.py
import time
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from .models import PokerTable, Player, Game, PlayerGame, HandHistory, BotPlayer
from .serializers import (
    PokerTableSerializer, PlayerSerializer, GameSerializer, PlayerGameSerializer,
    GameActionRequestSerializer, HandHistorySerializer
)
from .services.game_service import GameService
from django.contrib.auth.models import User
from django.db import transaction
from decimal import Decimal, InvalidOperation
import logging

# Get logger for API views
logger = logging.getLogger(__name__)

class PokerTableViewSet(viewsets.ModelViewSet):
    queryset = PokerTable.objects.all()
    serializer_class = PokerTableSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def join_table(self, request, pk=None):
        """Join a table with a specified buy-in amount"""
        table = self.get_object()
        player, created = Player.objects.get_or_create(user=request.user)
        
        # Get buy-in amount from request and convert to Decimal
        try:
            buy_in_raw = request.data.get('buy_in', table.min_buy_in)
            buy_in = Decimal(str(buy_in_raw))
        except (ValueError, TypeError, InvalidOperation):
            return Response(
                {'error': 'Invalid buy-in amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate buy-in amount
        if buy_in < table.min_buy_in:
            return Response(
                {'error': f'Buy-in must be at least {table.min_buy_in}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if buy_in > table.max_buy_in:
            return Response(
                {'error': f'Buy-in cannot exceed {table.max_buy_in}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buy-in validation only checks table limits, not player balance
        # Players can buy in for any amount within table limits
        
        # Find active game at this table or create a new one
        game = Game.objects.filter(table=table, status='WAITING').first()
        if not game:
            game = Game.objects.create(table=table, status='WAITING')
        
        # Check if player is already at the table
        if PlayerGame.objects.filter(game=game, player=player).exists():
            return Response(
                {'error': 'You are already at this table'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if table is full
        if PlayerGame.objects.filter(game=game).count() >= table.max_players:
            return Response(
                {'error': 'Table is full'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find an empty seat
        occupied_seats = PlayerGame.objects.filter(game=game).values_list('seat_position', flat=True)
        for seat in range(table.max_players):
            if seat not in occupied_seats:
                # Join the table
                PlayerGame.objects.create(
                    player=player,
                    game=game,
                    seat_position=seat,
                    stack=buy_in,
                    starting_stack=buy_in,  # Record initial stack for win/loss tracking
                    is_active=True
                )
                
                serializer = GameSerializer(game, context={'request': request})
                return Response(serializer.data)
        
        return Response(
            {'error': 'No available seats'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['delete'])
    def delete_all(self, request):
        """Delete all poker tables (admin only)"""
        # Check if user is admin
        if not (request.user.is_superuser or request.user.is_staff):
            return Response(
                {'error': 'Admin privileges required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get count before deletion
        table_count = PokerTable.objects.count()
        
        # Delete all tables (this will cascade delete related games and player games)
        PokerTable.objects.all().delete()
        
        return Response({
            'message': f'Successfully deleted {table_count} tables',
            'deleted_count': table_count
        })

class GameViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter games to include only those the player is part of"""
        player, created = Player.objects.get_or_create(user=self.request.user)
        return Game.objects.filter(playergame__player=player).distinct()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to add error handling"""
        try:
            return super().retrieve(request, *args, **kwargs)
        except KeyError as e:
            logger.error(f"KeyError in game serialization for user {request.user.username}: {e}")
            return Response(
                {'error': f'Game serialization error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error in game retrieve for user {request.user.username}: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start the game"""
        game = self.get_object()
        
        try:
            GameService.start_game(game.id)
            GameService.broadcast_game_update(game.id)
            serializer = self.get_serializer(game)
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='action')
    def perform_action(self, request, pk=None):
        """Take an action in the game"""
        game = self.get_object()
        player, created = Player.objects.get_or_create(user=request.user)
        
        # Validate action
        serializer = GameActionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"❌ Invalid action data from {request.user.username}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        action_type = serializer.validated_data['action_type']
        amount = serializer.validated_data.get('amount', 0)
        
        # Log the action attempt
        amount_str = f" ${amount}" if amount > 0 else ""
        logger.info(f"🎮 Game {game.id}: {request.user.username} attempting {action_type}{amount_str}")
        
        try:
            # Process the action
            updated_game = GameService.process_action(game.id, player.id, action_type, amount)
            logger.info(f"✅ Action processed successfully - Game status: {updated_game.status}, Phase: {updated_game.phase}")
            
            # Broadcast the update to all connected clients
            GameService.broadcast_game_update(game.id)
            logger.debug(f"📡 Game update broadcast for game {game.id}")
            
            # Return updated game state
            game_serializer = self.get_serializer(updated_game)
            return Response(game_serializer.data)
        except ValueError as e:
            logger.error(f"❌ Action failed for {request.user.username}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reset_game_state(self, request, pk=None):
        """Reset corrupted game state (debug utility)"""
        game = self.get_object()
        
        if game.status != 'PLAYING':
            return Response({'error': 'Game is not in progress'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get all active players (excluding cashed out players)
            active_players = list(PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).order_by('seat_position'))
            
            if len(active_players) < 2:
                return Response({'error': 'Not enough active players'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset current player to first active player
            game.current_player = active_players[0].player
            
            # If no current bet, reset to first player after dealer
            if game.current_bet == 0:
                dealer_pos = game.dealer_position
                # Find first active player after dealer
                for i in range(1, len(active_players) + 1):
                    next_pos = (dealer_pos + i) % len(active_players)
                    if next_pos < len(active_players):
                        game.current_player = active_players[next_pos].player
                        break
            
            game.save()
            
            # Broadcast update
            GameService.broadcast_game_update(game.id)
            
            serializer = self.get_serializer(game)
            return Response({
                'message': 'Game state reset successfully',
                'game': serializer.data
            })
            
        except Exception as e:
            return Response({'error': f'Failed to reset game state: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get game summary if available"""
        from .models import GameSummary
        
        try:
            # First try to get the game if it still exists
            game = self.get_object()
            
            # Check if user participated in this game
            if not PlayerGame.objects.filter(game=game, player__user=request.user).exists():
                return Response(
                    {'error': 'You did not participate in this game'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            summary_data = game.get_game_summary()
            if summary_data:
                return Response({
                    'game_summary': summary_data,
                    'game_status': game.status
                })
                
        except (Game.DoesNotExist, Exception):
            # Game has been deleted or other error, try to get from persistent GameSummary
            pass
        
        # Look for persistent GameSummary
        try:
            game_summary = GameSummary.objects.get(
                game_id=pk,
                participants__in=[request.user]
            )
            summary_data = game_summary.get_summary_data()
            
            return Response({
                'game_summary': summary_data,
                'game_status': 'FINISHED'
            })
            
        except GameSummary.DoesNotExist:
            return Response(
                {'error': 'Game summary not available'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def debug_state(self, request, pk=None):
        """Get detailed game state for debugging"""
        game = self.get_object()
        
        active_players = list(PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False).order_by('seat_position'))
        all_players = list(PlayerGame.objects.filter(game=game).order_by('seat_position'))
        
        debug_info = {
            'game_id': game.id,
            'status': game.status,
            'phase': game.phase,
            'current_player_id': game.current_player_id,
            'current_player_name': game.current_player.user.username if game.current_player else None,
            'current_bet': str(game.current_bet),
            'pot': str(game.pot),
            'dealer_position': game.dealer_position,
            'active_players_count': len(active_players),
            'total_players_count': len(all_players),
            'active_players': [
                {
                    'id': pg.player.id,
                    'username': pg.player.user.username,
                    'seat_position': pg.seat_position,
                    'stack': str(pg.stack),
                    'current_bet': str(pg.current_bet),
                    'total_bet': str(pg.total_bet),
                    'is_active': pg.is_active
                }
                for pg in all_players
            ]
        }
        
        return Response(debug_info)
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave the table completely (only works if already cashed out)"""
        game = self.get_object()
        player, created = Player.objects.get_or_create(user=request.user)
        
        try:
            player_game = PlayerGame.objects.get(game=game, player=player)
            
            # Can only leave if already cashed out
            if not player_game.cashed_out:
                return Response(
                    {'error': 'You must cash out before leaving the table'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Record final stack if not already recorded (in case player leaves without cashing out first)
            if player_game.final_stack is None:
                player_game.final_stack = player_game.stack
                player_game.save()
            
            logger.info(f"💸 Player {request.user.username} left table with ${player_game.stack} from game {game.id}")
            
            # Mark player as left instead of deleting (preserve for game summary)
            from django.utils import timezone
            player_game.left_table = True
            player_game.left_at = timezone.now()
            player_game.is_active = False
            player_game.save()
            
            # Store player data for potential game summary
            all_players_before_delete = list(PlayerGame.objects.filter(game=game))
            
            # Broadcast update to remove player from UI
            GameService.broadcast_game_update(game.id)
            
            # Check if we need to end the game (only count players who haven't left)
            remaining_players = PlayerGame.objects.filter(game=game, left_table=False)
            active_players = remaining_players.filter(is_active=True, cashed_out=False)
            
            if remaining_players.count() == 0:
                # All players left - check if all had final_stack recorded
                players_with_final_stack = [pg for pg in all_players_before_delete if pg.final_stack is not None]
                if len(players_with_final_stack) == len(all_players_before_delete):
                    # Generate game summary before finishing
                    summary = game.generate_game_summary()
                    logger.info(f"📊 Game summary generated for completed game {game.id}")
                    # Broadcast game summary notification (even though no players are left, other systems might need it)
                    GameService.broadcast_game_summary_available(game.id, summary)
                    
                    # Automatically delete the table since the game is complete
                    table = game.table
                    table_name = table.name
                    table.delete()  # This will cascade delete the game and all related data
                    logger.info(f"🗑️ Table '{table_name}' automatically deleted after game completion")
                else:
                    # No players remaining - use centralized completion logic
                    GameService._complete_game(game, "No players remaining")
                logger.info(f"🏁 Game {game.id} ended - no players remaining")
            elif active_players.count() == 1:
                # Only one active player left, they win by default
                last_player = active_players.first()
                if last_player and game.pot > 0:
                    last_player.stack += game.pot
                    last_player.save()
                    game.pot = 0
                # Use centralized completion logic instead of just setting status
                GameService._complete_game(game, "Only one active player remaining")
                logger.info(f"🏁 Game {game.id} ended - only one active player remaining")
            
            return Response({
                'success': True, 
                'left_with': str(player_game.stack)
            })
            
        except PlayerGame.DoesNotExist:
            logger.warning(f"Player {request.user.username} tried to leave but is not at table")
            return Response(
                {'error': 'You are not at this table'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def ready(self, request, pk=None):
        """Mark player as ready for next hand"""
        game = self.get_object()
        player, created = Player.objects.get_or_create(user=request.user)
        
        try:
            player_game = PlayerGame.objects.get(game=game, player=player)
            
            # Can only mark ready if hand has ended (winner_info exists)
            if not game.get_winner_info():
                return Response(
                    {'error': 'Cannot mark ready - hand has not ended yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark player as ready
            player_game.ready_for_next_hand = True
            player_game.save()
            
            logger.info(f"🟢 Player {request.user.username} marked ready for next hand in game {game.id}")
            
            # Check if all eligible players are ready (excluding cashed out players)
            # Note: After a hand ends, only the winner might be marked as "active", 
            # but we need to check all players who haven't cashed out
            all_eligible_players = PlayerGame.objects.filter(game=game, cashed_out=False)
            ready_eligible_players = all_eligible_players.filter(ready_for_next_hand=True)
            
            logger.info(f"📊 Ready status: {ready_eligible_players.count()}/{all_eligible_players.count()} eligible players ready")
            
            # If all eligible players are ready, start next hand
            if all_eligible_players.count() > 1 and ready_eligible_players.count() == all_eligible_players.count():
                logger.info(f"🎯 All players ready! Starting next hand for game {game.id}")
                
                # Clear winner info first
                game.winner_info = None
                game.save()
                
                # Start the new hand properly
                GameService._start_new_hand(game)
                
                # Broadcast update to show new hand started
                GameService.broadcast_game_update(game.id)
            else:
                # Just broadcast readiness update
                GameService.broadcast_game_update(game.id)
            
            return Response({'success': True, 'ready_count': ready_eligible_players.count(), 'total_count': all_eligible_players.count()})
            
        except PlayerGame.DoesNotExist:
            logger.warning(f"Player {request.user.username} tried to ready but is not at table")
            return Response(
                {'error': 'You are not at this table'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cash_out(self, request, pk=None):
        """Cash out from active play (stay at table but become inactive)"""
        game = self.get_object()
        player, created = Player.objects.get_or_create(user=request.user)
        
        try:
            player_game = PlayerGame.objects.get(game=game, player=player)
            
            # Cannot cash out if already cashed out
            if player_game.cashed_out:
                return Response(
                    {'error': 'You have already cashed out'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Cannot cash out during an active betting round (but allow during WAITING_FOR_PLAYERS phase)
            if game.status == 'PLAYING' and player_game.is_active and game.phase not in ['WAITING_FOR_PLAYERS', 'FINISHED']:
                return Response(
                    {'error': 'Cannot cash out during an active hand. Wait for hand to end or fold first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark player as cashed out and inactive (but keep them at table)
            player_game.cashed_out = True
            player_game.is_active = False
            player_game.final_stack = player_game.stack  # Record final stack for win/loss tracking
            player_game.save()
            
            logger.info(f"💰 Player {request.user.username} cashed out (staying at table) with ${player_game.stack} from game {game.id}")
            
            # Check if we need to end the game (only active, non-cashed-out players count)
            active_players = PlayerGame.objects.filter(game=game, is_active=True, cashed_out=False)
            
            if active_players.count() == 1:
                # Only one active player left, they win by default
                last_player = active_players.first()
                if last_player and game.pot > 0:
                    last_player.stack += game.pot
                    last_player.save()
                    game.pot = 0
                # Use centralized completion instead of just setting status
                GameService._complete_game(game, "Only one active player remaining after cash out")
                logger.info(f"🏁 Game {game.id} ended - only one active player remaining")
                return Response({'success': True, 'stack': str(player_game.stack), 'game_ended': True})
            elif active_players.count() == 0:
                # Use centralized completion instead of just setting status
                GameService._complete_game(game, "No active players remaining after cash out")
                logger.info(f"🏁 Game {game.id} ended - no active players remaining")
                return Response({'success': True, 'stack': str(player_game.stack), 'game_ended': True})
            else:
                # Check if only bots remain (human cashed out, bots still at table)
                # Note: Check all non-cashed-out players, not just active ones
                # because bots may be inactive after folding but still need to be cashed out
                remaining_players = PlayerGame.objects.filter(game=game, cashed_out=False, left_table=False)
                human_players = remaining_players.filter(player__is_bot=False)
                bot_players = remaining_players.filter(player__is_bot=True)
                
                if human_players.count() == 0 and bot_players.count() > 0:
                    # Only bots remain - auto-cash them out and end the game
                    logger.info(f"🤖 Only {bot_players.count()} bots remain at table - auto-cashing out all bots")
                    GameService._auto_cash_out_all_bots(game)
            
            # Check if game summary should be generated (all players have cashed out)
            all_players = PlayerGame.objects.filter(game=game)
            players_with_final_stack = all_players.filter(final_stack__isnull=False)
            game_summary_generated = False
            
            if all_players.count() > 0 and players_with_final_stack.count() == all_players.count():
                # All players have cashed out, use centralized completion logic
                logger.info(f"📊 All players have cashed out - completing game {game.id}")
                summary = GameService._complete_game(game, "All players cashed out")
                game_summary_generated = True
                
                # Note: Table is now deleted, so we can't broadcast regular updates
            else:
                # Regular broadcast update to show player as cashed out
                GameService.broadcast_game_update(game.id)
            
            # Prepare response data
            response_data = {
                'success': True, 
                'message': 'Cashed out successfully. You can buy back in or leave the table.',
                'stack': str(player_game.stack),
                'game_summary_generated': game_summary_generated
            }
            
            # Include summary in response if it was generated
            if game_summary_generated:
                response_data['game_summary'] = summary
                response_data['message'] = 'Cashed out successfully. Game summary has been generated as all players have cashed out.'
            
            return Response(response_data)
            
        except PlayerGame.DoesNotExist:
            logger.warning(f"Player {request.user.username} tried to cash out but is not at table")
            return Response(
                {'error': 'You are not at this table'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def buy_back_in(self, request, pk=None):
        """Buy back into the game after cashing out"""
        game = self.get_object()
        player, created = Player.objects.get_or_create(user=request.user)
        
        try:
            player_game = PlayerGame.objects.get(game=game, player=player)
            
            # Can only buy back in if currently cashed out
            if not player_game.cashed_out:
                return Response(
                    {'error': 'You have not cashed out, so you cannot buy back in'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get buy-in amount from request and convert to Decimal
            try:
                buy_in_raw = request.data.get('amount')
                if buy_in_raw is None:
                    return Response(
                        {'error': 'Buy-in amount is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                buy_in = Decimal(str(buy_in_raw))
            except (ValueError, TypeError, InvalidOperation):
                return Response(
                    {'error': 'Invalid buy-in amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate buy-in amount against table limits
            table = game.table
            if buy_in < table.min_buy_in:
                return Response(
                    {'error': f'Buy-in must be at least ${table.min_buy_in}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if buy_in > table.max_buy_in:
                return Response(
                    {'error': f'Buy-in cannot exceed ${table.max_buy_in}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Buy-in validation only checks table limits, not player balance
            # Players can buy back in for any amount within table limits
            
            # Cannot buy back in during an active hand (except WAITING_FOR_PLAYERS)
            if game.status == 'PLAYING' and game.phase not in ['WAITING_FOR_PLAYERS', 'FINISHED']:
                return Response(
                    {'error': 'Cannot buy back in during an active hand. Wait for hand to end.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process the buy-back-in
            player_game.stack = buy_in  # Set stack to buy-in amount (not add to existing stack)
            player_game.cashed_out = False
            player_game.is_active = True
            # Update starting stack to reflect the new buy-in (total investment)
            if player_game.starting_stack is None:
                player_game.starting_stack = buy_in
            else:
                player_game.starting_stack += buy_in
            # Clear final stack since they're back in play
            player_game.final_stack = None
            player_game.save()
            
            logger.info(f"🔄 Player {request.user.username} bought back in with ${buy_in} to game {game.id} (total stack: ${player_game.stack})")
            
            # Broadcast update to show player as active again
            GameService.broadcast_game_update(game.id)
            
            return Response({
                'success': True,
                'buy_in_amount': str(buy_in),
                'total_stack': str(player_game.stack)
            })
            
        except PlayerGame.DoesNotExist:
            logger.warning(f"Player {request.user.username} tried to buy back in but is not at table")
            return Response(
                {'error': 'You are not at this table'},
                status=status.HTTP_400_BAD_REQUEST
            )

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter to show only the current user's player profile by default"""
        if self.request.query_params.get('all'):
            return Player.objects.all()
        return Player.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get the current user's player profile"""
        player, created = Player.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(player)
        return Response(serializer.data)
    
    # Deposit and withdraw methods removed - balance is no longer tracked
    
    @action(detail=False, methods=['get'])
    def match_history(self, request):
        """Get the current user's match history including ongoing games"""
        from .models import GameSummary
        from django.utils import timezone
        
        # Get current player
        player, created = Player.objects.get_or_create(user=request.user)
        
        history_data = []
        
        # First, add ongoing games (games where user is participating but not completed)
        active_player_games = PlayerGame.objects.filter(
            player=player,
            game__status__in=['WAITING', 'PLAYING']
        ).select_related('game', 'game__table')
        
        for pg in active_player_games:
            game = pg.game
            current_stack = pg.stack if not pg.left_table else pg.final_stack or pg.stack
            win_loss = current_stack - (pg.starting_stack or 0)
            
            history_item = {
                'game_id': game.id,
                'table_name': game.table.name,
                'completed_at': None,  # Not completed yet
                'status': 'ONGOING',
                'total_hands': game.hand_count or 0,
                'total_players': PlayerGame.objects.filter(game=game, left_table=False).count(),
                'user_result': {
                    'starting_stack': float(pg.starting_stack) if pg.starting_stack else 0,
                    'final_stack': float(current_stack),
                    'win_loss': float(win_loss),
                    'status': pg.status
                }
            }
            history_data.append(history_item)
        
        # Then, add completed games from GameSummary
        game_summaries = GameSummary.objects.filter(
            participants=request.user
        ).order_by('-created_at')
        
        for gs in game_summaries:
            summary_data = gs.get_summary_data()
            if summary_data:
                # Find current user's data in the summary
                user_data = None
                for player_data in summary_data.get('players', []):
                    if player_data.get('player_name') == request.user.username:
                        user_data = player_data
                        break
                
                history_item = {
                    'game_id': gs.game_id,
                    'table_name': gs.table_name,
                    'completed_at': summary_data.get('completed_at'),
                    'status': 'COMPLETED',
                    'total_hands': summary_data.get('total_hands', 0),
                    'total_players': len(summary_data.get('players', [])),
                    'user_result': {
                        'starting_stack': user_data.get('starting_stack', 0) if user_data else 0,
                        'final_stack': user_data.get('final_stack', 0) if user_data else 0,
                        'win_loss': user_data.get('win_loss', 0) if user_data else 0,
                        'status': user_data.get('status', 'Unknown') if user_data else 'Unknown'
                    }
                }
                history_data.append(history_item)
        
        # Sort by date (ongoing games first, then most recent completed)
        history_data.sort(key=lambda x: (x['status'] != 'ONGOING', x['completed_at'] or timezone.now()), reverse=True)
        
        return Response({
            'match_history': history_data,
            'total_games': len(history_data)
        })

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user"""
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    
    # Validate required fields
    if not username or not email or not password:
        return Response(
            {'error': 'Please provide username, email, and password'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if username already exists
    if User.objects.filter(username=username).exists():
        return Response(
            {'username': ['This username is already taken']},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if email already exists
    if User.objects.filter(email=email).exists():
        return Response(
            {'email': ['This email is already registered']},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create user and player profile
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Create player profile
            from .models import Player
            Player.objects.create(user=user)
        
        return Response(
            {'message': 'User registered successfully'},
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def game_hand_history(request, game_id):
    """Get hand history for a specific game."""
    logger.info(f"📡 Hand history requested for game {game_id} by user {request.user.username}")
    
    game = get_object_or_404(Game, id=game_id)
    
    # Check if user is participating in the game
    if not PlayerGame.objects.filter(game=game, player__user=request.user).exists():
        logger.warning(f"❌ User {request.user.username} not authorized for game {game_id}")
        return Response(
            {'error': 'You are not a participant in this game'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    hand_histories = HandHistory.objects.filter(game=game).order_by('-hand_number')
    logger.info(f"📊 Found {hand_histories.count()} hand histories for game {game_id}")
    
    serializer = HandHistorySerializer(hand_histories, many=True)
    
    # Log details about each hand
    for hand in hand_histories[:3]:  # Log first 3 hands
        winner_info = hand.get_winner_info()
        if winner_info and 'winners' in winner_info:
            winner_name = winner_info['winners'][0]['player_name']
            winning_amount = winner_info['winners'][0]['winning_amount']
            logger.info(f"   Hand #{hand.hand_number}: Winner: {winner_name}, Amount: ${winning_amount}")
    
    logger.info(f"✅ Returning hand history response for game {game_id}")
    return Response({
        'game_id': game_id,
        'hand_history': serializer.data
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def simple_health_check(request):
    """Simple health check endpoint for Railway deployment healthcheck"""
    return Response({
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'poker_api'
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for monitoring"""
    import time
    from django.db import connections
    from django.core.cache import cache
    from django.conf import settings
    
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '1.0.0',
        'checks': {}
    }
    
    # Database health check
    try:
        db_conn = connections['default']
        db_conn.cursor()
        health_status['checks']['database'] = 'healthy'
    except Exception as e:
        health_status['checks']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Redis health check (for channels)
    try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            health_status['checks']['redis'] = 'healthy'
        else:
            health_status['checks']['redis'] = 'not configured'
    except Exception as e:
        health_status['checks']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Cache health check
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            health_status['checks']['cache'] = 'healthy'
        else:
            health_status['checks']['cache'] = 'unhealthy'
    except Exception as e:
        health_status['checks']['cache'] = f'unhealthy: {str(e)}'
    
    # Return appropriate HTTP status
    if health_status['status'] == 'healthy':
        return Response(health_status, status=status.HTTP_200_OK)
    else:
        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)

# Bot Management API Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_bot_to_table(request, table_id):
    """Add a bot player to a specific table"""
    try:
        table = get_object_or_404(PokerTable, id=table_id)
        
        # Get parameters from request
        buy_in_raw = request.data.get('buy_in', table.min_buy_in)
        difficulty = request.data.get('difficulty', 'BASIC')
        play_style = request.data.get('play_style', 'TIGHT_AGGRESSIVE')
        
        # Validate buy-in amount
        try:
            buy_in = Decimal(str(buy_in_raw))
        except (ValueError, TypeError, InvalidOperation):
            return Response(
                {'error': 'Invalid buy-in amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate buy-in range
        if buy_in < table.min_buy_in or buy_in > table.max_buy_in:
            return Response(
                {'error': f'Buy-in must be between {table.min_buy_in} and {table.max_buy_in}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate difficulty and play style
        valid_difficulties = ['BASIC', 'INTERMEDIATE', 'ADVANCED']
        valid_play_styles = ['TIGHT_PASSIVE', 'TIGHT_AGGRESSIVE', 'LOOSE_PASSIVE', 'LOOSE_AGGRESSIVE']
        
        if difficulty not in valid_difficulties:
            return Response(
                {'error': f'Invalid difficulty. Must be one of: {valid_difficulties}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if play_style not in valid_play_styles:
            return Response(
                {'error': f'Invalid play style. Must be one of: {valid_play_styles}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add bot to table
        bot_player = GameService.add_bot_to_table(table, buy_in, difficulty, play_style)
        
        return Response({
            'success': True,
            'bot_id': bot_player.id,
            'bot_name': bot_player.player.user.username,
            'difficulty': bot_player.difficulty,
            'play_style': bot_player.play_style,
            'buy_in': float(buy_in)
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error adding bot to table {table_id}: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_bot_from_table(request, table_id, bot_id):
    """Remove a bot player from a table"""
    try:
        table = get_object_or_404(PokerTable, id=table_id)
        bot_player = get_object_or_404(BotPlayer, id=bot_id)
        
        # Find active game at this table
        game = Game.objects.filter(table=table, status__in=['WAITING', 'PLAYING']).first()
        if not game:
            return Response(
                {'error': 'No active game at this table'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove bot from game
        GameService.remove_bot_from_game(game, bot_player)
        
        return Response({
            'success': True,
            'message': f'Bot {bot_player.player.user.username} removed from table'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error removing bot {bot_id} from table {table_id}: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_available_bots(request):
    """List all available bot players not currently in games"""
    try:
        available_bots = GameService.get_available_bots()
        
        bot_data = []
        for bot in available_bots:
            stats = GameService.get_bot_game_stats(bot)
            bot_data.append({
                'id': bot.id,
                'name': bot.player.user.username,
                'difficulty': bot.difficulty,
                'play_style': bot.play_style,
                'aggression_factor': bot.aggression_factor,
                'bluff_frequency': bot.bluff_frequency,
                'stats': stats
            })
        
        return Response({
            'bots': bot_data,
            'count': len(bot_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing available bots: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bot(request):
    """Create a new bot player"""
    try:
        difficulty = request.data.get('difficulty', 'BASIC')
        play_style = request.data.get('play_style', 'TIGHT_AGGRESSIVE')
        aggression_factor = request.data.get('aggression_factor', 0.5)
        bluff_frequency = request.data.get('bluff_frequency', 0.1)
        
        # Validate parameters
        valid_difficulties = ['BASIC', 'INTERMEDIATE', 'ADVANCED']
        valid_play_styles = ['TIGHT_PASSIVE', 'TIGHT_AGGRESSIVE', 'LOOSE_PASSIVE', 'LOOSE_AGGRESSIVE']
        
        if difficulty not in valid_difficulties:
            return Response(
                {'error': f'Invalid difficulty. Must be one of: {valid_difficulties}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if play_style not in valid_play_styles:
            return Response(
                {'error': f'Invalid play style. Must be one of: {valid_play_styles}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            aggression_factor = float(aggression_factor)
            bluff_frequency = float(bluff_frequency)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Aggression factor and bluff frequency must be numbers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not (0.0 <= aggression_factor <= 1.0) or not (0.0 <= bluff_frequency <= 1.0):
            return Response(
                {'error': 'Aggression factor and bluff frequency must be between 0.0 and 1.0'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create bot
        bot_player = GameService.create_bot_player(
            difficulty=difficulty,
            play_style=play_style,
            aggression_factor=aggression_factor,
            bluff_frequency=bluff_frequency
        )
        
        return Response({
            'success': True,
            'bot_id': bot_player.id,
            'bot_name': bot_player.player.user.username,
            'difficulty': bot_player.difficulty,
            'play_style': bot_player.play_style,
            'aggression_factor': bot_player.aggression_factor,
            'bluff_frequency': bot_player.bluff_frequency
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating bot: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_bot(request, bot_id):
    """Delete a bot player permanently"""
    try:
        bot_player = get_object_or_404(BotPlayer, id=bot_id)
        bot_name = bot_player.player.user.username
        
        # Delete the bot
        GameService.delete_bot_player(bot_player)
        
        return Response({
            'success': True,
            'message': f'Bot {bot_name} deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error deleting bot {bot_id}: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bot_stats(request, bot_id):
    """Get statistics for a specific bot"""
    try:
        bot_player = get_object_or_404(BotPlayer, id=bot_id)
        stats = GameService.get_bot_game_stats(bot_player)
        
        return Response({
            'bot_id': bot_player.id,
            'bot_name': bot_player.player.user.username,
            'difficulty': bot_player.difficulty,
            'play_style': bot_player.play_style,
            'stats': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting bot stats for {bot_id}: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """Readiness check endpoint for deployment"""
    import time
    try:
        # Check if we can run a simple database query
        from .models import PokerTable
        PokerTable.objects.count()
        
        return Response({
            'status': 'ready',
            'timestamp': time.time()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'status': 'not ready',
            'error': str(e),
            'timestamp': time.time()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)