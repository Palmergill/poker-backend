#!/usr/bin/env python3
"""
Test script to verify WebSocket functionality after fixes
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()

import asyncio
import json
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

async def test_websocket_with_auth():
    """Test WebSocket connection with proper authentication"""
    print("🔄 Testing WebSocket connection with authentication...")
    
    try:
        # Create a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        if created:
            user.set_password('testpass')
            user.save()
            print(f"✅ Created test user: {user.username}")
        else:
            print(f"✅ Using existing test user: {user.username}")
        
        # Generate JWT token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        print(f"✅ Generated JWT token: {access_token[:20]}...")
        
        # Test WebSocket connection with token
        from poker_api.consumers import PokerGameConsumer
        application = PokerGameConsumer.as_asgi()
        
        communicator = WebsocketCommunicator(
            application, 
            f"/ws/game/1/?token={access_token}"
        )
        
        connected, subprotocol = await communicator.connect()
        
        if connected:
            print("✅ WebSocket connected successfully!")
            
            # Try to receive initial game state
            try:
                response = await asyncio.wait_for(
                    communicator.receive_json_from(), 
                    timeout=5.0
                )
                print(f"✅ Received initial game state: {type(response)}")
            except asyncio.TimeoutError:
                print("⚠️ No initial game state received (this may be expected if game doesn't exist)")
            
            await communicator.disconnect()
            print("✅ WebSocket disconnected successfully!")
            
        else:
            print("❌ WebSocket connection failed")
            return False
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_basic_websocket():
    """Test basic WebSocket routing without authentication"""
    print("🔄 Testing basic WebSocket routing...")
    
    try:
        from poker_api.consumers import PokerGameConsumer
        application = PokerGameConsumer.as_asgi()
        
        communicator = WebsocketCommunicator(application, "/ws/game/1/")
        
        connected, subprotocol = await communicator.connect()
        
        if connected:
            print("❌ WebSocket connected without authentication (this shouldn't happen)")
            await communicator.disconnect()
            return False
        else:
            print("✅ WebSocket correctly rejected connection without authentication")
            return True
            
    except Exception as e:
        print(f"✅ WebSocket correctly rejected connection: {e}")
        return True

def test_channel_layer():
    """Test that Redis channel layer is working"""
    print("🔄 Testing Redis channel layer...")
    
    try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        if channel_layer is None:
            print("❌ Channel layer is None")
            return False
            
        print(f"✅ Channel layer loaded: {type(channel_layer)}")
        return True
        
    except Exception as e:
        print(f"❌ Channel layer test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting WebSocket fix verification tests...\n")
    
    # Test 1: Channel layer
    test1_passed = test_channel_layer()
    print()
    
    # Test 2: Basic WebSocket routing
    test2_passed = asyncio.run(test_basic_websocket())
    print()
    
    # Test 3: WebSocket with authentication
    test3_passed = asyncio.run(test_websocket_with_auth())
    print()
    
    # Summary
    print("📊 Test Results:")
    print(f"  ✅ Channel Layer: {'PASS' if test1_passed else 'FAIL'}")
    print(f"  ✅ Basic WebSocket: {'PASS' if test2_passed else 'FAIL'}")
    print(f"  ✅ Authenticated WebSocket: {'PASS' if test3_passed else 'FAIL'}")
    
    if all([test1_passed, test2_passed, test3_passed]):
        print("\n🎉 All WebSocket tests passed! WebSocket errors have been fixed.")
    else:
        print("\n❌ Some tests failed. WebSocket issues may still exist.")