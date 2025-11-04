import json
import asyncio
import ollama
from llama_index.tools.mcp import BasicMCPClient
import finnhub
import requests
import yaml
from datetime import datetime
from SYSTEM_PROMPT import system_prompt, custom_system_prompt


# load ips from yaml
with open("ip.yaml", 'r') as f:
    ips = yaml.safe_load(f)


# ---------------------- MCP CLIENT ----------------------
mcp_server_url = ips.get("mcp_server_url", "http://127.0.0.1:8000/sse")
chat_server_url = ips.get("chat_server_url", "http://127.0.0.1:6060/api/messages")
post_chat_url = ips.get("post_chat_url", "http://127.0.0.1:6060/api/chat")
mcp_client = BasicMCPClient(mcp_server_url)

# Shared action log for critic to monitor
ACTION_LOG_FILE = "actor_actions.json"

# ---------------------- FINNHUB CLIENT ----------------------
finnhub_client = finnhub.Client(api_key="d44ajupr01qt371u4s5gd44ajupr01qt371u4s60")



class ChatHistory:
    def __init__(self):
        self.messages = []
        self.last_message = None
        self.count = 0
        self.ollama_history = []  # Track conversation history for Ollama

    async def get_latest_chat(self, chat_server_url: str):
        """Fetch the latest chat messages from the chatroom server."""
        try:
            response = requests.get(chat_server_url)
            response.raise_for_status()
            # print(response.json())
            return response.json()
        except requests.RequestException as e:
            return {"error": f"Failed to fetch latest chat: {e}"}
    
    def add_to_ollama_history(self, role: str, content: str):
        """Add a message to Ollama conversation history."""
        self.ollama_history.append({"role": role, "content": content})
    
    def get_ollama_history(self):
        """Get the full Ollama conversation history."""
        return self.ollama_history


# ---------------------- OLLAMA REASONER ----------------------
def ollama_reason(prompt, conversation_history, custom_system_prompt=None):
    """Ask Ollama which MCP tool to call and with what arguments."""
    
    # Use custom system prompt if provided, otherwise use default
    sys_prompt = custom_system_prompt if custom_system_prompt else system_prompt
    
    # Build messages with system prompt and history
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})
    
    resp = ollama.chat(
        # model="qwen2.5:7b",
        model="falcon3:10b",
        messages=messages,
        format="json"  # Force JSON output
    )
    return resp["message"]["content"]

# ---------------------- TOOL CALLER ----------------------
async def call_mcp_tool(tool_name, args):
    """Call MCP tool and handle response."""
    try:
        res = await mcp_client.call_tool(tool_name, args)
        return res
    except Exception as e:
        print(f"❌ MCP Connection Error: {str(e)}")
        print(f"   Make sure MCP server is running at: {mcp_server_url}")
        return {"error": f"MCP server error: {str(e)}"}

def parse_mcp_result(result):
    """Parse MCP result into readable format."""
    if hasattr(result, 'content') and result.content:
        # Extract text from TextContent objects
        text_parts = []
        for item in result.content:
            if hasattr(item, 'text'):
                text_parts.append(item.text)
        
        # Try to parse as JSON first
        combined = ''.join(text_parts)
        try:
            import json
            return json.loads(combined)
        except:
            # If list_stocks, format as structured data
            if len(text_parts) % 3 == 0:  # Likely stock data (symbol, name, price)
                stocks = []
                for i in range(0, len(text_parts), 3):
                    stocks.append({
                        "symbol": text_parts[i],
                        "name": text_parts[i+1],
                        "price": float(text_parts[i+2])
                    })
                return stocks
            return combined
    return result

def send_action_to_flask(message: str, tool: str, args: dict, result: any):
    """Send action data to Flask server for real-time display."""
    try:
        action_data = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "tool": tool,
            "args": args,
            "result": str(result)[:500],  # Truncate long results
            "status": "success" if "error" not in str(result).lower() else "error"
        }
        
        # Send to Flask server
        flask_action_url = ips.get("flask_action_url", "http://127.0.0.1:7070/api/actor_action")
        response = requests.post(
            flask_action_url,
            json=action_data,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"📤 Action sent to Flask server successfully")
        else:
            print(f"⚠️ Flask server responded with status: {response.status_code}")
            
    except requests.RequestException as e:
        print(f"⚠️ Failed to send action to Flask server: {e}")
    except Exception as e:
        print(f"⚠️ Error sending action to Flask: {e}")

