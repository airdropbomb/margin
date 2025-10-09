from binance.client import Client
from binance.exceptions import BinanceAPIException
from decimal import Decimal
import os
from dotenv import load_dotenv
import time
import random

# Load environment variables
load_dotenv()

# Configuration
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
is_isolated = 'TRUE'

# Load TIME_REMAINING from .env, default to 25 if not set
TIME_REMAINING = int(os.getenv('TIME_REMAINING', '25'))

# Define pairs with correct symbols that exist on Binance
PAIRS = [
    'BTCUSDT', 'ETHBTC', 'LTCBTC', 'EURBTC', 'XRPBTC', 
    'ADABTC', 'BNBBTC', 'BCHBTC', 'XLMBTC', 'TRXBTC',
    'DOTBTC', 'ETCBTC', 'XMRBTC', 'ZECBTC', 'ZRXBTC'
]

# Dynamically load transfer amounts from .env for each pair
TRANSFER_AMOUNTS = {pair: Decimal(os.getenv(f'TRANSFER_AMOUNT_{pair}', '0.0104')) for pair in PAIRS}

# Debug print
print(f"API Key loaded: {'Yes' if api_key else 'No'}")
print(f"API Secret loaded: {'Yes' if api_secret else 'No'}")
if not api_key or not api_secret:
    raise ValueError("API Key or Secret is missing. Please check your .env file.")

# Initialize client
client = Client(api_key, api_secret, testnet=False)

def get_assets_from_symbol(symbol):
    """Extract base and quote assets from symbol"""
    # Common quote assets
    quote_assets = ['USDT', 'BTC', 'ETH', 'BNB', 'EUR', 'BUSD', 'USDC']
    
    for quote in quote_assets:
        if symbol.endswith(quote):
            base_asset = symbol[:-len(quote)]
            return base_asset, quote
    
    # Default fallback - assume last 3-4 characters are quote asset
    if len(symbol) > 3:
        return symbol[:-3], symbol[-3:]
    else:
        return symbol[:-2], symbol[-2:]

def get_display_name(symbol):
    """Get display name for symbol in BASE/QUOTE format"""
    base, quote = get_assets_from_symbol(symbol)
    return f"{base}/{quote}"

def get_transfer_asset_and_amount(symbol):
    """Determine which asset to transfer and the amount - FIXED FOR BNB/BTC"""
    base_asset, quote_asset = get_assets_from_symbol(symbol)
    amount = TRANSFER_AMOUNTS[symbol]
    
    # SPECIAL CASE: For BNB/BTC pair, we transfer BNB (base asset)
    if symbol == 'BNBBTC':
        return 'BNB', amount
    # For other BTC pairs, we transfer BTC (quote asset)
    elif quote_asset == 'BTC':
        return 'BTC', amount
    # For USDT pairs, we transfer USDT
    elif quote_asset == 'USDT':
        return 'USDT', amount
    else:
        # Default to quote asset
        return quote_asset, amount

def sync_server_time():
    server_time = client.get_server_time()
    local_time = int(time.time() * 1000)
    time_diff = server_time['serverTime'] - local_time
    print(f"ðŸ• [Sync] Server time difference: {time_diff}ms")

def ensure_isolated_account_enabled(symbol):
    try:
        display_name = get_display_name(symbol)
        print(f"ðŸ” [Setup] Enabling isolated margin account for {display_name}...")
        client.enable_isolated_margin_account(symbol=symbol)
        print(f"âœ… [Setup] Isolated margin account enabled for {display_name}.")
        time.sleep(2)
        return True
    except BinanceAPIException as e:
        if "already enabled" in str(e).lower() or e.code == -11001:
            print(f"â„¹ï¸ [Setup] Isolated margin account for {get_display_name(symbol)} already exists.")
            return True
        print(f"âŒ [Setup] Error enabling isolated account: {e}")
        return False

