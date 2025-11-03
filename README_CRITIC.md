# Trading Agent with Critic AI System

## Overview

This system implements a **dual-AI trading system** with an Actor and a Critic:

- **Actor AI** (`actor.py`): Monitors chatroom messages and executes trades based on user intent
- **Critic AI** (`critic.py`): Monitors the Actor's actions and flags anomalies

## Architecture

```
Chatroom Server
      ↓
   Actor AI ──→ MCP Server (executes trades)
      ↓           ↑
  Action Log     │
      ↓           │
   Critic AI ─────┘
      ↓
  Chatroom (posts warnings)
```

## How It Works

### Actor AI
1. Monitors chatroom messages in real-time
2. Uses LLM (Ollama) to interpret trading intent (even from casual/joking language)
3. Executes trades via MCP server
4. Logs all actions to `actor_actions.json`

### Critic AI
1. Monitors `actor_actions.json` for new trading actions
2. Analyzes if actions match the original message context
3. Detects anomalies like:
   - Selling stocks based on casual jokes
   - Buying excessive quantities for casual mentions
   - Actions contradicting message sentiment
4. Posts warnings to chatroom when anomalies detected
5. Waits for user confirmation to reverse the action

## Setup

### 1. Start the MCP Server
```bash
python mcp_server.py --server_type sse
```

### 2. Configure IP addresses
Edit `ip.yaml`:
```yaml
chat_server_url: http://YOUR_CHAT_IP:6060/api/messages
post_chat_url: http://YOUR_CHAT_IP:6060/api/chat
mcp_server_url: http://YOUR_MCP_IP:8000/sse
```

### 3. Start Actor AI
```bash
python actor.py
```

### 4. Start Critic AI (in separate terminal)
```bash
python critic.py
```

## Usage Examples

### Normal Trading (No Alert)
**User in chatroom:** "Buy 10 TSLA shares"
- ✅ Actor executes buy
- ✅ Critic: No anomaly detected

### Anomaly Detection
**User in chatroom:** "Lol just went bankrupt at Starbucks 😂"
- ⚠️ Actor interprets as stock crash → sells portfolio
- 🚨 Critic detects anomaly: "Casual joke triggered major sell-off"
- 📢 Posts warning to chatroom
- 🔄 User can respond with ❌ to reverse the trade

### Responding to Warnings
When Critic posts a warning:
- **Confirm trade was correct:** Reply with "👍" or "intentional"
- **Reverse the trade:** Reply with "❌" or "reverse"

## Critic Detection Rules

### Flags as Anomaly:
- Casual language + serious trade action
- Jokes/memes triggering real trades
- Excessive quantities for casual mentions
- Mismatched stock symbols
- Contradicting sentiment

### Allows as Normal:
- Explicit trading commands
- Clear trading intent
- Portfolio monitoring actions
- Small test trades

## Files

- `actor.py` - Main trading agent
- `critic.py` - Oversight/anomaly detection
- `mcp_server.py` - Trading backend
- `SYSTEM_PROMPT.py` - LLM prompts
- `actor_actions.json` - Action log (auto-generated)
- `trading.db` - Trading database (auto-generated)

## Advanced Features

### Custom System Prompts
Edit `SYSTEM_PROMPT.py` to customize:
- Trading detection patterns
- Anomaly severity levels
- Rectification strategies

### Action Logging
All actor actions are logged with:
- Timestamp
- Original message
- Tool called
- Arguments
- Result

### Automatic Rectification
Critic can generate reverse commands:
- Buy → Sell to undo
- Sell → Buy back to restore

## Safety Features

- ✅ Dual-AI oversight
- ✅ Human-in-the-loop for critical actions
- ✅ Action logging and audit trail
- ✅ Timeout on pending confirmations
- ✅ Severity-based alerting

## Monitoring

Both Actor and Critic print real-time logs:
```
💬 Message from User: "text"
🧰 Executing: buy_stock with {'symbol': 'TSLA', 'quantity': 10}
✅ Result: {...}
👁️ New action detected: buy_stock
🚨 ANOMALY DETECTED (high): Casual joke triggered sale
```

## Tips

1. Keep both actor.py and critic.py running simultaneously
2. Monitor both terminal outputs
3. Critic has a 30-second timeout for user responses
4. Action log keeps last 50 actions only
5. Test with small quantities first!
