from flask import Flask, request, jsonify, render_template
from datetime import datetime
import json
import os
import sqlite3

app = Flask(__name__)

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

# File to store chat history
CHAT_FILE = 'chat_history.json'
RESET_PASSWORD = '1234'
TRADING_DB = 'trading.db'
ACTOR_LOG = 'actor_actions.json'

# Load messages from file if it exists
def load_messages():
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

# Save messages to file
def save_messages():
    with open(CHAT_FILE, 'w') as f:
        json.dump(messages, f, indent=2)

# Initialize messages from file
messages = load_messages()

# In-memory storage for real-time actor actions
actor_actions = []

# Trading data functions
def get_portfolio_data():
    """Get portfolio data from trading.db"""
    try:
        # Check if database file exists
        if not os.path.exists(TRADING_DB):
            return {'error': f'Trading database not found at {TRADING_DB}', 'balance': 0, 'portfolio_value': 0, 'total_value': 0, 'holdings': []}
        
        conn = sqlite3.connect(TRADING_DB)
        cursor = conn.cursor()
        
        # Get portfolio
        cursor.execute("SELECT symbol, quantity FROM portfolio")
        portfolio = cursor.fetchall()
        
        # Get wallet balance
        cursor.execute("SELECT balance FROM wallet WHERE id=1")
        balance_row = cursor.fetchone()
        balance = balance_row[0] if balance_row else 0
        
        # Get stock prices
        cursor.execute("SELECT symbol, name, price FROM stocks")
        stocks = dict((row[0], {'name': row[1], 'price': row[2]}) for row in cursor.fetchall())
        
        conn.close()
        
        # Calculate portfolio value
        portfolio_value = 0
        portfolio_details = []
        for symbol, quantity in portfolio:
            if symbol in stocks:
                current_price = stocks[symbol]['price']
                total_value = quantity * current_price
                portfolio_value += total_value
                portfolio_details.append({
                    'symbol': symbol,
                    'name': stocks[symbol]['name'],
                    'quantity': quantity,
                    'price': current_price,
                    'total_value': total_value
                })
        
        return {
            'balance': balance,
            'portfolio_value': portfolio_value,
            'total_value': balance + portfolio_value,
            'holdings': portfolio_details
        }
    except Exception as e:
        return {'error': str(e), 'balance': 0, 'portfolio_value': 0, 'total_value': 0, 'holdings': []}

# File-based log reading removed - now only using real-time HTTP POST actions

# Routes
@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template('index.html')

# All HTML, CSS, and JS are now in separate files

# Duplicate route removed - using template-based routing above

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """API endpoint to retrieve all messages"""
    return jsonify({
        'success': True,
        'messages': messages,
        'count': len(messages)
    })

@app.route('/api/messages', methods=['POST'])
def post_message():
    """API endpoint to post a new message"""
    data = request.get_json()
    
    if not data or 'user' not in data or 'text' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing user or text field'
        }), 400
    
    message = {
        'user': data['user'],
        'text': data['text'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    messages.append(message)
    save_messages()  # Save to file after each message
    
    return jsonify({
        'success': True,
        'message': message
    }), 201

@app.route('/api/portfolio')
def get_portfolio():
    """API endpoint to get trading portfolio data"""
    portfolio_data = get_portfolio_data()
    return jsonify(portfolio_data)

@app.route('/api/logs')
def get_logs():
    """API endpoint to get real-time actor AI actions"""
    # Return only real-time actions from HTTP POST calls
    return jsonify({
        'logs': actor_actions[-20:]  # Last 20 real-time actions only
    })

@app.route('/api/actor_action', methods=['POST'])
def receive_actor_action():
    """API endpoint to receive real-time actor actions"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Add timestamp if not provided
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Add to in-memory storage
        actor_actions.append(data)
        
        # Keep only last 100 actions in memory
        if len(actor_actions) > 100:
            actor_actions[:] = actor_actions[-100:]
        
        print(f"📨 Received actor action: {data['tool']} - {data['message'][:50]}...")
        
        return jsonify({
            'success': True,
            'message': 'Action received successfully'
        }), 200
        
    except Exception as e:
        print(f"❌ Error receiving actor action: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500





@app.route('/api/reset', methods=['POST'])
def reset_chat():
    """API endpoint to reset chat history with password protection"""
    data = request.get_json()
    
    if not data or 'password' not in data:
        return jsonify({
            'success': False,
            'error': 'Password required'
        }), 400
    
    if data['password'] != RESET_PASSWORD:
        print(f"Password mismatch: received '{data['password']}', expected '{RESET_PASSWORD}'")
        return jsonify({
            'success': False,
            'error': 'Incorrect password'
        }), 403
    
    global messages
    messages = []
    save_messages()  # Save empty messages to file
    
    return jsonify({
        'success': True,
        'message': 'Chat history cleared'
    })

if __name__ == '__main__':
    print(f"Loaded {len(messages)} messages from history")
    print(f"Trading DB path: {TRADING_DB}")
    print(f"Actor log path: {ACTOR_LOG}")
    print(f"Trading DB exists: {os.path.exists(TRADING_DB)}")
    print(f"Actor log exists: {os.path.exists(ACTOR_LOG)}")
    print("Starting Flask server on http://0.0.0.0:7070")
    app.run(debug=True, host='0.0.0.0', port=7070)
