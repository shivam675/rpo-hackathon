#!/usr/bin/env python3
"""
Test script to verify Flask server components are working correctly
"""

import os
import json
import sqlite3
from flask_chatroom import get_portfolio_data, get_actor_logs, TRADING_DB, ACTOR_LOG

def test_files_exist():
    """Test if required files exist"""
    print("=== File Existence Test ===")
    
    files_to_check = [
        'templates/index.html',
        'static/css/style.css', 
        'static/js/dashboard.js',
        TRADING_DB,
        ACTOR_LOG
    ]
    
    for file_path in files_to_check:
        exists = os.path.exists(file_path)
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"{status}: {file_path}")
    
    print()

def test_portfolio_data():
    """Test portfolio data retrieval"""
    print("=== Portfolio Data Test ===")
    
    try:
        data = get_portfolio_data()
        print(f"Portfolio data: {json.dumps(data, indent=2)}")
        
        if 'error' in data:
            print(f"❌ Portfolio error: {data['error']}")
        else:
            print("✅ Portfolio data retrieved successfully")
    except Exception as e:
        print(f"❌ Portfolio test failed: {e}")
    
    print()

def test_actor_logs():
    """Test actor logs retrieval"""
    print("=== Actor Logs Test ===")
    
    try:
        logs = get_actor_logs()
        print(f"Number of logs: {len(logs)}")
        
        if logs:
            print("Recent logs:")
            for i, log in enumerate(logs[-3:]):  # Show last 3 logs
                print(f"  {i+1}. {log.get('timestamp', 'No timestamp')}: {log.get('tool', 'No tool')} - {log.get('message', 'No message')[:50]}...")
            print("✅ Actor logs retrieved successfully")
        else:
            print("⚠️ No logs found")
    except Exception as e:
        print(f"❌ Actor logs test failed: {e}")
    
    print()

def test_database_structure():
    """Test trading database structure"""
    print("=== Database Structure Test ===")
    
    if not os.path.exists(TRADING_DB):
        print(f"❌ Trading database not found: {TRADING_DB}")
        return
    
    try:
        conn = sqlite3.connect(TRADING_DB)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Database tables: {[table[0] for table in tables]}")
        
        # Check wallet
        cursor.execute("SELECT * FROM wallet")
        wallet = cursor.fetchall()
        print(f"Wallet data: {wallet}")
        
        # Check portfolio
        cursor.execute("SELECT * FROM portfolio")
        portfolio = cursor.fetchall()
        print(f"Portfolio data: {portfolio}")
        
        # Check stocks
        cursor.execute("SELECT * FROM stocks")
        stocks = cursor.fetchall()
        print(f"Available stocks: {len(stocks)} stocks")
        
        conn.close()
        print("✅ Database structure looks good")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
    
    print()

if __name__ == "__main__":
    print("🧪 Testing Flask Server Components\n")
    
    test_files_exist()
    test_database_structure() 
    test_portfolio_data()
    test_actor_logs()
    
    print("🏁 Test complete!")