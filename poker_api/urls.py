# poker_api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PokerTableViewSet, PlayerViewSet, GameViewSet
from .views import register_user, game_hand_history, health_check, readiness_check, simple_health_check
from .views import (
    add_bot_to_table, remove_bot_from_table, list_available_bots, 
    create_bot, delete_bot, bot_stats
)

router = DefaultRouter()
router.register(r'tables', PokerTableViewSet)
router.register(r'players', PlayerViewSet)
router.register(r'games', GameViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/', register_user, name='register_user'),
    path('games/<int:game_id>/hand-history/', game_hand_history, name='game_hand_history'),
    path('health/', simple_health_check, name='simple_health_check'),
    path('health/full/', health_check, name='health_check'),
    path('ready/', readiness_check, name='readiness_check'),
    
    # Bot management endpoints
    path('tables/<int:table_id>/add-bot/', add_bot_to_table, name='add_bot_to_table'),
    path('tables/<int:table_id>/remove-bot/<int:bot_id>/', remove_bot_from_table, name='remove_bot_from_table'),
    path('bots/', list_available_bots, name='list_available_bots'),
    path('bots/create/', create_bot, name='create_bot'),
    path('bots/<int:bot_id>/', delete_bot, name='delete_bot'),
    path('bots/<int:bot_id>/stats/', bot_stats, name='bot_stats'),
]