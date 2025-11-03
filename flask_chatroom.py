from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import json
import os

app = Flask(__name__)

# File to store chat history
CHAT_FILE = 'chat_history.json'
RESET_PASSWORD = '1234'

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

# HTML template for the chat interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Chat Room</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #0f0f1e;
            background-image: 
                radial-gradient(at 0% 0%, rgba(102, 126, 234, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(118, 75, 162, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(102, 126, 234, 0.15) 0px, transparent 50%),
                radial-gradient(at 0% 100%, rgba(118, 75, 162, 0.15) 0px, transparent 50%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        .container {
            width: 95%;
            max-width: 900px;
            height: 90vh;
            background: rgba(26, 26, 46, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
            padding: 24px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .header-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .header-title {
            font-size: 20px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }
        .header-subtitle {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
            margin-top: 2px;
        }
        .reset-btn {
            background: rgba(231, 76, 60, 0.2);
            border: 1px solid rgba(231, 76, 60, 0.4);
            color: #ff6b6b;
            padding: 10px 18px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .reset-btn:hover {
            background: rgba(231, 76, 60, 0.3);
            border-color: rgba(231, 76, 60, 0.6);
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(231, 76, 60, 0.3);
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            background: rgba(15, 15, 30, 0.5);
        }
        .messages::-webkit-scrollbar {
            width: 8px;
        }
        .messages::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
        }
        .messages::-webkit-scrollbar-thumb {
            background: rgba(102, 126, 234, 0.3);
            border-radius: 4px;
        }
        .messages::-webkit-scrollbar-thumb:hover {
            background: rgba(102, 126, 234, 0.5);
        }
        .message {
            background: rgba(26, 26, 46, 0.8);
            backdrop-filter: blur(10px);
            padding: 16px 20px;
            margin-bottom: 14px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            transition: all 0.3s ease;
        }
        .message:hover {
            background: rgba(26, 26, 46, 0.95);
            border-color: rgba(102, 126, 234, 0.3);
            transform: translateX(4px);
        }
        @keyframes slideIn {
            from { 
                opacity: 0; 
                transform: translateY(20px) scale(0.95); 
            }
            to { 
                opacity: 1; 
                transform: translateY(0) scale(1); 
            }
        }
        .message-user {
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 6px;
            font-size: 14px;
        }
        .message-text {
            color: rgba(255, 255, 255, 0.9);
            word-wrap: break-word;
            line-height: 1.5;
            font-size: 15px;
        }
        .message-time {
            font-size: 11px;
            color: rgba(255, 255, 255, 0.4);
            margin-top: 8px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .input-area {
            padding: 24px;
            background: rgba(26, 26, 46, 0.8);
            backdrop-filter: blur(10px);
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        .input-row {
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
        }
        input {
            padding: 14px 18px;
            background: rgba(15, 15, 30, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            font-size: 14px;
            color: white;
            transition: all 0.3s ease;
        }
        input::placeholder {
            color: rgba(255, 255, 255, 0.4);
        }
        input:focus {
            outline: none;
            border-color: #667eea;
            background: rgba(15, 15, 30, 0.95);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        #username {
            flex: 1;
        }
        #message {
            flex: 1;
        }
        button {
            padding: 14px 28px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
        }
        button:active {
            transform: translateY(0);
        }
        .empty-state {
            text-align: center;
            color: rgba(255, 255, 255, 0.4);
            padding: 60px 20px;
            font-size: 15px;
        }
        .empty-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.3;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            justify-content: center;
            align-items: center;
            z-index: 1000;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: rgba(26, 26, 46, 0.95);
            backdrop-filter: blur(20px);
            padding: 32px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
            max-width: 420px;
            width: 90%;
            animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        @keyframes slideUp {
            from { 
                opacity: 0;
                transform: translateY(30px) scale(0.95); 
            }
            to { 
                opacity: 1;
                transform: translateY(0) scale(1); 
            }
        }
        .modal-title {
            font-size: 22px;
            font-weight: 600;
            margin-bottom: 24px;
            color: white;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .modal-input {
            width: 100%;
            padding: 14px 18px;
            background: rgba(15, 15, 30, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            font-size: 14px;
            color: white;
            margin-bottom: 24px;
            transition: all 0.3s ease;
        }
        .modal-input:focus {
            outline: none;
            border-color: #e74c3c;
            background: rgba(15, 15, 30, 0.95);
            box-shadow: 0 0 0 3px rgba(231, 76, 60, 0.1);
        }
        .modal-input::placeholder {
            color: rgba(255, 255, 255, 0.4);
        }
        .modal-buttons {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }
        .modal-btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .modal-btn-cancel {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .modal-btn-cancel:hover {
            background: rgba(255, 255, 255, 0.15);
            color: white;
        }
        .modal-btn-confirm {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.4);
        }
        .modal-btn-confirm:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(231, 76, 60, 0.5);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <div class="header-icon">💬</div>
                <div>
                    <div class="header-title">Hyperstitious Bot</div>
                    <div class="header-subtitle">Real-time collaboration</div>
                </div>
            </div>
            <button class="reset-btn" onclick="showResetModal()">
                <span>🗑️</span>
                <span>Reset</span>
            </button>
        </div>
        <div class="messages" id="messages">
            <div class="empty-state">
                <div class="empty-icon">💭</div>
                <div>No messages yet. Start the conversation!</div>
            </div>
        </div>
        <div class="input-area">
            <div class="input-row">
                <input type="text" id="username" placeholder="Enter your name" />
            </div>
            <div class="input-row">
                <input type="text" id="message" placeholder="Type your message..." />
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>

    <!-- Reset Modal -->
    <div class="modal" id="resetModal">
        <div class="modal-content">
            <div class="modal-title">⚠️ Reset Chat History</div>
            <input type="password" class="modal-input" id="resetPassword" placeholder="Enter password" />
            <div class="modal-buttons">
                <button class="modal-btn modal-btn-cancel" onclick="hideResetModal()">Cancel</button>
                <button class="modal-btn modal-btn-confirm" onclick="confirmReset()">Reset</button>
            </div>
        </div>
    </div>

    <script>
        let lastMessageCount = 0;
        let isUserScrolled = false;

        const messagesContainer = document.getElementById('messages');

        // Detect if user has scrolled up
        messagesContainer.addEventListener('scroll', function() {
            const isAtBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop <= messagesContainer.clientHeight + 50;
            isUserScrolled = !isAtBottom;
        });

        function loadMessages() {
            fetch('/api/messages')
                .then(res => res.json())
                .then(data => {
                    const container = document.getElementById('messages');
                    
                    if (data.messages.length === 0) {
                        container.innerHTML = '<div class="empty-state"><div class="empty-icon">💭</div><div>No messages yet. Start the conversation!</div></div>';
                        lastMessageCount = 0;
                        return;
                    }

                    // Only update if there are new messages
                    if (data.messages.length !== lastMessageCount) {
                        const wasAtBottom = !isUserScrolled;
                        
                        container.innerHTML = data.messages.map(msg => `
                            <div class="message">
                                <div class="message-user">${escapeHtml(msg.user)}</div>
                                <div class="message-text">${escapeHtml(msg.text)}</div>
                                <div class="message-time">${msg.timestamp}</div>
                            </div>
                        `).join('');
                        
                        lastMessageCount = data.messages.length;
                        
                        // Auto-scroll only if user was at bottom
                        if (wasAtBottom) {
                            container.scrollTop = container.scrollHeight;
                        }
                    }
                })
                .catch(err => console.error('Error loading messages:', err));
        }

        function sendMessage() {
            const username = document.getElementById('username').value.trim();
            const message = document.getElementById('message').value.trim();
            
            if (!username || !message) {
                alert('Please enter both name and message');
                return;
            }

            fetch('/api/messages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user: username, text: message })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('message').value = '';
                    isUserScrolled = false;
                    loadMessages();
                }
            })
            .catch(err => console.error('Error sending message:', err));
        }

        function showResetModal() {
            document.getElementById('resetModal').classList.add('active');
            document.getElementById('resetPassword').value = '';
            document.getElementById('resetPassword').focus();
        }

        function hideResetModal() {
            document.getElementById('resetModal').classList.remove('active');
        }

        function confirmReset() {
            const password = document.getElementById('resetPassword').value;
            
            fetch('/api/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    hideResetModal();
                    loadMessages();
                    alert('Chat history cleared successfully!');
                } else {
                    alert(data.error || 'Incorrect password');
                }
            })
            .catch(err => {
                console.error('Error resetting chat:', err);
                alert('Error resetting chat');
            });
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        document.getElementById('message').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });

        document.getElementById('resetPassword').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') confirmReset();
        });

        // Use long polling for real-time updates
        function startLongPolling() {
            loadMessages();
            setInterval(loadMessages, 500);
        }

        startLongPolling();

        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                loadMessages();
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Render the chat interface"""
    return render_template_string(HTML_TEMPLATE)

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
    app.run(debug=True, host='0.0.0.0', port=7070)