def transfer_spot_to_margin(symbol):
    """Transfer asset from spot to isolated margin - FIXED FOR BNB/BTC"""
    try:
        transfer_asset, amount = get_transfer_asset_and_amount(symbol)
        display_name = get_display_name(symbol)
        
        print(f"ðŸ”„ [Step 1] Transferring {amount} {transfer_asset} to Isolated Margin for {display_name}...")
        
        # Check spot balance for the transfer asset
        spot_balance = client.get_asset_balance(asset=transfer_asset)
        free_balance = Decimal(spot_balance['free'])
        print(f"ðŸ’° [Info] Spot {transfer_asset} Balance: {free_balance}")
        
        if free_balance < amount:
            print(f"âŒ [Error] Insufficient {transfer_asset}: {free_balance} < {amount}")
            return False
        
        transfer = client.transfer_spot_to_isolated_margin(
            asset=transfer_asset, symbol=symbol, amount=float(amount)
        )
        print(f"âœ… [Step 1] Transfer successful. Transaction ID: {transfer['tranId']}")
        return True
    except BinanceAPIException as e:
        print(f"âŒ [Error] Transfer failed for {get_display_name(symbol)}: {e}")
        return False

def wait_for_manual_close():
    """Wait for user to manually close position with single line progress"""
    print(f"â³ [Step 2] Waiting {TIME_REMAINING}s for manual position close...")
    print("ðŸ’¡ [Info] Please manually close the position in the Binance app.")
    print("â° [Progress] Time remaining: ", end="", flush=True)
    
    for i in range(TIME_REMAINING, 0, -1):
        print(f"\râ° [Progress] Time remaining: {i}s", end="", flush=True)
        time.sleep(1)
    
    print("\râœ… [Step 2] Wait completed" + " " * 20)
    print("ðŸ”„ [Check] Verifying manual close...")

def check_margin_account(symbol):
    """Check margin account status"""
    try:
        account = client.get_isolated_margin_account(symbols=symbol)
        if not account['assets']:
            print(f"âŒ [Error] No margin account found for {get_display_name(symbol)}")
            return None
            
        asset_info = account['assets'][0]
        base_asset_info = asset_info['baseAsset']
        quote_asset_info = asset_info['quoteAsset']
        
        base_asset, quote_asset = get_assets_from_symbol(symbol)
        
        base_free = Decimal(base_asset_info['free'])
        quote_free = Decimal(quote_asset_info['free'])
        base_borrowed = Decimal(base_asset_info['borrowed'])
        quote_borrowed = Decimal(quote_asset_info['borrowed'])
        
        print(f"ðŸ“Š [Status] Margin Account Details for {get_display_name(symbol)}:")
        print(f"   {base_asset} - Free: {base_free}, Borrowed: {base_borrowed}")
        print(f"   {quote_asset} - Free: {quote_free}, Borrowed: {quote_borrowed}")
        
        return {
            'base_asset': base_asset,
            'quote_asset': quote_asset,
            'base_free': base_free,
            'quote_free': quote_free,
            'base_borrowed': base_borrowed,
            'quote_borrowed': quote_borrowed
        }
        
    except Exception as e:
        print(f"âŒ [Error] Check margin account failed for {get_display_name(symbol)}: {e}")
        return None

