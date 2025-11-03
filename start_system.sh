#!/bin/bash

# Trading Agent System Startup Script

echo "🚀 Starting Trading Agent System with Critic AI"
echo "================================================"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down all processes..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Virtual environment not detected"
    echo "   Consider activating mcp_env first: source mcp_env/bin/activate"
    echo ""
fi

# Clear old logs
if [ -f "actor_actions.json" ]; then
    echo "🗑️  Clearing previous session logs..."
    rm -f actor_actions.json
fi

echo "Starting components..."
echo ""

# Start MCP Server
echo "1️⃣  Starting MCP Server..."
python mcp_server.py --server_type sse > mcp_server.log 2>&1 &
MCP_PID=$!
sleep 2

if ! kill -0 $MCP_PID 2>/dev/null; then
    echo "❌ Failed to start MCP Server"
    exit 1
fi
echo "   ✅ MCP Server running (PID: $MCP_PID)"

# Start Actor AI
echo "2️⃣  Starting Actor AI..."
python actor.py > actor.log 2>&1 &
ACTOR_PID=$!
sleep 2

if ! kill -0 $ACTOR_PID 2>/dev/null; then
    echo "❌ Failed to start Actor AI"
    kill $MCP_PID 2>/dev/null
    exit 1
fi
echo "   ✅ Actor AI running (PID: $ACTOR_PID)"

# Start Critic AI
echo "3️⃣  Starting Critic AI..."
python critic.py > critic.log 2>&1 &
CRITIC_PID=$!
sleep 2

if ! kill -0 $CRITIC_PID 2>/dev/null; then
    echo "❌ Failed to start Critic AI"
    kill $MCP_PID $ACTOR_PID 2>/dev/null
    exit 1
fi
echo "   ✅ Critic AI running (PID: $CRITIC_PID)"

echo ""
echo "✨ All systems operational!"
echo "================================================"
echo "📊 View logs:"
echo "   Actor:  tail -f actor.log"
echo "   Critic: tail -f critic.log"
echo "   MCP:    tail -f mcp_server.log"
echo ""
echo "Press Ctrl+C to stop all systems"
echo ""

# Wait for all processes
wait