def log_action_for_critic(message: str, tool: str, args: dict, result: any):
    """Send actions to Flask server for real-time display and keep minimal file log for critic."""
    import os
    from datetime import datetime
    
    # Send to Flask server for real-time display (primary method)
    send_action_to_flask(message, tool, args, result)
    
    # Keep minimal file log only for critic monitoring (optional)
    action_entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "tool": tool,
        "args": args,
        "result": str(result)[:500]  # Truncate long results
    }
    
    # Read existing log
    if os.path.exists(ACTION_LOG_FILE):
        with open(ACTION_LOG_FILE, 'r') as f:
            try:
                log = json.load(f)
            except:
                log = []
    else:
        log = []
    
    # Append new action
    log.append(action_entry)
    
    # Keep only last 50 actions
    log = log[-50:]
    
    # Write back
    with open(ACTION_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)

# ---------------------- FINNHUB ANALYZER ----------------------
def analyze_stock(symbol: str):
    """Fetch and display some live data for realism."""
    try:
        quote = finnhub_client.quote(symbol)
        fundamentals = finnhub_client.company_basic_financials(symbol, 'all')
        price = quote.get('c', None)
        change = quote.get('dp', None)
        return {
            "symbol": symbol,
            "current_price": price,
            "daily_change_%": change,
            "fundamentals": fundamentals.get("metric", {})
        }
    except Exception as e:
        return {"error": f"Finnhub failed: {e}"}

