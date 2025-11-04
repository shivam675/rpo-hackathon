let lastMessageCount = 0;
let isUserScrolled = false;

const messagesContainer = document.getElementById('messages');

// Detect if user has scrolled up
messagesContainer.addEventListener('scroll', function() {
    const isAtBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop <= messagesContainer.clientHeight + 50;
    isUserScrolled = !isAtBottom;
});

function loadPortfolio() {
    fetch('/api/portfolio')
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            const container = document.getElementById('portfolio-content');
            
            if (data.error) {
                console.error('Portfolio API error:', data.error);
                container.innerHTML = '<div class="empty-portfolio">Error loading portfolio: ' + data.error + '</div>';
                return;
            }
            
            let html = `
                <div class="balance-card">
                    <div class="balance-label">Total Portfolio Value</div>
                    <div class="balance-value">AED ${data.total_value.toLocaleString()}</div>
                </div>
                <div style="margin-bottom: 15px;">
                    <div style="color: rgba(255,255,255,0.7); font-size: 14px; margin-bottom: 10px;">
                        Cash: AED ${data.balance.toLocaleString()} | 
                        Stocks: AED ${data.portfolio_value.toLocaleString()}
                    </div>
                </div>
            `;
            
            if (data.holdings && data.holdings.length > 0) {
                html += '<div class="holdings-grid">';
                data.holdings.forEach(holding => {
                    html += `
                        <div class="holding-card">
                            <div class="holding-header">
                                <div class="stock-symbol">${holding.symbol}</div>
                                <div class="stock-price">AED ${holding.price.toFixed(2)}</div>
                            </div>
                            <div class="stock-name">${holding.name}</div>
                            <div class="holding-details">
                                <div class="quantity">${holding.quantity} shares</div>
                                <div class="total-value">AED ${holding.total_value.toLocaleString()}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html += '<div class="empty-portfolio">No holdings yet. Start trading!</div>';
            }
            
            container.innerHTML = html;
        })
        .catch(err => {
            console.error('Error loading portfolio:', err);
            document.getElementById('portfolio-content').innerHTML = `<div class="empty-portfolio">Connection error: ${err.message}</div>`;
        });
}

function loadLogs() {
    fetch('/api/logs')
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            const container = document.getElementById('logs-content');
            
            // Only show real-time actions from HTTP POST calls
            const realTimeActions = data.logs || [];
            
            if (realTimeActions.length === 0) {
                container.innerHTML = '<div class="empty-logs">No real-time activity yet...<br><small>Waiting for Actor AI to send actions via HTTP POST</small></div>';
                return;
            }
            
            // Sort by timestamp (newest first)
            realTimeActions.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            
            const html = realTimeActions.map(log => {
                const statusClass = log.status === 'error' ? 'log-error' : log.status === 'success' ? 'log-success' : '';
                
                return `
                    <div class="log-entry ${statusClass}">
                        <div class="log-timestamp">
                            ${new Date(log.timestamp).toLocaleString()} <span class="realtime-indicator">🔴 LIVE</span>
                        </div>
                        <div class="log-message">"${escapeHtml(log.message)}"</div>
                        <div class="log-action">${log.tool}(${JSON.stringify(log.args)})</div>
                        <div class="log-result">→ ${escapeHtml(log.result)}</div>
                    </div>
                `;
            }).join('');
            
            container.innerHTML = html;
            
            // Auto-scroll to bottom
            container.scrollTop = container.scrollHeight;
        })
        .catch(err => {
            console.error('Error loading logs:', err);
            document.getElementById('logs-content').innerHTML = `<div class="empty-logs">Connection error: ${err.message}</div>`;
        });
}

function loadMessages() {
    fetch('/api/messages')
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
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
                        .catch(err => {
                    console.error('Error loading messages:', err);
                    document.getElementById('messages').innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div>Connection error: ${err.message}</div></div>`;
                });
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
    
    if (!password) {
        alert('Please enter the password');
        return;
    }
    
    console.log('Attempting to reset chat with password...');
    
    fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password })
    })
    .then(res => {
        console.log('Reset response status:', res.status);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        console.log('Reset response data:', data);
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
        alert(`Error resetting chat: ${err.message}`);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners
document.getElementById('message').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendMessage();
});

document.getElementById('resetPassword').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') confirmReset();
});

// Modal close on outside click
document.getElementById('resetModal').addEventListener('click', function(e) {
    if (e.target === this) {
        hideResetModal();
    }
});

// Initialize and start real-time updates
function startPolling() {
    // Load initial data
    loadMessages();
    loadPortfolio();
    loadLogs();
    
    // Set up polling intervals
    setInterval(loadMessages, 500);      // Messages update frequently
    setInterval(loadPortfolio, 2000);    // Portfolio updates every 2 seconds
    setInterval(loadLogs, 500);          // Logs update every 500ms for real-time display
}

startPolling();

document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
        loadMessages();
        loadPortfolio();
        loadLogs();
    }
});