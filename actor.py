import json
import asyncio
import ollama
from llama_index.tools.mcp import BasicMCPClient
import finnhub
import requests
import yaml
from SYSTEM_PROMPT import system_prompt, custom_system_prompt


# load ips from yaml
with open("ip.yaml", 'r') as f:
    ips = yaml.safe_load(f)


# ---------------------- MCP CLIENT ----------------------
mcp_server_url = ips.get("mcp_server_url", "http://127.0.0.1:8000/sse")
chat_server_url = ips.get("chat_server_url", "http://127.0.0.1:6060/api/messages")
mcp_client = BasicMCPClient(mcp_server_url)

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
        model="qwen2.5:7b",
        messages=messages
    )
    return resp["message"]["content"]

# ---------------------- TOOL CALLER ----------------------
async def call_mcp_tool(tool_name, args):
    """Call MCP tool and handle response."""
    try:
        res = await mcp_client.call_tool(tool_name, args)
        return res
    except Exception as e:
        return {"error": str(e)}

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
        decision = json.loads(decision_json)
        
        # Add assistant response to history
        chat_history.add_to_ollama_history("assistant", decision_json)
        
        if "tool" not in decision:
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
        
        # Add tool result to history so LLM knows what happened
        result_msg = f"Tool '{tool}' executed. Result: {json.dumps(parsed_result)}"
        chat_history.add_to_ollama_history("assistant", result_msg)
        
        # If this was list_portfolio and user wanted to sell, trigger another decision
        if tool == "list_portfolio" and "sell" in user_input.lower():
            print("🔄 Continuing to execute sell orders...")
            await asyncio.sleep(0.5)  # Brief pause
            await get_ollama_decision(user_input, chat_history, custom_system_prompt)
        
        return parsed_result
        
    except json.JSONDecodeError:
        print(f"⚠️ LLM returned invalid JSON for message: '{user_input}'")
        # Still add the response to history even if it's not valid JSON
        chat_history.add_to_ollama_history("assistant", decision_json)
        return None
    except Exception as e:
        print(f"❌ Error processing decision: {e}")
        return None


async def fetch_chats_periodically(chat_history):
    """Monitor chat server and process trading messages."""
    while True:
        latest_chat = await chat_history.get_latest_chat(chat_server_url)
        
        if "error" not in latest_chat:
            if latest_chat != chat_history.last_message:
                chat_history.last_message = latest_chat
                chat_history.count += 1
                
                # Get the latest message
                latest_message = latest_chat['messages'][-1]
                user = latest_message.get('user', 'Unknown')
                text = latest_message.get('text', '')
                
                print(f"\n💬 Message #{chat_history.count} from {user}: {text}")
                
                # Process the message for trading actions with custom system prompt
                await get_ollama_decision(text, chat_history, custom_system_prompt)
        else:
            print(f"⚠️ {latest_chat['error']}")
            
        await asyncio.sleep(1)  # wait for 1 second before fetching again

if __name__ == "__main__":
    print("🚀 Trading Agent Started - Monitoring chat for trading signals...")
    chat_history = ChatHistory()
    asyncio.run(fetch_chats_periodically(chat_history=chat_history))
    