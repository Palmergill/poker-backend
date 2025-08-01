# test_redis.py - Script to test Redis connection

import redis
import sys

def test_redis_connection():
    """Test if Redis is running and accessible."""
    try:
        # Try to connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Test the connection
        r.ping()
        print("✅ Redis is running and accessible!")
        
        # Test basic operations
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        
        if value == b'test_value':
            print("✅ Redis read/write operations work correctly!")
            r.delete('test_key')  # Clean up
            return True
        else:
            print("❌ Redis read/write operations failed!")
            return False
            
    except redis.ConnectionError:
        print("❌ Could not connect to Redis. Make sure Redis is running on localhost:6379")
        return False
    except Exception as e:
        print(f"❌ Error testing Redis: {e}")
        return False

def print_redis_instructions():
    """Print instructions for installing and starting Redis."""
    print("\n🔧 Redis Setup Instructions:")
    print("=" * 50)
    
    print("\nFor Windows:")
    print("1. Download Redis from: https://github.com/microsoftarchive/redis/releases")
    print("2. Extract and run redis-server.exe")
    print("3. Or use Windows Subsystem for Linux (WSL) and follow Linux instructions")
    
    print("\nFor macOS:")
    print("1. Install Homebrew if you haven't: https://brew.sh/")
    print("2. Run: brew install redis")
    print("3. Start Redis: brew services start redis")
    print("4. Or run temporarily: redis-server")
    
    print("\nFor Linux (Ubuntu/Debian):")
    print("1. Update packages: sudo apt update")
    print("2. Install Redis: sudo apt install redis-server")
    print("3. Start Redis service: sudo systemctl start redis-server")
    print("4. Enable auto-start: sudo systemctl enable redis-server")
    
    print("\nFor Docker:")
    print("1. Install Docker if you haven't")
    print("2. Run: docker run -d -p 6379:6379 --name redis redis:alpine")
    
    print("\nTo test if Redis is working:")
    print("1. Run this script again: python test_redis.py")
    print("2. Or use Redis CLI: redis-cli ping (should return PONG)")

if __name__ == "__main__":
    print("🔍 Testing Redis connection...")
    
    if test_redis_connection():
        print("\n🎉 Redis is ready for your Django Channels application!")
        sys.exit(0)
    else:
        print_redis_instructions()
        sys.exit(1)