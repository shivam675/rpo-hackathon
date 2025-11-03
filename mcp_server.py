import sqlite3
import argparse
import random
import asyncio
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("trading-sim")

# -------------------- DATABASE SETUP --------------------
def init_db():
    conn = sqlite3.connect("trading.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            symbol TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallet (
            id INTEGER PRIMARY KEY,
            balance REAL NOT NULL
        )
    """)

    # Initialize wallet
    cursor.execute("SELECT COUNT(*) FROM wallet")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO wallet (id, balance) VALUES (1, 524000)")

    # Seed stock list
    cursor.execute("SELECT COUNT(*) FROM stocks")
    if cursor.fetchone()[0] == 0:
        initial_stocks = [
            ("AAPL", "Apple Inc.", 640.5),
            ("TSLA", "Tesla Motors", 920.2),
            ("MSFT", "Microsoft Corp.", 470.3),
            ("GOOGL", "Alphabet Inc.", 820.7),
            ("NVDA", "NVIDIA Corp.", 1200.5)
        ]
        cursor.executemany(
            "INSERT INTO stocks (symbol, name, price) VALUES (?, ?, ?)",
            initial_stocks
        )

    conn.commit()
    return conn, cursor


# -------------------- HELPERS --------------------
def update_stock_prices(cursor):
    """Simulate small price movements."""
    cursor.execute("SELECT symbol, price FROM stocks")
    stocks = cursor.fetchall()
    for symbol, price in stocks:
        change = random.uniform(-0.03, 0.03)  # ±3%
        new_price = round(price * (1 + change), 2)
        cursor.execute("UPDATE stocks SET price = ? WHERE symbol = ?", (new_price, symbol))


# -------------------- TOOLS --------------------
@mcp.tool("list_stocks")
async def list_stocks() -> list:
    """List all available stocks and their current prices."""
    conn, cursor = init_db()
    try:
        update_stock_prices(cursor)
        conn.commit()
        cursor.execute("SELECT symbol, name, price FROM stocks")
        return cursor.fetchall()
    finally:
        conn.close()


@mcp.tool("list_portfolio")
async def list_portfolio() -> dict:
    """List owned stocks and current wallet balance."""
    conn, cursor = init_db()
    try:
        cursor.execute("SELECT symbol, quantity FROM portfolio")
        holdings = cursor.fetchall()
        cursor.execute("SELECT balance FROM wallet WHERE id=1")
        balance = cursor.fetchone()[0]
        return {"balance_AED": round(balance, 2), "portfolio": holdings}
    finally:
        conn.close()


@mcp.tool("buy_stock")
async def buy_stock(symbol: str, quantity: int) -> dict:
    """Buy a given quantity of stock at current market price."""
    conn, cursor = init_db()
    try:
        update_stock_prices(cursor)
        conn.commit()

        cursor.execute("SELECT price FROM stocks WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Stock '{symbol}' not found."}

        price = row[0]
        cost = price * quantity

        cursor.execute("SELECT balance FROM wallet WHERE id=1")
        balance = cursor.fetchone()[0]
        if cost > balance:
            return {"error": f"Insufficient funds. Required: {cost:.2f}, Available: {balance:.2f}"}

        new_balance = balance - cost
        cursor.execute("UPDATE wallet SET balance=? WHERE id=1", (new_balance,))
        cursor.execute("INSERT OR IGNORE INTO portfolio (symbol, quantity) VALUES (?, 0)", (symbol,))
        cursor.execute("UPDATE portfolio SET quantity = quantity + ? WHERE symbol=?", (quantity, symbol))
        conn.commit()

        return {
            "status": "bought",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "cost": cost,
            "new_balance": round(new_balance, 2)
        }
    finally:
        conn.close()


@mcp.tool("sell_stock")
async def sell_stock(symbol: str, quantity: int) -> dict:
    """Sell a given quantity of owned stock."""
    conn, cursor = init_db()
    try:
        update_stock_prices(cursor)
        conn.commit()

        cursor.execute("SELECT price FROM stocks WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Stock '{symbol}' not found."}

        price = row[0]
        revenue = price * quantity

        cursor.execute("SELECT quantity FROM portfolio WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        if not row or row[0] < quantity:
            return {"error": f"Not enough shares to sell. Owned: {row[0] if row else 0}"}

        new_qty = row[0] - quantity
        if new_qty == 0:
            cursor.execute("DELETE FROM portfolio WHERE symbol=?", (symbol,))
        else:
            cursor.execute("UPDATE portfolio SET quantity=? WHERE symbol=?", (new_qty, symbol))

        cursor.execute("SELECT balance FROM wallet WHERE id=1")
        balance = cursor.fetchone()[0]
        new_balance = balance + revenue
        cursor.execute("UPDATE wallet SET balance=? WHERE id=1", (new_balance,))
        conn.commit()

        return {
            "status": "sold",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "revenue": revenue,
            "new_balance": round(new_balance, 2)
        }
    finally:
        conn.close()


# -------------------- MAIN --------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_type", type=str, default="sse", choices=["sse", "stdio"])
    args = parser.parse_args()

    print("🚀 Starting Trading MCP Server...")
    asyncio.run(mcp.run(args.server_type))
