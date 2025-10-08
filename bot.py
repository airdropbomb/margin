from binance.client import Client
from binance.exceptions import BinanceAPIException
import time

# API Key နဲ့ Secret (သင့်ဟာထည့်ပါ)
api_key = 'YOUR_API_KEY_HERE'
api_secret = 'YOUR_API_SECRET_HERE'
symbol = 'BTCUSDT'
usdt_amount = 0.0104  # USDT ပမာဏ
loops = 80  # အကြိမ်ရေ
sleep_time = 20  # စက္ကန့်စောင့်ချိန်

# Binance Client (Testnet အတွက် testnet=True ထည့်ပါ)
client = Client(api_key, api_secret)  # Testnet: client = Client(api_key, api_secret, testnet=True)

def transfer_to_isolated_margin():
    """Spot ကနေ Isolated Margin ထဲကို USDT 0.0104 လွှဲပါ"""
    try:
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

def get_current_price(symbol):
    """Current BTC price ယူပါ"""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        print(f"Price ယူရန် error: {e}")
        return None

def open_position():
    """Market Buy နဲ့ BTC ဝယ်ပါ (USDT 0.0104)"""
    try:
        price = get_current_price(symbol)
        if not price:
            return False
        quantity = round(usdt_amount / price, 6)  # BTC quantity တွက်ပါ
        if quantity <= 0:
            print("Quantity မမှန်ပါ")
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
        # Isolated Margin account မှာ BTC free amount ယူပါ
        account = client.get_isolated_margin_account(symbols=symbol)
        base_asset = next((asset for asset in account['assets'] if asset['baseAsset']['asset'] == 'BTC'), None)
        if not base_asset:
            print("BTC asset မတွေ့ပါ")
            return False
        free_btc = float(base_asset['baseAsset']['free'])
        if free_btc <= 0:
            print("Close လုပ်ဖို့ BTC မရှိပါ")
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
            time.sleep(sleep_time)

print("အားလုံး ပြီးဆုံးပါပြီ!")
