"""
Alpaca Trading MCP Server

This is a Model Context Protocol (MCP) server implementation for Alpaca trading.
It allows LLMs like Claude to interact with Alpaca's trading API, providing
resources for market data and tools for executing trades.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union

# Import MCP server components
from mcp.server.fastmcp import FastMCP, Context

# Import Alpaca components
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

# For loading environment variables
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Alpaca API credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
# Use paper trading by default for safety
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "TRUE").upper() == "TRUE"

# Create a lifespan context manager for proper startup/shutdown handling
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

@asynccontextmanager
async def alpaca_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """
    Manage Alpaca client lifecycle with proper initialization and cleanup.
    This runs on server startup and shutdown.
    """
    global trading_client, data_client
    
    # --- Startup code ---
    logger.info("Initializing Alpaca clients...")
    
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        logger.error("Alpaca API credentials not found. Please set ALPACA_API_KEY and ALPACA_API_SECRET environment variables.")
        raise ValueError("Alpaca API credentials not found")
    
    try:
        # Initialize Trading client (for executing trades and account management)
        trading_client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_API_SECRET,
            paper=ALPACA_PAPER
        )
        
        # Initialize Data client (for market data)
        data_client = StockHistoricalDataClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_API_SECRET,
            sandbox=ALPACA_PAPER # Use sandbox when paper trading is enabled
        )
        
        logger.info("Alpaca clients initialized successfully")
        logger.info(f"Using {'paper' if ALPACA_PAPER else 'live'} trading environment")
        
        # Yield control back to the server (server runs normally here)
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize Alpaca clients: {e}")
        raise
    finally:
        # --- Shutdown code ---
        logger.info("Shutting down Alpaca clients...")
        
        # Set clients to None to help with garbage collection
        trading_client = None
        data_client = None
        logger.info("Alpaca clients shut down")

# Initialize the MCP Server
mcp_server = FastMCP(
    name="Alpaca Trading",
    description="MCP server for trading and market data via Alpaca API",
    version="1.0.0",
    dependencies=["mcp[cli]", "alpaca-py", "python-dotenv"],
    lifespan=alpaca_lifespan
)

# Global clients
trading_client = None
data_client = None


# ========== RESOURCES ==========

@mcp_server.resource("account://info")
async def get_account_info() -> str:
    """Get account information."""
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        account = trading_client.get_account()
        
        # Format the account information as readable text
        account_info = f"""
        Account Information:
        - Account ID: {account.id}
        - Status: {account.status}
        - Cash: ${account.cash}
        - Portfolio Value: ${account.portfolio_value}
        - Buying Power: ${account.buying_power}
        - Equity: ${account.equity}
        - Pattern Day Trader: {account.pattern_day_trader}
        - Trading Blocked: {account.trading_blocked}
        - Account Blocked: {account.account_blocked}
        - Created At: {account.created_at}
        """
        
        return account_info
    except Exception as e:
        logger.error(f"Error fetching account info: {e}")
        return f"Error fetching account information: {str(e)}"


@mcp_server.resource("positions://all")
async def get_all_positions() -> str:
    """Get all current positions."""
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        positions = trading_client.get_all_positions()
        
        if not positions:
            return "No open positions found."
        
        # Format the positions as readable text
        positions_text = "Current Positions:\n\n"
        for pos in positions:
            positions_text += f"""
            Symbol: {pos.symbol}
            Quantity: {pos.qty}
            Side: {pos.side}
            Market Value: ${pos.market_value}
            Cost Basis: ${pos.cost_basis}
            Unrealized P/L: ${pos.unrealized_pl} ({pos.unrealized_plpc}%)
            Current Price: ${pos.current_price}
            -------------------------------------
            """
        
        return positions_text
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return f"Error fetching positions: {str(e)}"


@mcp_server.resource("market://quote/{symbol}")
async def get_quote(symbol: str) -> str:
    """Get latest quote for a symbol."""
    if not symbol:
        return "Error: Symbol parameter is required"
    
    symbol = symbol.upper()
    
    if not data_client:
        return "Error: Data client not initialized"
    
    try:
        request_params = StockLatestQuoteRequest(
            symbol_or_symbols=symbol,
            feed='iex'
        )
        quote = data_client.get_stock_latest_quote(request_params)
        
        if not quote or symbol not in quote:
            return f"No quote data found for {symbol}"
        
        quote_data = quote[symbol]
        
        quote_text = f"""
        Latest Quote for {symbol}:
        - Ask Price: ${quote_data.ask_price}
        - Ask Size: {quote_data.ask_size}
        - Bid Price: ${quote_data.bid_price}
        - Bid Size: {quote_data.bid_size}
        - Timestamp: {quote_data.timestamp}
        """
        
        return quote_text
    except Exception as e:
        logger.error(f"Error fetching quote for {symbol}: {e}")
        return f"Error fetching quote for {symbol}: {str(e)}"


@mcp_server.resource("market://bars/{symbol}")
async def get_bars(symbol: str) -> str:
    """Get historical bars for a symbol."""
    if not symbol:
        return "Error: Symbol parameter is required"
    
    symbol = symbol.upper()
    
    if not data_client:
        return "Error: Data client not initialized"
    
    try:
        # Default to 1-day bars for the past week
        end = datetime.now()
        start = end - timedelta(days=7)
        
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed='iex'
        )
        
        bars = data_client.get_stock_bars(request_params)
        
        if not bars or symbol not in bars:
            return f"No historical data found for {symbol}"
        
        bars_data = bars[symbol]
        
        bars_text = f"Historical Daily Bars for {symbol} (Last 7 days):\n\n"
        for bar in bars_data:
            bars_text += f"""
            Date: {bar.timestamp.date()}
            Open: ${bar.open}
            High: ${bar.high}
            Low: ${bar.low}
            Close: ${bar.close}
            Volume: {bar.volume}
            -------------------------------------
            """
        
        return bars_text
    except Exception as e:
        logger.error(f"Error fetching bars for {symbol}: {e}")
        return f"Error fetching bars for {symbol}: {str(e)}"


@mcp_server.resource("orders://recent")
async def get_recent_orders() -> str:
    """Get recent orders."""
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        # Get orders from the last 7 days
        end = datetime.now()
        start = end - timedelta(days=7)
        
        request_params = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=20,
            after=start,
            until=end
        )
        
        orders = trading_client.get_orders(filter=request_params)
        
        if not orders:
            return "No recent orders found."
        
        # Format the orders as readable text
        orders_text = "Recent Orders (Last 7 days):\n\n"
        for order in orders:
            orders_text += f"""
            Order ID: {order.id}
            Symbol: {order.symbol}
            Type: {order.type}
            Side: {order.side}
            Qty: {order.qty}
            Status: {order.status}
            Created At: {order.created_at}
            -------------------------------------
            """
        
        return orders_text
    except Exception as e:
        logger.error(f"Error fetching recent orders: {e}")
        return f"Error fetching recent orders: {str(e)}"


# ========== TOOLS ==========

@mcp_server.tool()
async def place_market_order(symbol: str, side: str, qty: float) -> str:
    """
    Place a market order.
    
    Args:
        symbol: The stock symbol (e.g., AAPL, MSFT)
        side: 'buy' or 'sell'
        qty: Quantity of shares to trade
    
    Returns:
        Information about the submitted order
    """
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        # Validate input
        symbol = symbol.upper()
        side = side.lower()
        
        if side not in ['buy', 'sell']:
            return f"Error: Invalid side '{side}'. Must be 'buy' or 'sell'."
        
        if qty <= 0:
            return "Error: Quantity must be greater than 0."
        
        # Create the market order request
        order_details = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        
        # Submit the order
        order = trading_client.submit_order(order_details)
        
        # Return information about the submitted order
        return f"""
        Market Order Submitted:
        Order ID: {order.id}
        Symbol: {order.symbol}
        Side: {order.side}
        Qty: {order.qty}
        Type: {order.type}
        Status: {order.status}
        Submitted At: {order.submitted_at}
        """
    
    except Exception as e:
        logger.error(f"Error placing market order: {e}")
        return f"Error placing market order: {str(e)}"


@mcp_server.tool()
async def place_limit_order(symbol: str, side: str, qty: float, limit_price: float) -> str:
    """
    Place a limit order.
    
    Args:
        symbol: The stock symbol (e.g., AAPL, MSFT)
        side: 'buy' or 'sell'
        qty: Quantity of shares to trade
        limit_price: Limit price for the order
    
    Returns:
        Information about the submitted order
    """
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        # Validate input
        symbol = symbol.upper()
        side = side.lower()
        
        if side not in ['buy', 'sell']:
            return f"Error: Invalid side '{side}'. Must be 'buy' or 'sell'."
        
        if qty <= 0:
            return "Error: Quantity must be greater than 0."
        
        if limit_price <= 0:
            return "Error: Limit price must be greater than 0."
        
        # Create the limit order request
        order_details = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            limit_price=limit_price
        )
        
        # Submit the order
        order = trading_client.submit_order(order_details)
        
        # Return information about the submitted order
        return f"""
        Limit Order Submitted:
        Order ID: {order.id}
        Symbol: {order.symbol}
        Side: {order.side}
        Qty: {order.qty}
        Type: {order.type}
        Limit Price: ${order.limit_price}
        Status: {order.status}
        Submitted At: {order.submitted_at}
        """
    
    except Exception as e:
        logger.error(f"Error placing limit order: {e}")
        return f"Error placing limit order: {str(e)}"


@mcp_server.tool()
async def cancel_order(order_id: str) -> str:
    """
    Cancel an existing order.
    
    Args:
        order_id: The ID of the order to cancel
    
    Returns:
        Confirmation message
    """
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        # Attempt to cancel the order
        trading_client.cancel_order_by_id(order_id)
        
        return f"Order {order_id} cancelled successfully."
    
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        return f"Error cancelling order {order_id}: {str(e)}"


@mcp_server.tool()
async def get_portfolio_summary() -> str:
    """
    Get a summary of the current portfolio.
    
    Returns:
        Summary of account value, positions, and P/L
    """
    if not trading_client:
        return "Error: Trading client not initialized"
    
    try:
        # Get account information
        account = trading_client.get_account()
        
        # Get all positions
        positions = trading_client.get_all_positions()
        
        # Calculate total P/L
        total_pl = sum(float(pos.unrealized_pl) for pos in positions) if positions else 0
        
        # Generate portfolio summary
        summary = f"""
        Portfolio Summary:
        
        Account Value: ${account.portfolio_value}
        Cash Balance: ${account.cash}
        Buying Power: ${account.buying_power}
        
        Number of Positions: {len(positions)}
        Total Unrealized P/L: ${total_pl:.2f}
        
        Top Positions:
        """
        
        # Sort positions by market value and show top 5
        if positions:
            sorted_positions = sorted(positions, key=lambda p: float(p.market_value), reverse=True)
            top_positions = sorted_positions[:5]
            
            for pos in top_positions:
                summary += f"""
                {pos.symbol}: {pos.qty} shares @ ${pos.current_price}
                Market Value: ${pos.market_value}
                Unrealized P/L: ${pos.unrealized_pl} ({pos.unrealized_plpc}%)
                """
        else:
            summary += "\nNo open positions."
        
        return summary
    
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        return f"Error getting portfolio summary: {str(e)}"


# Main entry point
if __name__ == "__main__":
    try:
        # Start the MCP server
        mcp_server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")