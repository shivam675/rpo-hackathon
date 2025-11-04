from llama_index.tools.mcp import BasicMCPClient
import asyncio
import json
import requests
import yaml
import os
import finnhub
import ollama
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


# ---------------------- LANGFLOW INTEGRATION ----------------------
class LangflowIntegration:
    def __init__(self, base_url: str, flow_id: str = None):
        self.base_url = base_url
        self.flow_id = flow_id
        self.session = requests.Session()
    
    async def get_trading_decision(self, message: str, context: dict = None):
        """Get trading decision from Langflow."""
        try:
            # Langflow API endpoint
            url = f"{self.base_url}/api/v1/run/{self.flow_id}" if self.flow_id else f"{self.base_url}/api/v1/process"
            
            payload = {
                "input_value": message,
                "output_type": "chat",
                "input_type": "chat"
            }
            
            # Add context/tweaks if provided
            if context:
                payload["tweaks"] = context
            
            print(f"🔗 Calling Langflow: {url}")
            print(f"📤 Payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            print(f"📥 Langflow Response: {json.dumps(result, indent=2)}")
            
            # Extract the decision from Langflow response
            # This may need adjustment based on your flow's output structure
            if "outputs" in result:
                outputs = result["outputs"]
                if outputs and len(outputs) > 0:
                    first_output = outputs[0]
                    if "outputs" in first_output:
                        nested_outputs = first_output["outputs"]
                        if nested_outputs and len(nested_outputs) > 0:
                            return nested_outputs[0].get("results", {})
            
            # Fallback: try to find text in various locations
            if "result" in result:
                return result["result"]
            elif "message" in result:
                return result["message"]
            
            return result
            
        except requests.exceptions.Timeout:
            print("⏰ Langflow request timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Langflow API error: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected Langflow error: {e}")
            return None
    
    def set_flow_id(self, flow_id: str):
        """Update the flow ID"""
        self.flow_id = flow_id


class ChatHistory:
    def __init__(self):
        self.messages = []
        self.last_message = None
        self.count = 0
        self.ollama_history = []  # Track conversation history for Ollama

    async def get_latest_chat(self, chat_server_url: str):
        """Fetch the latest chat messages from the chatroom server."""
        try:
            response = requests.get(chat_server_url, timeout=5)
            response.raise_for_status()
            result = response.json()
            # Ensure we always return a list
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'messages' in result:
                return result['messages']
            else:
                return []
        except requests.RequestException as e:
            # Only print error once every 30 seconds to avoid spam
            if not hasattr(self, 'last_error_time') or (asyncio.get_event_loop().time() - self.last_error_time) > 30:
                print(f"❌ Chat server connection error: {e}")
                self.last_error_time = asyncio.get_event_loop().time()
            return []
        except Exception as e:
            print(f"❌ Unexpected chat server error: {e}")
            return []
    
    def add_to_ollama_history(self, role: str, content: str):
        """Add a message to Ollama conversation history."""
        self.ollama_history.append({"role": role, "content": content})
    
    def get_ollama_history(self):
        """Get the full Ollama conversation history."""
        return self.ollama_history


# ---------------------- OLLAMA REASONER (FALLBACK) ----------------------
def ollama_reason(prompt, conversation_history, custom_system_prompt=None):
    """Ask Ollama which MCP tool to call and with what arguments (fallback)."""
    
    # Use custom system prompt if provided, otherwise use default
    sys_prompt = custom_system_prompt if custom_system_prompt else system_prompt
    
    # Build messages with system prompt and history
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})
    
    resp = ollama.chat(
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
            return json.loads(combined)
        except:
            return combined
            
    return result


def log_action_for_critic(message: str, tool: str, args: dict, result: any):
    """Log actions to file for critic to monitor."""
    import os
    import json
    from datetime import datetime
    
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


# ---------------------- MAIN DECISION LOGIC ----------------------
async def get_langflow_decision(user_input: str, chat_history: ChatHistory, langflow: LangflowIntegration, custom_system_prompt=None):
    """Process user input using Langflow reasoning and execute trading actions."""
    
    # Prepare context for Langflow
    context = {
        "conversation_history": json.dumps(chat_history.get_ollama_history()),
        "system_prompt": custom_system_prompt or system_prompt,
        "available_tools": ["buy_stock", "sell_stock", "list_portfolio", "get_balance", "analyze_stock"]
    }
    
    print(f"🤖 Processing with Langflow: {user_input}")
    
    # Try Langflow first
    langflow_result = await langflow.get_trading_decision(user_input, context)
    
    decision_json = None
    
    if langflow_result:
        print(f"✅ Langflow returned: {langflow_result}")
        
        # Try to extract decision from Langflow result
        if isinstance(langflow_result, dict):
            if "tool" in langflow_result:
                decision_json = json.dumps(langflow_result)
            elif "message" in langflow_result:
                decision_json = langflow_result["message"].get("text", "")
            elif "text" in langflow_result:
                decision_json = langflow_result["text"]
        elif isinstance(langflow_result, str):
            decision_json = langflow_result
    
    # Fallback to Ollama if Langflow fails or returns invalid format
    if not decision_json or decision_json.strip() == "":
        print("⚠️ Langflow failed or returned empty, falling back to Ollama...")
        decision_json = ollama_reason(user_input, chat_history.get_ollama_history(), custom_system_prompt)
    
    # Add user message to history
    chat_history.add_to_ollama_history("user", user_input)
    
    try:
        # Clean up the response
        decision_json = decision_json.strip()
        
        # Extract only the first complete JSON object
        if "{" in decision_json:
            start_idx = decision_json.find("{")
            brace_count = 0
            end_idx = start_idx
            
            for i, char in enumerate(decision_json[start_idx:], start_idx):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            decision_json = decision_json[start_idx:end_idx]
        
        decision = json.loads(decision_json)
        
        # Add assistant response to history
        chat_history.add_to_ollama_history("assistant", json.dumps(decision))
        
        # Check if empty response (no action needed)
        if not decision or "tool" not in decision:
            print("ℹ️ No action required")
            return {"message": "No action needed"}
            
        tool = decision["tool"]
        args = decision.get("args", {})
        
        # If user mentions a stock symbol, fetch live data first
        if "symbol" in args:
            stock_data = analyze_stock(args["symbol"])
            print(f"📊 Live data for {args['symbol']}: {json.dumps(stock_data, indent=2)}")
        
        print(f"🧰 Executing: {tool} with {args}")
        result = await call_mcp_tool(tool, args)
        parsed_result = parse_mcp_result(result)
        print(f"✅ Result: {json.dumps(parsed_result, indent=2)}")
        
        # Log action for critic to monitor
        log_action_for_critic(user_input, tool, args, parsed_result)
        
        # Add tool result to history so LLM knows what happened
        result_msg = f"Tool '{tool}' executed. Result: {json.dumps(parsed_result)}"
        chat_history.add_to_ollama_history("assistant", result_msg)
        
        return parsed_result
        
    except json.JSONDecodeError as e:
        print(f"⚠️ Invalid JSON response")
        print(f"   Raw response: {decision_json[:200]}")
        print(f"   Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error processing decision: {e}")
        return None


# ---------------------- MAIN LOOP ----------------------
async def fetch_chats_periodically(chat_history, langflow):
    """Monitor chat server and process trading messages."""
    while True:
        try:
            # Get latest messages
            messages = await chat_history.get_latest_chat(chat_server_url)
            
            if messages and len(messages) > 0:
                latest = messages[-1]
                
                # Check if this is a new message
                if latest != chat_history.last_message:
                    chat_history.last_message = latest
                    chat_history.count += 1
                    
                    message_text = latest.get("message", "")
                    sender = latest.get("sender", "unknown")
                    
                    print(f"\n🔥 New message #{chat_history.count} from {sender}: {message_text}")
                    
                    # Process the trading message using Langflow
                    if message_text.strip():
                        result = await get_langflow_decision(message_text, chat_history, langflow)
                        
                        if result:
                            # Post response back to chat
                            response_data = {
                                "message": f"🤖 Executed: {json.dumps(result)}",
                                "sender": "TradingBot"
                            }
                            
                            try:
                                post_response = requests.post(post_chat_url, json=response_data)
                                if post_response.status_code == 200:
                                    print("✅ Response posted to chat")
                                else:
                                    print(f"⚠️ Failed to post response: {post_response.status_code}")
                            except Exception as e:
                                print(f"❌ Error posting to chat: {e}")
            
        except Exception as e:
            print(f"❌ Error in chat monitoring: {e}")
        
        # Wait before checking again
        await asyncio.sleep(2)


async def test_langflow_integration():
    """Test the Langflow integration with a sample message."""
    print("🧪 Testing Langflow Integration...")
    
    # Initialize components
    langflow_url = ips.get("langflow_url", "http://127.0.0.1:7860")
    langflow_flow_id = ips.get("langflow_flow_id", None)
    
    langflow = LangflowIntegration(langflow_url, langflow_flow_id)
    chat_history = ChatHistory()
    
    # Test messages
    test_messages = [
        "Buy 100 shares of AAPL",
        "Sell 50 shares of TSLA",
        "What's my portfolio balance?",
        "Analyze MSFT stock"
    ]
    
    for msg in test_messages:
        print(f"\n🔍 Testing: '{msg}'")
        result = await get_langflow_decision(msg, chat_history, langflow)
        print(f"📋 Result: {result}")
        print("-" * 50)


if __name__ == "__main__":
    import sys
    
    print("🚀 Langflow Trading Agent")
    print(f"📡 Chat Server: {chat_server_url}")
    print(f"📡 MCP Server: {mcp_server_url}")
    print(f"🌊 Langflow Server: {ips.get('langflow_url', 'http://127.0.0.1:7860')}")
    print(f"🆔 Flow ID: {ips.get('langflow_flow_id', 'Not set')}")
    print()
    
    # Check if user wants test mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🧪 Running in TEST mode...")
        asyncio.run(test_langflow_integration())
    else:
        print("🔄 Starting chat monitoring mode...")
        print("💡 Tip: Run with 'python langflow_actor.py test' to test without chat server")
        print(f"⚠️  Make sure MCP server is running: python mcp_server.py --server_type sse")
        print(f"⚠️  Make sure Langflow server is running: langflow run")
        print()
        
        # Initialize Langflow integration
        langflow_url = ips.get("langflow_url", "http://127.0.0.1:7860")
        langflow_flow_id = ips.get("langflow_flow_id", None)
        
        langflow = LangflowIntegration(langflow_url, langflow_flow_id)
        chat_history = ChatHistory()
        
        try:
            asyncio.run(fetch_chats_periodically(chat_history=chat_history, langflow=langflow))
        except KeyboardInterrupt:
            print("\n👋 Shutting down gracefully...")
        except Exception as e:
            print(f"❌ Fatal error: {e}")