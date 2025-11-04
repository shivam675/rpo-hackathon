import json
import asyncio
import ollama
from llama_index.tools.mcp import BasicMCPClient
import requests
import yaml
from datetime import datetime

# load ips from yaml
with open("ip.yaml", 'r') as f:
    ips = yaml.safe_load(f)

# ---------------------- MCP CLIENT ----------------------
mcp_server_url = ips.get("mcp_server_url", "http://127.0.0.1:8000/sse")
chat_server_url = ips.get("chat_server_url", "http://127.0.0.1:6060/api/messages")
post_chat_url = ips.get("post_chat_url", "http://127.0.0.1:6060/api/messages")
mcp_client = BasicMCPClient(mcp_server_url)

# Monitor actor's action log
ACTION_LOG_FILE = "actor_actions.json"

CRITIC_SYSTEM_PROMPT = """
You are a hyper-vigilant and skeptical trading oversight AI. Your primary mission is to prevent erroneous trades by scrutinizing every action the trading actor takes. Assume any ambiguity is a potential risk. Be extremely cautious.

Your job:
1. Analyze the user's message and the full conversation context.
2. Scrutinize the action taken by the trading actor.
3. Decide if the action is a potential anomaly.

IGNORE these messages (they are system commands and not user intent):
- Messages starting with @ACTOR_AI or @
- Messages from 🛡️ GUARDIAN_AI

FLAG AS ANOMALY IF:
- **High Severity**: A casual, sarcastic, or joking message triggers a real trade (e.g., "lol I'm going bankrupt" → `sell_stock`).
- **High Severity**: The action directly contradicts the user's stated sentiment (e.g., user says "I'm scared of the market" → `buy_stock`).
- **Medium Severity**: The trade quantity is large (e.g., > 20) and was inferred from vague language like "some" or "a lot", not a specific number.
- **Medium Severity**: The user seems to be asking a question, not giving a command, but a trade was made (e.g., "what do you think about tesla?" → `buy_stock`).
- **Low Severity**: A stock symbol was mapped, which might confuse the user (e.g., user said "samsung" and actor actioned "MSFT"). This is technically correct but worth confirming.
- **Low Severity**: The action seems disproportionate to a very casual comment (e.g., "nvidia is cool" → `buy_stock`).

SAFE (Don't flag):
- Clear, unambiguous trading commands: "buy 10 TSLA", "sell 40 AAPL".
- The actor used `list_stocks` or `list_portfolio`, as these are non-destructive read-only actions.
- The message is a direct system command to the actor (e.g., starts with @ACTOR_AI).

CRITICAL: Return ONLY valid JSON. NO explanations or extra text.

Response format (STRICTLY follow):
If anomaly:
{
  "is_anomaly": true,
  "severity": "low"|"medium"|"high",
  "reason": "A concise, one-line explanation of the potential issue.",
  "recommendation": "Suggest a clear action, like 'Reverse the trade' or 'Confirm with user'."
}

If safe:
{"is_anomaly": false}

Examples:
Message: "buy 40 samsung stocks"
Action: buy_stock MSFT quantity 40
→ {"is_anomaly": true, "severity": "low", "reason": "Stock symbol was mapped (samsung→MSFT), which could be confusing.", "recommendation": "Confirm user wanted to buy MSFT."}

Message: "lol im so broke"
Action: sell_stock TSLA quantity 100
→ {"is_anomaly": true, "severity": "high", "reason": "A casual joke about being broke triggered a large, real trade.", "recommendation": "Reverse the sale immediately."}

Message: "I guess I'll buy a lot of apple"
Action: buy_stock AAPL quantity 40
→ {"is_anomaly": true, "severity": "medium", "reason": "A large quantity (40) was inferred from vague term 'a lot'.", "recommendation": "Confirm the quantity with the user before proceeding."}

Message: "tesla to the moon"
Action: buy_stock TSLA quantity 10
→ {"is_anomaly": false}

ONLY return JSON. NO explanations.
"""