def remove_margin_max_assets(symbol):
    """Remove all assets from margin account with MAX amounts - FIXED FOR DUST AMOUNTS"""
    try:
        display_name = get_display_name(symbol)
        print(f"ðŸ”„ [Step 5] Removing Margin with MAX assets for {display_name}...")
        
        account_info = check_margin_account(symbol)
        if not account_info:
            print(f"âœ… [Step 5] No margin account found for {display_name}")
            return True
            
        base_asset = account_info['base_asset']
        quote_asset = account_info['quote_asset']
        base_free = account_info['base_free']
        quote_free = account_info['quote_free']
        base_borrowed = account_info['base_borrowed']
        quote_borrowed = account_info['quote_borrowed']
        
        print(f"ðŸ“Š [Info] Assets available for removal for {display_name}:")
        print(f"   {base_asset} - Free: {base_free}, Borrowed: {base_borrowed}")
        print(f"   {quote_asset} - Free: {quote_free}, Borrowed: {quote_borrowed}")
        
        removed = False
        
        # Remove any borrowed assets first if exist
        if quote_borrowed > 0:
            print(f"ðŸ”„ [Action] Repaying borrowed {quote_asset}: {quote_borrowed}")
            client.repay_isolated_margin_loan(asset=quote_asset, symbol=symbol, amount=float(quote_borrowed))
            print(f"âœ… [Action] Borrowed {quote_asset} repaid: {quote_borrowed}")
            removed = True
            time.sleep(2)

        if base_borrowed > 0:
            print(f"ðŸ”„ [Action] Repaying borrowed {base_asset}: {base_borrowed}")
            client.repay_isolated_margin_loan(asset=base_asset, symbol=symbol, amount=float(base_borrowed))
            print(f"âœ… [Action] Borrowed {base_asset} repaid: {base_borrowed}")
            removed = True
            time.sleep(2)

        # Refresh account info after repaying loans
        account_info = check_margin_account(symbol)
        if account_info:
            base_free = account_info['base_free']
            quote_free = account_info['quote_free']

        # Remove MAX base asset - FORCE REMOVE even very small amounts
        if base_free > Decimal('0'):
            try:
                symbol_info = client.get_symbol_info(symbol)
                lot_size = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
                min_qty = Decimal(lot_size['minQty'])
                step_size = Decimal(lot_size['stepSize'])
                
                print(f"ðŸ”§ [Debug] {base_asset} - Free: {base_free}, MinQty: {min_qty}, StepSize: {step_size}")
                
                # Force remove even if below min quantity - try with adjusted amount
                if base_free > Decimal('0'):
                    # Try to remove the exact amount first
                    try:
                        print(f"ðŸ”„ [Action] Removing MAX {base_asset}: {base_free}")
                        transfer = client.transfer_isolated_margin_to_spot(
                            asset=base_asset, symbol=symbol, amount=float(base_free)
                        )
                        print(f"âœ… [Action] MAX {base_asset} removed. Transaction ID: {transfer['tranId']}")
                        removed = True
                    except BinanceAPIException as e:
                        if "too small" in str(e).lower():
                            print(f"âš ï¸ [Warning] Amount too small, trying with minimum quantity...")
                            # Try with minimum quantity if we have enough
                            if base_free >= min_qty:
                                transfer = client.transfer_isolated_margin_to_spot(
                                    asset=base_asset, symbol=symbol, amount=float(min_qty)
                                )
                                print(f"âœ… [Action] {base_asset} removed with min quantity. Transaction ID: {transfer['tranId']}")
                                removed = True
                            else:
                                print(f"â„¹ï¸ [Info] {base_asset} amount {base_free} is dust, leaving in margin account")
                        else:
                            raise e
                            
            except Exception as e:
                print(f"âš ï¸ [Warning] Error removing {base_asset}: {e}")

        # Remove quote asset - FORCE REMOVE even very small amounts
        if quote_free > Decimal('0'):
            try:
                print(f"ðŸ”„ [Action] Removing {quote_asset}: {quote_free}")
                transfer = client.transfer_isolated_margin_to_spot(
                    asset=quote_asset, symbol=symbol, amount=float(quote_free)
                )
                print(f"âœ… [Action] {quote_asset} removed. Transaction ID: {transfer['tranId']}")
                removed = True
            except BinanceAPIException as e:
                if "too small" in str(e).lower():
                    print(f"â„¹ï¸ [Info] {quote_asset} amount {quote_free} is dust, leaving in margin account")
                else:
                    print(f"âš ï¸ [Warning] Error removing {quote_asset}: {e}")
            
        if not removed:
            print(f"â„¹ï¸ [Info] No assets to remove or all removed as dust for {display_name}")
        else:
            print(f"âœ… [Step 5] All assets removed successfully for {display_name}")
            
        return True
        
    except BinanceAPIException as e:
        print(f"âŒ [Error] Remove margin failed for {get_display_name(symbol)}: {e}")
        return False

def wait_for_final_remove():
    """Wait before final remove with single line progress"""
    wait_time = random.randint(5, 10)
    print(f"â³ [Step 4] Waiting {wait_time}s before final remove: ", end="", flush=True)
    
    for i in range(wait_time, 0, -1):
        print(f"\râ³ [Step 4] Waiting {wait_time}s before final remove: {i}s", end="", flush=True)
        time.sleep(1)
    
    print("\râœ… [Step 4] Wait completed" + " " * 30)

