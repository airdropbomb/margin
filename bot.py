from binance.client import Client
from binance.exceptions import BinanceAPIException
import time

# API Key နဲ့ Secret (သင့်ဟာထည့်ပါ)
api_key = 'YOUR_API_KEY_HERE'
api_secret = 'YOUR_API_SECRET_HERE'
symbol = 'BTCUSDT'
usdt_amount = 0.0104  # USDT ပမာဏ
loops = 80  # အကြိမ်ရေ
sleep_time = 10  # စက္ကန့်စောင့်ချိန်

# Binance Client (Testnet အတွက် testnet=True ထည့်ပါ)
client = Client(api_key, api_secret)  # Testnet: client = Client(api_key, api_secret, testnet=True)

def transfer_to_isolated_margin():
    """Spot ကနေ Isolated Margin ထဲကို USDT 0.0104 လွှဲပါ"""
    try:
        # Spot balance စစ်ပါ
        spot_balance = client.get_asset_balance(asset='USDT')
        free_usdt = float(spot_balance['free'])
        if free_usdt < usdt_amount:
            print(f"Spot wallet မှာ USDT မလုံလောက်ပါ: {free_usdt} USDT ရှိတယ်")
            return False
        
        transfer = client.transfer_spot_to_isolated_margin(
            asset='USDT',
            symbol=symbol,
            amount=usdt_amount
        )
        print(f"Transfer အောင်မြင်: {usdt_amount} USDT to Isolated Margin, Trans ID {transfer['tranId']}")
        return True
    except BinanceAPIException as e:
        print(f"Transfer error: {e}")
        return False

def get_current_price(symbol, retries=3):
    """Current BTC price ယူပါ (Retry logic ထည့်ထားတယ်)"""
    for attempt in range(retries):
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            print(f"Price ယူရန် error (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(2)
    print("Price ယူရန် မအောင်မြင်ပါ")
    return None

def get_min_quantity(symbol):
    """Symbol ရဲ့ minimum quantity ယူပါ"""
    try:
        info = client.get_symbol_info(symbol)
        for filter in info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                return float(filter['minQty'])
        return 0.0001  # Default fallback
    except Exception as e:
        print(f"Minimum quantity ယူရန် error: {e}")
        return 0.0001

def check_margin_balance():
    """Isolated Margin မှာ USDT balance စစ်ပါ"""
    try:
        account = client.get_isolated_margin_account(symbols=symbol)
        quote_asset = next((asset for asset in account['assets'] if asset['quoteAsset']['asset'] == 'USDT'), None)
        if not quote_asset:
            print("USDT asset မတွေ့ပါ")
            return 0
        free_usdt = float(quote_asset['quoteAsset']['free'])
        return free_usdt
    except Exception as e:
        print(f"Margin balance ယူရန် error: {e}")
        return 0

def open_position():
    """Market Buy နဲ့ BTC ဝယ်ပါ (USDT 0.0104)"""
    try:
        # Margin balance စစ်ပါ
        free_usdt = check_margin_balance()
        if free_usdt < usdt_amount:
            print(f"Isolated Margin မှာ USDT မလုံလောက်ပါ: {free_usdt} USDT ရှိတယ်")
            return False

        price = get_current_price(symbol)
        if not price:
            return False
        
        min_qty = get_min_quantity(symbol)
        quantity = round(usdt_amount / price, 6)  # BTC quantity တွက်ပါ
        if quantity < min_qty:
            print(f"Quantity သေးငယ်လွန်းပါတယ်: {quantity} BTC, Minimum: {min_qty} BTC")
            return False
        
        order = client.create_margin_order(
            symbol=symbol,
            side=client.SIDE_BUY,
            type=client.ORDER_TYPE_MARKET,
            quoteOrderQty=usdt_amount,  # USDT amount နဲ့ buy
            isIsolated='TRUE',
            sideEffectType='AUTO_BORROW'  # Borrow လုပ်ပါ
        )
        print(f"Open Order အောင်မြင်: Quantity {quantity} BTC, Order ID {order['orderId']}")
        return True
    except BinanceAPIException as e:
        print(f"Open order error: {e}")
        return False

def close_position():
    """Free BTC ကို Market Sell နဲ့ ပိတ်ပါ (BTC Settle)"""
    try:
        account = client.get_isolated_margin_account(symbols=symbol)
        base_asset = next((asset for asset in account['assets'] if asset['baseAsset']['asset'] == 'BTC'), None)
        if not base_asset:
            print("BTC asset မတွေ့ပါ")
            return False
        free_btc = float(base_asset['baseAsset']['free'])
        min_qty = get_min_quantity(symbol)
        if free_btc < min_qty:
            print(f"Close လုပ်ဖို့ BTC မလုံလောက်ပါ: {free_btc} BTC, Minimum: {min_qty} BTC")
            return False
        
        order = client.create_margin_order(
            symbol=symbol,
            side=client.SIDE_SELL,
            type=client.ORDER_TYPE_MARKET,
            quantity=round(free_btc, 6),  # Free BTC ကို sell
            isIsolated='TRUE',
            sideEffectType='AUTO_REPAY'  # Repay လုပ်ပါ
        )
        print(f"Close Order အောင်မြင်: Quantity {free_btc} BTC, Order ID {order['orderId']}")
        return True
    except BinanceAPIException as e:
        print(f"Close order error: {e}")
        return False

# Step 1: Spot to Isolated Margin Transfer (တစ်ကြိမ်တည်း)
if not transfer_to_isolated_margin():
    print("Transfer မအောင်မြင်ပါ၊ ရပ်လိုက်ပါမယ်")
else:
    # Step 2: Main Loop for Open and Close
    for i in range(loops):
        print(f"\n--- Loop {i+1}/{loops} ---")
        
        # Open Position
        if open_position():
            time.sleep(2)  # Order ပြီးဆုံးဖို့ စောင့်ပါ
            
            # Close Position (BTC Settle)
            close_position()
        
        if i < loops - 1:
            print(f"{sleep_time} စက္ကန့် စောင့်ပါမယ်...")
            try:
                time.sleep(sleep_time)
            except KeyboardInterrupt:
                print("KeyboardInterrupt: Script ကို ရပ်လိုက်ပါပြီ")
                break

print("အားလုံး ပြီးဆုံးပါပြီ!")
