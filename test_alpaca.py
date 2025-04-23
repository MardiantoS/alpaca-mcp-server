"""
Test script for Alpaca Trading API

This script tests the functionality of the alpaca.py module
by calling each function and printing the results to stdout.

Before running:
1. Make sure alpaca.py is in the same directory
2. Install required packages: pip install python-dotenv alpaca-py
3. Create a .env file with your ALPACA_API_KEY and ALPACA_API_SECRET
4. Run: python test_alpaca.py
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import all components from alpaca.py
# This assumes alpaca.py is in the same directory
from alpaca_mcp_server import (
    trading_client, 
    data_client,
    get_account_info,
    get_all_positions,
    get_quote,
    get_bars,
    get_recent_orders,
    place_market_order,
    place_limit_order,
    cancel_order,
    get_portfolio_summary,
    alpaca_lifespan
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_all_functions():
    """
    Test all functions from alpaca.py
    """
    print("\n" + "="*50)
    print("ALPACA TRADING API TEST")
    print("="*50 + "\n")
    
    # Check if clients are initialized
    print("\n--- Checking if clients are initialized ---")
    print(f"Trading client initialized: {trading_client is not None}")
    print(f"Data client initialized: {data_client is not None}")
    
    if data_client is not None:
        print(f"Data client type: {type(data_client)}")
        print(f"Data client attributes: {dir(data_client)}")
    
    if trading_client is not None:
        print(f"Trading client type: {type(trading_client)}")
        print(f"Trading client attributes: {dir(trading_client)}")
    
    # Test get account info
    print("\n--- Testing get_account_info ---")
    try:
        account_info = await get_account_info()
        print(account_info)
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test get all positions
    print("\n--- Testing get_all_positions ---")
    try:
        positions = await get_all_positions()
        print(positions)
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test get quote
    print("\n--- Testing get_quote ---")
    try:
        quote = await get_quote("AAPL")  # Using Apple as an example
        print(quote)
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test get bars
    print("\n--- Testing get_bars ---")
    try:
        bars = await get_bars("MSFT")  # Using Microsoft as an example
        print(bars)
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test get recent orders
    print("\n--- Testing get_recent_orders ---")
    try:
        recent_orders = await get_recent_orders()
        print(recent_orders)
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test get portfolio summary
    print("\n--- Testing get_portfolio_summary ---")
    try:
        portfolio = await get_portfolio_summary()
        print(portfolio)
    except Exception as e:
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test place market order (uncomment to actually place orders)    
    print("\n--- Testing place_market_order ---")
    # Small order for testing: buy 1 share of a low-cost stock
    market_order = await place_market_order(
        symbol="F",  # Ford - typically a lower cost stock
        side="buy",
        qty=1
    )
    print(market_order)
    
    # Get the order ID from the response (this is just an example, actual parsing will depend on response format)
    try:
        order_id = market_order.strip().split("Order ID: ")[1].split("\n")[0].strip()
        
        # Test cancel order
        print("\n--- Testing cancel_order ---")
        cancel_response = await cancel_order(order_id)
        print(cancel_response)
    except:
        print("Could not extract order ID from response")    
    
    # Test place limit order (uncomment to actually place orders)    
    print("\n--- Testing place_limit_order ---")
    # Get current price first
    quote = await get_quote("F")
    # Set limit price 5% below current price
    try:
        current_price = float(quote.split("Bid Price: $")[1].split("\n")[0].strip())
        limit_price = current_price * 0.95
        
        # Place limit order
        limit_order = await place_limit_order(
            symbol="F",
            side="buy",
            qty=1,
            limit_price=limit_price
        )
        print(limit_order)
    except:
        print("Could not extract current price from quote")    
    
    print("\n" + "="*50)
    print("TEST COMPLETE")
    print("="*50 + "\n")

async def run_tests():
    """
    Run all tests with proper initialization and cleanup
    """
    # Create a dummy server context for the lifespan
    class DummyServer:
        pass
        
    dummy_server = DummyServer()
    
    # Use the alpaca_lifespan to properly initialize clients
    async with alpaca_lifespan(dummy_server):
        await test_all_functions()

if __name__ == "__main__":
    # Check if API credentials are set
    if not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_API_SECRET"):
        logger.error("Alpaca API credentials not found. Please check your .env file or set ALPACA_API_KEY and ALPACA_API_SECRET environment variables.")
        exit(1)
    
    # Run the test
    asyncio.run(run_tests())