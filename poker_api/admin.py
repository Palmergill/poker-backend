# poker_api/admin.py
from django.contrib import admin
from .models import PokerTable, Player, Game, PlayerGame, GameAction, BotPlayer

@admin.register(PokerTable)
class PokerTableAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_players', 'small_blind', 'big_blind', 'min_buy_in', 'max_buy_in', 'created_at')
    search_fields = ('name',)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_bot')
    list_filter = ('is_bot',)
    search_fields = ('user__username',)

class PlayerGameInline(admin.TabularInline):
    model = PlayerGame
    extra = 0

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'status', 'phase', 'pot', 'created_at')
    list_filter = ('status', 'phase', 'table')
    search_fields = ('table__name',)
    inlines = [PlayerGameInline]

@admin.register(GameAction)
class GameActionAdmin(admin.ModelAdmin):
    list_display = ('player_game', 'action_type', 'amount', 'timestamp')
    list_filter = ('action_type',)
    search_fields = ('player_game__player__user__username',)

@admin.register(BotPlayer)
class BotPlayerAdmin(admin.ModelAdmin):
    list_display = ('player', 'difficulty', 'play_style', 'aggression_factor', 'bluff_frequency')
    list_filter = ('difficulty', 'play_style')
    search_fields = ('player__user__username',)
    
    def get_queryset(self, request):
        """Only show bot players"""
        qs = super().get_queryset(request)
        return qs.filter(player__is_bot=True)