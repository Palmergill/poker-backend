# poker_api/consumers.py (Updated)
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.serializers.json import DjangoJSONEncoder
from .models import Game, PlayerGame
import logging

# Get logger for WebSocket consumer
logger = logging.getLogger(__name__)

class PokerGameConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time poker game updates."""
    async def connect(self):
        """Handle WebSocket connection with authentication and permission checks."""
        try:
            self.game_id = self.scope['url_route']['kwargs']['game_id']
            self.game_group_name = f'game_{self.game_id}'
            
            # Get user from scope (set by our custom middleware)
            user = self.scope.get('user')
            user_str = user.username if hasattr(user, 'username') else str(user)
            
            logger.info(f"WebSocket connection attempt for game {self.game_id} from user: {user_str}")
            logger.debug(f"Connection details - Game group: {self.game_group_name}, Channel: {self.channel_name}")
            
            # Check if user is authenticated
            if isinstance(user, AnonymousUser) or not user.is_authenticated:
                logger.warning(f"Rejected unauthenticated WebSocket connection for game {self.game_id}")
                await self.close(code=4001)  # Custom close code for authentication failure
                return
            
            # Check if user can join this game
            can_join = await self.can_join_game(user)
            if can_join == "GAME_NOT_FOUND":
                logger.warning(f"User {user.username} denied access - game {self.game_id} does not exist")
                await self.close(code=4004)  # Custom close code for game not found
                return
            elif not can_join:
                logger.warning(f"User {user.username} denied access to game {self.game_id} - not a player")
                await self.close(code=4003)  # Custom close code for permission denied
                return
            
            logger.debug(f"User {user.username} authorized to join game {self.game_id}")
            
            # Join game group
            await self.channel_layer.group_add(
                self.game_group_name,
                self.channel_name
            )
            logger.debug(f"Added user {user.username} to group {self.game_group_name}")
            
            await self.accept()
            logger.info(f"WebSocket connection established: {user.username} -> game {self.game_id}")
            
            # Send current game state to the new consumer
            try:
                logger.debug(f"Fetching initial game state for {user.username}")
                game_state = await self.get_game_state()
                await self.send(text_data=json.dumps(game_state, cls=DjangoJSONEncoder))
                logger.debug(f"Initial game state sent to {user.username}")
            except Exception as e:
                logger.error(f"Failed to send initial game state to {user.username}: {str(e)}")
                
        except Exception as e:
            logger.error(f"WebSocket connection failed for game {self.game_id}: {str(e)}")
            await self.close(code=1011)  # Internal server error
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection and cleanup."""
        user = self.scope.get('user')
        user_str = user.username if hasattr(user, 'username') else 'Anonymous'
        
        logger.info(f"WebSocket disconnecting: {user_str} from game {getattr(self, 'game_id', 'unknown')} (code: {close_code})")
        
        # Leave game group
        if hasattr(self, 'game_group_name'):
            await self.channel_layer.group_discard(
                self.game_group_name,
                self.channel_name
            )
            logger.debug(f"Removed {user_str} from group {self.game_group_name}")
        
        logger.info(f"WebSocket disconnection complete for {user_str}")
    
    async def receive(self, text_data):
        """Receive message from WebSocket client (currently not used for game actions)."""
        # This consumer doesn't handle incoming messages from clients
        # Game actions are handled by the REST API
        user = self.scope.get('user')
        user_str = user.username if hasattr(user, 'username') else 'Anonymous'
        
        logger.debug(f"Received WebSocket message from {user_str}: {text_data}")
        logger.info(f"WebSocket message ignored - game actions should use REST API")
    
    async def game_update(self, event):
        """Receive and forward game update messages from the game group."""
        user = self.scope.get('user')
        user_str = user.username if hasattr(user, 'username') else 'Anonymous'
        game_data = event.get('data', {})
        
        # Log game update details
        game_status = game_data.get('status', 'unknown')
        game_phase = game_data.get('phase', 'unknown')
        logger.debug(f"Forwarding game update to {user_str}: status={game_status}, phase={game_phase}")
        
        # Check if this is a hand completion update
        if game_data.get('winner_info'):
            winner_info = game_data['winner_info']
            if winner_info.get('winners'):
                winner_names = [w.get('player_name', 'Unknown') for w in winner_info['winners']]
                if len(winner_names) == 1:
                    logger.info(f"Sending hand completion to {user_str} - Winner: {winner_names[0]}")
                else:
                    logger.info(f"Sending hand completion to {user_str} - Winners: {', '.join(winner_names)}")
        
        # Send message to WebSocket
        try:
            await self.send(text_data=json.dumps(event['data'], cls=DjangoJSONEncoder))
            logger.debug(f"Game update sent successfully to {user_str}")
        except Exception as e:
            logger.error(f"Failed to send game update to {user_str}: {str(e)}")

    async def game_summary_notification(self, event):
        """Receive and forward game summary notification messages from the game group."""
        user = self.scope.get('user')
        user_str = user.username if hasattr(user, 'username') else 'Anonymous'
        summary_data = event.get('data', {})
        
        # Log game summary notification details
        game_id = summary_data.get('game_id', 'unknown')
        total_hands = summary_data.get('total_hands', 0)
        player_count = len(summary_data.get('game_summary', {}).get('players', []))
        
        logger.info(f"Forwarding game summary notification to {user_str}: game={game_id}, hands={total_hands}, players={player_count}")
        
        # Send message to WebSocket
        try:
            await self.send(text_data=json.dumps(summary_data, cls=DjangoJSONEncoder))
            logger.info(f"Game summary notification sent successfully to {user_str}")
        except Exception as e:
            logger.error(f"Failed to send game summary notification to {user_str}: {str(e)}")
    
    @database_sync_to_async
    def can_join_game(self, user):
        """Check if user is authorized to join this poker game."""
        try:
            logger.debug(f"Checking if {user.username} can join game {self.game_id}")
            game = Game.objects.get(id=self.game_id)
            
            # Check if user is part of the game
            is_player = PlayerGame.objects.filter(game=game, player__user=user).exists()
            logger.debug(f"User {user.username} player status for game {self.game_id}: {is_player}")
            
            return is_player
        except Game.DoesNotExist:
            logger.error(f"Authorization check failed - Game {self.game_id} does not exist")
            # Return a special value to indicate game not found
            return "GAME_NOT_FOUND"
        except Exception as e:
            logger.error(f"Authorization check failed for {user.username} in game {self.game_id}: {str(e)}")
            return False
    
    @database_sync_to_async
    def get_game_state(self):
        """Get current game state for the user connecting to WebSocket."""
        from .serializers import GameSerializer
        from rest_framework.request import Request
        from django.http import HttpRequest
        
        try:
            user = self.scope['user']
            logger.debug(f"Fetching game state for {user.username} in game {self.game_id}")
            
            # Create a mock request with the user
            http_request = HttpRequest()
            http_request.user = user
            request = Request(http_request)
            
            game = Game.objects.get(id=self.game_id)
            serializer = GameSerializer(game, context={'request': request})
            
            game_data = serializer.data
            player_count = len(game_data.get('players', []))
            logger.debug(f"Game state retrieved for {user.username}: status={game_data.get('status')}, players={player_count}")
            
            return game_data
        except Game.DoesNotExist:
            logger.error(f"Cannot get game state - Game {self.game_id} does not exist")
            return {"error": "Game not found"}
        except Exception as e:
            logger.error(f"Failed to get game state for {self.scope['user'].username}: {str(e)}")
            return {"error": "Failed to get game state"}