# ---------------------- MAIN LOOP ----------------------
async def get_ollama_decision(user_input: str, chat_history: ChatHistory, custom_system_prompt=None):
    """Process user input and execute trading actions."""
    # Let Ollama reason with full conversation history
    decision_json = ollama_reason(user_input, chat_history.get_ollama_history(), custom_system_prompt)
    
    # Add user message to history
    chat_history.add_to_ollama_history("user", user_input)
    
    try:
        # Clean up the response
        decision_json = decision_json.strip()
        
        # Extract only the first complete JSON object
        if "{" in decision_json:
            start = decision_json.find("{")
            # Find matching closing brace
            brace_count = 0
            end = start
            for i, char in enumerate(decision_json[start:], start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            decision_json = decision_json[start:end]
        
        decision = json.loads(decision_json)
        
        # Add assistant response to history
        chat_history.add_to_ollama_history("assistant", json.dumps(decision))
        
        # Check if empty response (no action needed)
        if not decision or "tool" not in decision:
            return None
            
        tool = decision["tool"]
        args = decision.get("args", {})
        
        # If user mentions a stock symbol, fetch live data first
        if "symbol" in args:
            live_data = analyze_stock(args["symbol"])
            print(f"📈 Live Data for {args['symbol']}: Price=${live_data.get('current_price', 'N/A')}, Change={live_data.get('daily_change_%', 'N/A')}%")
        
        print(f"🧰 Executing: {tool} with {args}")
        result = await call_mcp_tool(tool, args)
        parsed_result = parse_mcp_result(result)
        print(f"✅ Result: {json.dumps(parsed_result, indent=2)}")
        
        # Log action for critic to monitor
        log_action_for_critic(user_input, tool, args, parsed_result)
        
        # Add tool result to history so LLM knows what happened
        result_msg = f"Tool '{tool}' executed. Result: {json.dumps(parsed_result)}"
        chat_history.add_to_ollama_history("assistant", result_msg)
        
        # If this was list_portfolio and user wanted to sell, trigger another decision
        if tool == "list_portfolio" and "sell" in user_input.lower():
            print("🔄 Continuing to execute sell orders...")
            await asyncio.sleep(0.5)  # Brief pause
            
            # Extract portfolio info
            if isinstance(parsed_result, dict) and "portfolio" in parsed_result:
                portfolio = parsed_result["portfolio"]
                
                # Check if a specific stock was mentioned in the sell command
                target_symbol = None
                available_stocks = ["AAPL", "TSLA", "MSFT", "GOOGL", "NVDA"]
                for stock_symbol in available_stocks:
                    if stock_symbol in user_input.upper():
                        target_symbol = stock_symbol
                        break
                
                # Sell each stock one by one
                for stock_entry in portfolio:
                    symbol = stock_entry[0]
                    quantity = stock_entry[1]
                    
                    # If a target is specified, only sell that stock. Otherwise, sell all.
                    if target_symbol and symbol != target_symbol:
                        continue # Skip stocks that don't match the target

                    if quantity > 0:
                        print(f"🔄 Selling {quantity} shares of {symbol}...")
                        sell_result = await call_mcp_tool("sell_stock", {"symbol": symbol, "quantity": quantity})
                        sell_parsed = parse_mcp_result(sell_result)
                        print(f"✅ Sold: {json.dumps(sell_parsed, indent=2)}")
                        
                        # Log each sell action
                        log_action_for_critic(user_input, "sell_stock", {"symbol": symbol, "quantity": quantity}, sell_parsed)
                        await asyncio.sleep(0.3)  # Brief pause between sells
                
                print("✅ All specified stocks sold!")
        
        return parsed_result
        
    except json.JSONDecodeError as e:
        print(f"⚠️ LLM returned invalid JSON")
        print(f"   Raw response: {decision_json[:200]}")
        print(f"   Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error processing decision: {e}")
        return None


async def fetch_chats_periodically(chat_history):
    """Monitor chat server and process trading messages."""
    while True:
        try:
            latest_chat = await chat_history.get_latest_chat(chat_server_url)
            
            if "error" in latest_chat:
                print(f"⚠️ {latest_chat['error']}")
                await asyncio.sleep(1)
                continue
            
            # Check if messages exist and list is not empty
            if "messages" not in latest_chat or not latest_chat["messages"]:
                await asyncio.sleep(1)
                continue
            
            if latest_chat != chat_history.last_message:
                chat_history.last_message = latest_chat
                chat_history.count += 1
                
                # Get the latest message
                latest_message = latest_chat['messages'][-1]
                user = latest_message.get('user', 'Unknown')
                
                # Skip Guardian AI warning messages (but not rectification commands)
                if user == "🛡️ GUARDIAN_AI" and not latest_message.get('text', '').startswith('@ACTOR_AI'):
                    await asyncio.sleep(1)
                    continue
                    
                text = latest_message.get('text', '')
                
                # Handle Guardian AI rectification commands
                stripped_text = text.strip()
                if user == "🛡️ GUARDIAN_AI" and stripped_text.lower().startswith('@actor_ai'):
                    print(f"\n🛡️ Guardian AI Rectification: {stripped_text}")

                    import re

                    # Match patterns like:
                    # @ACTOR_AI sell 80 MSFT ...
                    # @ACTOR_AI buy back 80 MSFT ...
                    rectification_regex = re.compile(
                        r"@actor_ai\s+(buy(?:\s+back)?|sell)\s+(\d+)\s+([a-zA-Z]+)",
                        re.IGNORECASE
                    )

                    match = rectification_regex.search(stripped_text)

                    if not match:
                        print("❌ Failed to parse rectification command: pattern not recognized")
                        await asyncio.sleep(1)
                        continue

                    action_word, quantity_str, symbol = match.groups()
                    symbol = symbol.upper()

                    try:
                        quantity = int(quantity_str)
                    except ValueError:
                        print("❌ Failed to parse rectification command: invalid quantity")
                        await asyncio.sleep(1)
                        continue

                    tool_to_call = "sell_stock" if action_word.lower().startswith("sell") else "buy_stock"

                    print(f"🔄 Executing rectification: {tool_to_call} quantity={quantity} symbol={symbol}")
                    result = await call_mcp_tool(tool_to_call, {"symbol": symbol, "quantity": quantity})
                    parsed_result = parse_mcp_result(result)
                    print(f"✅ Rectification complete: {json.dumps(parsed_result, indent=2)}")
                    log_action_for_critic(stripped_text, tool_to_call, {"symbol": symbol, "quantity": quantity}, parsed_result)
                    
                    await asyncio.sleep(1)
                    continue
                
                # Skip other system commands
                if text.startswith("@"):
                    await asyncio.sleep(1)
                    continue
                
                print(f"\n💬 Message #{chat_history.count} from {user}: {text}")
                
                # Process the message for trading actions with custom system prompt
                await get_ollama_decision(text, chat_history, custom_system_prompt)
                
        except KeyError as e:
            print(f"⚠️ Missing expected data in chat response: {e}")
        except IndexError as e:
            print(f"⚠️ Empty message list received")
        except Exception as e:
            print(f"❌ Unexpected error in chat monitoring: {e}")
            
        await asyncio.sleep(1)  # wait for 1 second before fetching again

if __name__ == "__main__":
    print("🚀 Trading Agent Started - Monitoring chat for trading signals...")
    print(f"📡 Chat Server: {chat_server_url}")
    print(f"📡 MCP Server: {mcp_server_url}")
    print(f"📡 Flask Action URL: {ips.get('flask_action_url', 'http://127.0.0.1:7070/api/actor_action')}")
    print(f"⚠️  Make sure MCP server is running: python mcp_server.py --server_type sse")
    print(f"⚠️  Make sure Flask server is running: python flask_chatroom.py")
    print()
    
    # Test connection to Flask server
    try:
        flask_action_url = ips.get("flask_action_url", "http://127.0.0.1:7070/api/actor_action")
        test_response = requests.get(flask_action_url.replace('/actor_action', '/messages'), timeout=3)
        if test_response.status_code == 200:
            print("✅ Flask server connection test successful")
        else:
            print(f"⚠️ Flask server responded with status: {test_response.status_code}")
    except Exception as e:
        print(f"⚠️ Cannot connect to Flask server: {e}")
    print()
    
    chat_history = ChatHistory()
    asyncio.run(fetch_chats_periodically(chat_history=chat_history))
    