def main():
    print("ðŸš€ [Start] Manual Close + Auto Remove Margin")
    print("=" * 60)
    print(f"ðŸ“‹ [Config] Wait Time: {TIME_REMAINING} seconds")
    print(f"ðŸ“‹ [Config] Total Pairs: {len(PAIRS)}")
    print("ðŸ“‹ [Workflow] Transfer â†’ Wait â†’ Manual Close â†’ Auto Remove (80 loops per selected pair)")
    print("=" * 60)

    # Display pair selection menu with clean formatting
    print("ðŸŽ¯ [Select Trading Pair]:")
    print("-" * 50)
    
    for i, pair in enumerate(PAIRS, 1):
        base_asset, quote_asset = get_assets_from_symbol(pair)
        amount = TRANSFER_AMOUNTS[pair]
        transfer_asset, _ = get_transfer_asset_and_amount(pair)
        display_name = get_display_name(pair)
        
        # Format the display nicely
        pair_display = f"[ {i:2d} ] {display_name:12}"
        amount_display = f"Transfer: {amount} {transfer_asset}"
        
        print(f"{pair_display} {amount_display}")
    
    print("-" * 50)
    print("[ xxx ] Exit")
    print("-" * 50)
    
    # Get user input for pair selection
    while True:
        choice = input("ðŸ”¢ [Input] Enter pair number or 'xxx' to exit: ").strip()
        if choice == 'xxx':
            print("ðŸ›‘ [Info] Script terminated by user")
            return
        try:
            choice = int(choice)
            if 1 <= choice <= len(PAIRS):
                selected_pair = PAIRS[choice - 1]
                amount = TRANSFER_AMOUNTS[selected_pair]
                base_asset, quote_asset = get_assets_from_symbol(selected_pair)
                transfer_asset, _ = get_transfer_asset_and_amount(selected_pair)
                display_name = get_display_name(selected_pair)
                
                print(f"\nðŸŽ¯ [Selected] {display_name}")
                print(f"ðŸ’° [Transfer] {amount} {transfer_asset} from Spot to Isolated Margin")
                print(f"ðŸ”„ [Loops] 80 cycles")
                print("-" * 40)
                break
            else:
                print(f"âŒ [Error] Please enter a number between 1 and {len(PAIRS)}")
        except ValueError:
            print("âŒ [Error] Please enter a valid number or 'xxx' to exit")

    # Process the selected pair 80 times
    for loop in range(1, 81):  # 80 loops
        display_name = get_display_name(selected_pair)
        transfer_asset, amount = get_transfer_asset_and_amount(selected_pair)
        
        print(f"\nðŸ”„ [Loop {loop}/80] Processing {display_name}")
        print("-" * 40)
        
        # Initial setup
        sync_server_time()
        ensure_isolated_account_enabled(selected_pair)
        
        # Step 1: Transfer asset to Margin
        print(f"\nðŸ“¥ [Step 1] Transfer {transfer_asset} to Margin")
        if not transfer_spot_to_margin(selected_pair):
            print(f"âŒ [Error] Transfer failed, skipping loop {loop}")
            continue

        # Step 2: Wait for manual close
        print(f"\nâ³ [Step 2] Manual Close Wait")
        wait_for_manual_close()

        # Step 3: Check account status after manual close
        print(f"\nðŸ“Š [Step 3] Account Status Check")
        account_status = check_margin_account(selected_pair)
        
        if account_status:
            base_asset = account_status['base_asset']
            quote_asset = account_status['quote_asset']
            
            print(f"ðŸ“ˆ [Position] {display_name}:")
            print(f"   {base_asset} Available: {account_status['base_free']}")
            print(f"   {quote_asset} Available: {account_status['quote_free']}")
            print(f"   {base_asset} Borrowed: {account_status['base_borrowed']}")
            print(f"   {quote_asset} Borrowed: {account_status['quote_borrowed']}")
            
            if account_status['base_borrowed'] > 0 or account_status['quote_borrowed'] > 0:
                print(f"âš ï¸ [Warning] Borrowed funds remain!")
                response = input(f"Continue with remove margin? (y/n): ")
                if response.lower() != 'y':
                    print(f"ðŸ›‘ [Info] Skipping remove margin in loop {loop}")
                    continue

        # Step 4: Wait a bit before remove
        print(f"\nâ³ [Step 4] Final Preparation")
        wait_for_final_remove()

        # Step 5: Remove Margin with MAX assets
        print(f"\nðŸ“¤ [Step 5] Remove Margin Assets")
        if remove_margin_max_assets(selected_pair):
            print(f"âœ… [Success] Remove margin completed")
        else:
            print(f"âŒ [Error] Remove margin failed")

        # Final status check
        print(f"\nâœ… [Loop {loop} Complete] {display_name}")
        final_status = check_margin_account(selected_pair)
        if final_status:
            base_asset = final_status['base_asset']
            quote_asset = final_status['quote_asset']
            print(f"   Final {base_asset}: {final_status['base_free']}")
            print(f"   Final {quote_asset}: {final_status['quote_free']}")

    print(f"\nðŸŽ‰ [Mission Complete] All 80 loops finished for {get_display_name(selected_pair)}!")
    print("=" * 60)

if __name__ == "__main__":
    main()