class CriticMonitor:
    def __init__(self):
        self.chat_history = []
        self.last_message_count = 0
        self.last_action_count = 0
        self.pending_confirmation = None
        
    def get_actor_actions(self):
        """Read actor's action log."""
        import os
        if os.path.exists(ACTION_LOG_FILE):
            try:
                with open(ACTION_LOG_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
        
    async def get_latest_chat(self):
        """Fetch latest chat messages."""
        try:
            response = requests.get(chat_server_url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": f"Failed to fetch chat: {e}"}
    
    def post_warning_to_chat(self, warning_message: str, user: str = "CRITIC_AI"):
        """Post a warning message to the chatroom."""
        try:
            payload = {
                "user": user,
                "text": warning_message
            }
            response = requests.post(post_chat_url, json=payload)
            response.raise_for_status()
            print(f"🚨 Posted warning to chatroom: {warning_message}")
            return True
        except requests.RequestException as e:
            print(f"❌ Failed to post to chat: {e}")
            return False
    
    async def get_portfolio(self):
        """Get current portfolio from MCP server."""
        try:
            result = await mcp_client.call_tool("list_portfolio", {})
            if hasattr(result, 'content') and result.content:
                text = ''.join([item.text for item in result.content if hasattr(item, 'text')])
                return json.loads(text)
            return None
        except Exception as e:
            print(f"❌ Failed to get portfolio: {e}")
            return None
    
    def analyze_action(self, message: str, action: dict, conversation_context: list):
        """Use LLM to analyze if an action is anomalous."""
        
        # Skip if message is from Guardian AI or Actor AI (system commands)
        if message.startswith("@ACTOR_AI") or "🛡️ GUARDIAN_AI" in message or message.startswith("@"):
            return {"is_anomaly": False}
        
        # Build context for critic
        context = f"""
        Recent conversation:
        {json.dumps(conversation_context[-5:], indent=2)}
        
        Latest message: "{message}"
        
        Action taken by trading actor:
        {json.dumps(action, indent=2)}
        
        Analyze if this action is appropriate or anomalous.
        Return ONLY JSON, no explanation.
        """
        
        response = ollama.chat(
            # model="qwen2.5:7b",
            model="falcon3:10b",
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            format="json"  # Force JSON output
        )
        
        try:
            content = response["message"]["content"].strip()
            
            # Extract only the first complete JSON object
            if "{" in content:
                start = content.find("{")
                # Find matching closing brace
                brace_count = 0
                end = start
                for i, char in enumerate(content[start:], start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                
                content = content[start:end]
            
            analysis = json.loads(content)
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Critic returned invalid JSON")
            print(f"   Raw: {content[:200]}")
            return {"is_anomaly": False}
    
    def generate_rectification_command(self, action: dict, recommendation: str):
        """Generate a command to reverse an anomalous action."""
        if "buy_stock" in str(action):
            # Reverse buy → sell
            symbol = action.get("args", {}).get("symbol")
            quantity = action.get("args", {}).get("quantity")
            return f"@ACTOR_AI sell {quantity} {symbol} shares immediately - false positive trade"
        
        elif "sell_stock" in str(action):
            # Reverse sell → buy back
            symbol = action.get("args", {}).get("symbol")
            quantity = action.get("args", {}).get("quantity")
            return f"@ACTOR_AI buy back {quantity} {symbol} shares - accidental sale"
        
        return recommendation
    
    async def handle_anomaly(self, analysis: dict, action: dict, original_message: str):
        """Handle detected anomaly by posting warning and asking for confirmation."""
        severity = analysis.get("severity", "medium")
        reason = analysis.get("reason", "Suspicious trading activity detected")
        recommendation = analysis.get("recommendation", "Review the action")
        
        # Create warning message
        warning = f"""
🚨 TRADING ANOMALY DETECTED ({severity.upper()}) 🚨

Original Message: "{original_message}"
Action Taken: {action.get('tool', 'unknown')} {action.get('args', {})}

Issue: {reason}

Recommendation: {recommendation}

React with 👍 if this trade was intentional
React with ❌ if you want to REVERSE this action immediately
        """.strip()
        
        self.post_warning_to_chat(warning, user="🛡️ GUARDIAN_AI")
        
        # Store for potential rectification
        self.pending_confirmation = {
            "action": action,
            "rectification": self.generate_rectification_command(action, recommendation),
            "timestamp": datetime.now().isoformat()
        }
        
        # Wait for user response (check for rectification messages)
        await self.wait_for_user_response()
    
    async def wait_for_user_response(self, timeout: int = 30):
        """Wait for user to respond to anomaly warning."""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            chat = await self.get_latest_chat()
            if "messages" in chat and chat.get("messages"):
                latest = chat["messages"][-1]
                text = latest.get("text", "")
                user = latest.get("user", "")
                
                # Skip if it's a Guardian AI message
                if user == "🛡️ GUARDIAN_AI":
                    await asyncio.sleep(1)
                    continue
                
                text_lower = text.lower()
                
                # Check for rectification confirmation
                if "❌" in text or "reverse" in text_lower or "undo" in text_lower:
                    if self.pending_confirmation:
                        rectification_msg = self.pending_confirmation["rectification"]
                        
                        # Notify that rectification is being initiated
                        self.post_warning_to_chat("🔄 Initiating trade reversal...", user="🛡️ GUARDIAN_AI")
                        await asyncio.sleep(0.5)  # Brief pause
                        
                        # Send the rectification command
                        self.post_warning_to_chat(rectification_msg, user="🛡️ GUARDIAN_AI")
                        print(f"✅ Rectification command sent: {rectification_msg}")
                        
                        # Wait a moment for actor to execute
                        await asyncio.sleep(2)
                        
                        # Confirm completion
                        self.post_warning_to_chat("✅ Reversal command sent to Actor AI. Trade should be reversed shortly.", user="🛡️ GUARDIAN_AI")
                        
                        self.pending_confirmation = None
                        return True
                
                # User confirmed it was intentional
                elif "👍" in text or "intentional" in text_lower or "correct" in text_lower:
                    self.post_warning_to_chat("✅ Trade confirmed as intentional. Continuing monitoring.", user="🛡️ GUARDIAN_AI")
                    self.pending_confirmation = None
                    return False
            
            await asyncio.sleep(1)
        
        # Timeout - assume user didn't respond
        print("⏱️ User response timeout - assuming trade was intentional")
        self.post_warning_to_chat("⏱️ No response received. Assuming trade was intentional. Continuing monitoring.", user="🛡️ GUARDIAN_AI")
        self.pending_confirmation = None
        return False


async def monitor_actor_actions(critic: CriticMonitor):
    """Monitor chatroom and actor actions for anomalies."""
    print("🛡️ Critic AI Started - Monitoring for trading anomalies...")
    print(f"📡 Chat Server: {chat_server_url}")
    print(f"📡 MCP Server: {mcp_server_url}")
    print(f"📄 Monitoring action log: {ACTION_LOG_FILE}")
    
    # Clear action log from previous session
    import os
    if os.path.exists(ACTION_LOG_FILE):
        print(f"🗑️  Clearing previous session action log...")
        os.remove(ACTION_LOG_FILE)
    
    print("✅ Ready to monitor\n")
    
    while True:
        try:
            # Get actor's recent actions
            actions = critic.get_actor_actions()
            
            # Check for new actions
            if len(actions) > critic.last_action_count:
                # Process new actions
                new_actions = actions[critic.last_action_count:]
                critic.last_action_count = len(actions)
                
                for action_entry in new_actions:
                    message = action_entry.get("message", "")
                    tool = action_entry.get("tool", "")
                    args = action_entry.get("args", {})
                    result = action_entry.get("result", "")
                    timestamp = action_entry.get("timestamp", "")
                    
                    # Skip system messages (Guardian AI, Actor AI commands)
                    if message.startswith("@") or "🛡️" in message or "GUARDIAN" in message.upper():
                        print(f"\n⏭️  Skipping system message: '{message[:50]}...'")
                        continue
                    
                    print(f"\n👁️ New action detected: {tool} with {args}")
                    print(f"   Triggered by: '{message}'")
                    
                    # Skip monitoring tools (list_stocks, list_portfolio)
                    if tool in ["list_stocks", "list_portfolio"]:
                        print("   ✅ Monitoring action - no anomaly check needed")
                        continue
                    
                    # Build action dict for analysis
                    action_dict = {
                        "tool": tool,
                        "args": args,
                        "message": message,
                        "timestamp": timestamp
                    }
                    
                    # Get conversation context
                    chat = await critic.get_latest_chat()
                    conversation_context = []
                    if "messages" in chat and chat.get("messages"):
                        # Filter out Guardian AI messages from context
                        conversation_context = [
                            {"user": msg.get("user"), "text": msg.get("text")}
                            for msg in chat["messages"][-10:]
                            if msg.get("user") != "🛡️ GUARDIAN_AI"
                        ]
                    
                    # Analyze for anomalies
                    analysis = critic.analyze_action(message, action_dict, conversation_context)
                    
                    if analysis.get("is_anomaly", False):
                        severity = analysis.get("severity", "medium")
                        print(f"🚨 ANOMALY DETECTED ({severity}): {analysis.get('reason')}")
                        await critic.handle_anomaly(analysis, action_dict, message)
                    else:
                        print(f"   ✅ Action appears legitimate")
                        
        except FileNotFoundError:
            # Action log doesn't exist yet
            pass
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse action log: {e}")
        except Exception as e:
            print(f"❌ Unexpected error in critic monitoring: {e}")
        
        await asyncio.sleep(2)  # Check every 2 seconds


if __name__ == "__main__":
    critic = CriticMonitor()
    asyncio.run(monitor_actor_actions(critic))
