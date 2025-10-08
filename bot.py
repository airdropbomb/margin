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

def close_position():
    """Existing BTCUSDT position ကို BTC settle နဲ့ ပိတ်ပါ"""
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
            side=client.SIDE_SELL,  # Long position ကို close လုပ်ဖို့ sell
            type=client.ORDER_TYPE_MARKET,
            quantity=round(free_btc, 6),
            isIsolated='TRUE',
            sideEffectType='AUTO_REPAY'  # Borrowed amount ကို repay
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
    # Step 2: Main Loop for Closing Positions
    for i in range(loops):
        print(f"\n--- Loop {i+1}/{loops} ---")
        
        # Close Position (BTC Settle)
        if not close_position():
            print("Position close မအောင်မြင်ပါ၊ loop ရပ်ပါမယ်")
            break
        
        if i < loops - 1:
            print(f"{sleep_time} စက္ကန့် စောင့်ပါမယ်...")
            try:
                time.sleep(sleep_time)
            except KeyboardInterrupt:
                print("KeyboardInterrupt: Script ကို ရပ်လိုက်ပါပြီ")
                break

print("အားလုံး ပြီးဆုံးပါပြီ!")
