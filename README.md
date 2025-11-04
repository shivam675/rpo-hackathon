# Multi-Agent Trading System with LLMs

This project implements a multi-agent system for simulated stock trading, featuring an interactive web dashboard, an autonomous trading "Actor" AI, and a "Critic" AI for oversight. The system is powered by local language models via Ollama and communicates using the Model Context Protocol (MCP).

## Architecture

The system consists of four main components that run concurrently:

1.  **MCP Server (`mcp_server.py`)**: The core backend service. It manages the trading environment, including the user's portfolio, wallet balance (in `trading.db`), and provides the fundamental trading tools (`buy_stock`, `sell_stock`, `list_portfolio`).

2.  **Flask Web UI (`flask_chatroom.py`)**: A real-time web dashboard with three main panels:
    *   **Portfolio**: Displays current cash, stock holdings, and total portfolio value.
    *   **Actor AI Live Feed**: Shows a real-time stream of actions taken by the Actor AI.
    *   **Chatroom**: The user interface for interacting with the system.

3.  **Actor AI (`actor.py`)**: The autonomous agent that interprets user messages from the chat. It uses a local LLM to decide which trading tool to use and executes it by calling the MCP Server.

4.  **Critic AI (`critic.py`)**: A guardian agent that monitors the Actor's actions for anomalies. If it detects a potentially erroneous trade (e.g., interpreting a joke as a command), it posts a warning to the chat and can initiate a reversal.

```
+-------------------+      +----------------------+      +---------------------+
|                   |      |                      |      |                     |
|   User via Browser|----->|  Flask Web UI        |----->|   Actor AI          |
| (localhost:7070)  |      | (flask_chatroom.py)  |<-----|  (actor.py)         |
|                   |      |                      |      |                     |
+-------------------+      +----------+-----------+      +----------+----------+
       ^                             |                           |
       |                             |                           |
       | (POST warnings)             | (GET chat)                | (Calls tools)
       |                             |                           |
+------v-----------+      +----------v-----------+      +---------v-----------+
|                  |      |                      |      |                     |
|   Critic AI      |<-----|   Action Log         |<-----|   MCP Server        |
|   (critic.py)    |      |  (actor_actions.json)|      |  (mcp_server.py)    |
|                  |      |                      |      | (localhost:8000)    |
+------------------+      +----------------------+      +---------------------+
```

## Features

- **LLM-Powered Trading**: Uses a local LLM (`falcon3:10b`) to understand natural language commands.
- **Real-Time Dashboard**: A responsive Flask UI provides instant updates on portfolio status and agent actions.
- **Autonomous Agents**: Separate processes for the Actor (execution) and Critic (oversight).
- **Anomaly Detection**: The Critic AI provides a safety layer to prevent accidental trades.
- **Trade Reversal**: The Critic can automatically issue commands to reverse anomalous trades if confirmed by the user.
- **Configurable**: Key endpoints are managed via `ip.yaml`.

## Prerequisites

- Python 3.8+
- [Ollama](https://ollama.com/) installed and running.
- The required LLM model pulled via Ollama:
  ```bash
  ollama pull falcon3:10b
  ```

## Setup

1.  **Clone the repository** (if you haven't already).

2.  **Create and activate a Python virtual environment**:
    ```bash
    python -m venv mcp_env
    source mcp_env/bin/activate
    ```

3.  **Install the required dependencies**:
    ```bash
    pip install flask ollama llama-index requests pyyaml finnhub-python
    ```
    *(Note: You may want to create a `requirements.txt` file for easier setup).*

4.  **Configure Endpoints** (Optional): The default values in `ip.yaml` are configured for a local setup. You can modify the ports here if needed.

## Running the Application

You need to run the four main components in **four separate terminals** from the `/home/sentinal/llms/mcp_agent` directory.

**Terminal 1: Start the MCP Server**
```bash
source mcp_env/bin/activate
python mcp_server.py --server_type sse
```
*This server must be running first. It provides the trading tools.*

**Terminal 2: Start the Flask Web UI**
```bash
source mcp_env/bin/activate
python flask_chatroom.py
```
*This serves the web dashboard. You can access it at `http://127.0.0.1:7070`.*

**Terminal 3: Start the Actor AI**
```bash
source mcp_env/bin/activate
python actor.py
```
*This agent listens to the chat and performs trading actions.*

**Terminal 4: Start the Critic AI**
```bash
source mcp_env/bin/activate
python critic.py
```
*This agent monitors the Actor for mistakes.*

Once all services are running, open your web browser to **`http://127.0.0.1:7070`** to start trading.
