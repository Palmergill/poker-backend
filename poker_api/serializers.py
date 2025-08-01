# poker_api/serializers.py
from rest_framework import serializers
from .models import PokerTable, Player, Game, PlayerGame, GameAction, HandHistory, BotPlayer
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_superuser', 'is_staff']

class PlayerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    bot_config = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = ['id', 'user', 'is_bot', 'bot_config']
    
    def get_bot_config(self, obj):
        """Get bot configuration if this is a bot player"""
        if obj.is_bot:
            try:
                bot_player = BotPlayer.objects.get(player=obj)
                return BotPlayerSerializer(bot_player).data
            except BotPlayer.DoesNotExist:
                return None
        return None

class BotPlayerSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.user.username', read_only=True)

    class Meta:
        model = BotPlayer
        fields = ['id', 'player_name', 'difficulty', 'play_style', 'aggression_factor', 
                 'bluff_frequency', 'thinking_time_min', 'thinking_time_max']

class PokerTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = PokerTable
        fields = ['id', 'name', 'max_players', 'small_blind', 'big_blind', 'min_buy_in', 'max_buy_in', 'created_at']
        
    def validate(self, data):
        """
        Validate table creation data
        """
        if 'big_blind' in data and 'small_blind' in data:
            if data['big_blind'] < data['small_blind']:
                raise serializers.ValidationError({'big_blind': 'Big blind must be greater than or equal to small blind'})
        
        if 'min_buy_in' in data and 'big_blind' in data:
            if data['min_buy_in'] < data['big_blind'] * 10:
                raise serializers.ValidationError({'min_buy_in': 'Minimum buy-in should be at least 10 times the big blind'})
        
        if 'max_buy_in' in data and 'min_buy_in' in data:
            if data['max_buy_in'] < data['min_buy_in']:
                raise serializers.ValidationError({'max_buy_in': 'Maximum buy-in must be greater than or equal to minimum buy-in'})
        
        return data

class PlayerGameSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    cards = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField()
    win_loss = serializers.SerializerMethodField()
    
    class Meta:
        model = PlayerGame
        fields = ['id', 'player', 'seat_position', 'stack', 'starting_stack', 'final_stack', 'is_active', 'cashed_out', 'left_table', 'left_at', 'cards', 'current_bet', 'total_bet', 'ready_for_next_hand', 'status', 'win_loss']
    
    def get_cards(self, obj):
        # Always send cards data and let frontend handle visibility
        # This ensures consistency between API and WebSocket updates
        return {
            'cards': obj.get_cards(),
            'owner_id': obj.player.user.id,
            'owner_username': obj.player.user.username
        }
    
    def get_win_loss(self, obj):
        return obj.calculate_win_loss()

class GameActionSerializer(serializers.ModelSerializer):
    player = serializers.SerializerMethodField()
    
    class Meta:
        model = GameAction
        fields = ['id', 'player', 'action_type', 'amount', 'timestamp']
    
    def get_player(self, obj):
        try:
            return obj.player_game.player.user.username
        except (AttributeError, ValueError) as e:
            # Handle case where player_game relationship is broken
            return "Unknown Player"

class GameSerializer(serializers.ModelSerializer):
    table = PokerTableSerializer(read_only=True)
    current_player = PlayerSerializer(read_only=True)
    players = serializers.SerializerMethodField()
    community_cards = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    winner_info = serializers.SerializerMethodField()
    game_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Game
        fields = ['id', 'table', 'status', 'phase', 'pot', 'current_bet', 'dealer_position', 
                  'current_player', 'community_cards', 'players', 'actions', 'created_at', 'winner_info', 'game_summary']
    
    def get_community_cards(self, obj):
        return obj.get_community_cards()
    
    def get_players(self, obj):
        # Only include players who haven't left the table for UI display
        player_games = PlayerGame.objects.filter(game=obj, left_table=False).order_by('seat_position')
        serializer = PlayerGameSerializer(player_games, many=True, context=self.context)
        return serializer.data
    
    def get_actions(self, obj):
        try:
            # Get last 10 actions
            actions = GameAction.objects.filter(
                player_game__game=obj
            ).order_by('-timestamp')[:10]
            serializer = GameActionSerializer(actions, many=True)
            return serializer.data
        except Exception as e:
            # Log the error and return empty list instead of crashing
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing actions for game {obj.id}: {e}")
            return []
    
    def get_winner_info(self, obj):
        return obj.get_winner_info()
    
    def get_game_summary(self, obj):
        return obj.get_game_summary()

class GameActionRequestSerializer(serializers.Serializer):
    action_type = serializers.ChoiceField(choices=['FOLD', 'CHECK', 'CALL', 'BET', 'RAISE'])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)

class HandHistorySerializer(serializers.ModelSerializer):
    winner_info = serializers.SerializerMethodField()
    player_cards = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    community_cards = serializers.SerializerMethodField()
    
    class Meta:
        model = HandHistory
        fields = ['id', 'hand_number', 'pot_amount', 'final_phase', 'completed_at', 
                 'winner_info', 'player_cards', 'actions', 'community_cards']
    
    def get_winner_info(self, obj):
        return obj.get_winner_info()
    
    def get_player_cards(self, obj):
        return obj.get_player_cards()
    
    def get_actions(self, obj):
        return obj.get_actions()
    
    def get_community_cards(self, obj):
        return obj.get_community_cards()