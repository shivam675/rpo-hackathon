#!/usr/bin/env python3
"""
Test script to verify the actor -> Flask communication works
"""

import requests
import json
from datetime import datetime
import time

FLASK_URL = "http://127.0.0.1:7070"

def test_flask_connection():
    """Test if Flask server is running"""
    print("=== Testing Flask Server Connection ===")
    
    try:
        response = requests.get(f"{FLASK_URL}/api/messages", timeout=5)
        if response.status_code == 200:
            print("✅ Flask server is running and responsive")
            return True
        else:
            print(f"❌ Flask server responded with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Flask server: {e}")
        return False

def test_actor_action_endpoint():
    """Test sending an actor action to Flask"""
    print("\n=== Testing Actor Action Endpoint ===")
    
    # Test data similar to what actor.py would send
    test_action = {
        "timestamp": datetime.now().isoformat(),
        "message": "Test message: buy 10 AAPL stocks",
        "tool": "buy_stock",
        "args": {"symbol": "AAPL", "quantity": 10},
        "result": '{"status": "bought", "symbol": "AAPL", "quantity": 10, "price": 150.0, "cost": 1500.0, "new_balance": 8500.0}',
        "status": "success"
    }
    
    try:
        response = requests.post(
            f"{FLASK_URL}/api/actor_action",
            json=test_action,
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ Actor action sent successfully")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Failed to send actor action. Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending actor action: {e}")
        return False

def test_logs_retrieval():
    """Test retrieving logs from Flask"""
    print("\n=== Testing Logs Retrieval ===")
    
    try:
        response = requests.get(f"{FLASK_URL}/api/logs", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ Logs retrieved successfully")
            print(f"   Real-time actions count: {len(data.get('logs', []))}")
            
            # Show recent actions
            if data.get('logs'):
                print("   Recent real-time actions:")
                for i, action in enumerate(data['logs'][-3:]):
                    print(f"     {i+1}. {action.get('tool', 'Unknown')} - {action.get('message', 'No message')[:50]}...")
            else:
                print("   No real-time actions yet")
            
            return True
        else:
            print(f"❌ Failed to retrieve logs. Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error retrieving logs: {e}")
        return False

def send_multiple_test_actions():
    """Send multiple test actions to simulate real actor activity"""
    print("\n=== Sending Multiple Test Actions ===")
    
    test_actions = [
        {
            "message": "buy 5 tesla shares",
            "tool": "buy_stock", 
            "args": {"symbol": "TSLA", "quantity": 5},
            "result": '{"status": "bought", "symbol": "TSLA", "quantity": 5, "price": 920.0, "cost": 4600.0}',
            "status": "success"
        },
        {
            "message": "check portfolio status",
            "tool": "list_portfolio",
            "args": {},
            "result": '{"balance": 5400.0, "portfolio": [["TSLA", 5], ["AAPL", 10]]}',
            "status": "success"
        },
        {
            "message": "sell 2 apple stocks",
            "tool": "sell_stock",
            "args": {"symbol": "AAPL", "quantity": 2},
            "result": '{"status": "sold", "symbol": "AAPL", "quantity": 2, "price": 150.0, "revenue": 300.0}',
            "status": "success"
        }
    ]
    
    for i, action in enumerate(test_actions):
        print(f"   Sending action {i+1}/3: {action['tool']}")
        
        # Add timestamp
        action["timestamp"] = datetime.now().isoformat()
        
        try:
            response = requests.post(
                f"{FLASK_URL}/api/actor_action",
                json=action,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"   ✅ Action {i+1} sent successfully")
            else:
                print(f"   ❌ Action {i+1} failed. Status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error sending action {i+1}: {e}")
        
        # Small delay between actions
        time.sleep(0.5)
    
    print("✅ Finished sending test actions")

if __name__ == "__main__":
    print("🧪 Testing Actor -> Flask Communication\n")
    
    # Run tests
    if test_flask_connection():
        if test_actor_action_endpoint():
            time.sleep(0.5)  # Brief pause
            test_logs_retrieval()
            
            print("\n" + "="*50)
            print("🚀 Sending realistic test data...")
            send_multiple_test_actions()
            
            print("\n" + "="*50)
            print("📊 Final logs check:")
            test_logs_retrieval()
    
    print(f"\n🏁 Test complete!")
    print(f"💡 Now open http://127.0.0.1:7070 in your browser to see the real-time logs!")