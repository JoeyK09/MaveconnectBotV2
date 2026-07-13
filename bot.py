import random
import os
import time
import requests
import feedparser
from keyboards import main_menu
from games_keyboard import games_menu
from kamikaze_game import register_kamikaze_handlers
from games import register_game_handlers
from staking import register_staking_handlers
from predictions import register_prediction_handlers
from collectibles import register_collectible_handlers, maybe_drop_collectible
from admin import register_admin_handlers
from vip_keyboards import (
    vip_menu,
    vip_plans_keyboard,
    payment_keyboard
)
from database import get_vip_info
from telebot import types
from datetime import datetime
from datetime import datetime, timedelta
from database import update_deposit_status
from database import update_deposit_status
from database import txid_exists
from database import get_pending_deposits
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from database import get_pending_deposits
from database import add_deposit
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from database import get_pending_withdrawals
from database import add_withdrawal
from database import create_deposit
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from database import get_mining_bonus
from config import PICKAXES
from database import has_achievement, unlock_achievement
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta
from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from flask import Flask
from threading import Thread
from database import (
    conn,
    cursor,
    get_balance,
    add_plats,
    remove_plats,
    get_profile,
    update_mine,
    update_pickaxe,
    update_daily,
    add_win,
    leaderboard,
    add_favorite,
    get_favorites,
    add_alert,
    get_alerts,
    delete_alert
)
from database import create_deposit
from database import is_vip as db_is_vip
from database import activate_vip as activate_vip_admin
from database import remove_vip as remove_vip_admin
from database import get_total_vip as get_total_vip_admin
from database import approve_deposit, reject_deposit
from database import register_new_user, get_referrer, get_referral_count, count_approved_deposits
from database import get_users_needing_daily_reminder, mark_reminder_sent
from database import get_newly_matured_stakes, mark_stake_notified
from database import approve_withdrawal, reject_withdrawal
from admin_keyboards import admin_menu
from stk import stk_push
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from vip import register_vip_handlers
import telebot
import os
import requests
from vip import register_vip_handlers

# ========= TRONGRID API KEY ===========

TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY")

USDT_TRC20_ADDRESS = "TCHtvSHZgSzKAg85GzJoVgxBTUUauxYGna"
USDT_TRC20_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"

def verify_trc20_tx(txid, expected_amount):
    headers = {
        "TRON-PRO-API-KEY": TRONGRID_API_KEY
    }

    try:
        r = requests.get(
            f"https://api.trongrid.io/v1/transactions/{txid}/events",
            headers=headers,
            timeout=20
        )
    except requests.RequestException:
        return False, "⚠️ Could not reach the blockchain right now. Please try again shortly."

    if r.status_code != 200:
        return False, "Unable to verify transaction."

    data = r.json().get("data", [])

    if not data:
        return False, "Transaction not found. If you just sent it, wait a minute and try again."

    matching_event = None

    for event in data:

        # Must be a Transfer event on the real USDT TRC20 contract
        # (not just any token sent to a similar-looking event).
        if event.get("event_name") != "Transfer":
            continue

        if event.get("contract_address") != USDT_TRC20_CONTRACT:
            continue

        result = event.get("result", {})

        if result.get("to") == USDT_TRC20_ADDRESS:
            matching_event = event
            break

    if not matching_event:
        return False, "❌ No USDT transfer to the MaveConnect wallet was found in this transaction."

    result = matching_event.get("result", {})

    try:
        amount = float(result.get("value")) / 1_000_000
    except (TypeError, ValueError):
        return False, "❌ Could not read the transferred amount."

    if abs(amount - expected_amount) > 0.000001:
        return False, f"Amount mismatch.\nExpected {expected_amount} USDT\nReceived {amount} USDT"

    # Confirmations = current chain tip - the block this tx was included in.
    block_number = matching_event.get("block_number")
    current_block = None

    try:
        block_r = requests.get(
            "https://api.trongrid.io/wallet/getnowblock",
            headers=headers,
            timeout=20
        )
        current_block = (
            block_r.json()
            .get("block_header", {})
            .get("raw_data", {})
            .get("number")
        )
    except requests.RequestException:
        pass

    if block_number and current_block:
        confirmations = current_block - block_number

        if confirmations < 19:
            return False, f"⏳ Waiting for confirmations ({max(confirmations, 0)}/19). Please try again shortly."

    return True, "Verified"


# ================= BOT =================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("BOT_TOKEN not found")

bot = telebot.TeleBot(TOKEN, threaded=True)
print("Telegram bot initialized")

register_vip_handlers(bot)

register_admin_handlers(bot)

register_game_handlers(bot)
register_staking_handlers(bot)
register_prediction_handlers(bot)
register_collectible_handlers(bot)


app = Flask(__name__)
register_kamikaze_handlers(bot, app, get_balance, add_plats, remove_plats)

# ================= GROUPS =================

FREE_GROUP = "https://t.me/UltimateAvian"
VIP_GROUP = "https://t.me/UltimateAve"
VIP_CHANNEL = "@UltimateAve"

# ================= COINS =================

COINS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "bnb": "binancecoin",
    "sol": "solana",
    "xrp": "ripple",
    "ada": "cardano",
    "doge": "dogecoin",
    "matic": "matic-network",
    "dot": "polkadot",
    "ltc": "litecoin",
    "trx": "tron",
    "avax": "avalanche-2",
    "shib": "shiba-inu",
    "link": "chainlink"
}

PRICE_BUTTONS = {

    "₿ BTC":"btc",
    "Ξ ETH":"eth",
    "🟡 BNB":"bnb",
    "☀️ SOL":"sol",
    "💧 XRP":"xrp",
    "🔵 ADA":"ada",
    
    "🔷 DOT":"dot",
    "⚡ LTC":"ltc",
    "🔺 TRX":"trx",
    "🏔 AVAX":"avax",
    "🔗 LINK":"link",

    "🧠 FET":"fet",
    "⚡ TAO":"tao",
    "🤖 ICP":"icp",
    "🔷 RENDER":"render",
    "🛰 AKT":"akt",
    "💎 GRT":"grt",

    "🐕 DOGE": "doge",
    "🐶 SHIB": "shib",
    "🐸 PEPE": "pepe",
    "🐕 FLOKI": "floki",
    "🦴 BONK": "bonk",
    "🐶 WIF": "wif",
    "🍞 BRETT": "brett",
    # ================= DEFI =================

    "🦄 UNI": "uni",
    "👻 AAVE": "aave",
    "🏦 MKR": "mkr",
    "📈 CRV": "crv",
    "🥞 CAKE": "cake",
    "🍣 SUSHI": "sushi",
    "🔀 1INCH": "1inch",
    "💧 LDO": "ldo",

    # ================= LAYER 1 =================

    "🌌 ATOM": "atom",
    "🌐 NEAR": "near",
    "🚀 APT": "apt",
    "💧 SUI": "sui",
    "💎 TON": "ton",
    "⚫ HBAR": "hbar",
    "⚡ KAS": "kas",
    "🦅 EGLD": "egld",
    "🔷 ALGO": "algo",
    "✔️ VET": "vet",

    # ================= RWA =================

    "💎 ONDO": "ondo",
    "🕉 OM": "om",
    "⏳ PENDLE": "pendle",
    
}

NEWS_NAMES = {
    "btc": "Bitcoin",
    "eth": "Ethereum",
    "bnb": "BNB",
    "xrp": "XRP",
    "sol": "Solana",
    "doge": "Dogecoin",
    "ada": "Cardano",
    "trx": "Tron"
}

DASHBOARD_BUTTONS = [
    "🏦 DeFi",
    "⚡ Layer 1",
    "💎 RWA",
    "🎮 Games",
    "🔎 Coin Search",
    "⭐ Favorites",
    "🏠 Home"
]

CRYPTOS = {
    "₿ Bitcoin": ("BTC", "Bitcoin"),
    "Ξ Ethereum": ("ETH", "ERC20"),
    "🔴 USDT TRC20": ("USDT", "TRC20"),
    "🟡 USDT BEP20": ("USDT", "BEP20"),
    "🔵 USDT ERC20": ("USDT", "ERC20"),
}

# ================= CACHE =================

price_cache = {}
CACHE_TIME = 30
vip_users = set()
search_users = set()
current_coin = {}
alert_users = set()
waiting_alert = {}
user_last_coin = {}
deposit_amount = {}
user_withdraw_amount = {}
ADMIN_ID = 6384391560

# ================= DAILY VIP GROUP INSIGHTS =================
# Set this to your VIP group's chat ID to enable automatic daily posts
# there. This is deliberately separate from your general/free group —
# insights only go to VIP.
# How to find the chat ID: add the bot to your VIP group as admin, send
# any message in that group, then visit
# https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates in a browser and
# look for "chat":{"id": -100XXXXXXXXXX, ...} in the response — that
# negative number is your VIP_GROUP_CHAT_ID.
VIP_GROUP_CHAT_ID = None  # e.g. -1001234567890

DAILY_INSIGHT_COINS = ["btc", "eth", "bnb", "sol", "xrp"]
DAILY_INSIGHT_HOUR = 5  # 24h format, SERVER time. Render runs UTC, so 5 = 8am Nairobi (EAT, UTC+3)
pending_deposit = {}
buy_plats_state = {}
pending_withdrawal = {}
BINANCE_REFERRAL = "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_005LWI9SEA"
OKX_REFERRAL = "https://okx.com/join/60241030"
COINBASE_REFERRAL = "https://base.app/invite/friends/J6DN4LND"
BYBIT_REFERRAL = "https://www.bybit.com/invite?ref=MNXP6M3&medium=referral&utm_campaign=evergreen"
pending_crypto_withdraw = {}
mpesa_waiting = {}
coinflip_bets = {}

# ============== PICKAXE PRICES ================

PICKAXES = {
    1: {
        "name": "Wood",
        "price": 0,
        "bonus": 0,
        "cooldown": 3600
    },
    2: {
        "name": "Stone",
        "price": 500,
        "bonus": 5,
        "cooldown": 3300
    },
    3: {
        "name": "Bronze",
        "price": 2000,
        "bonus": 10,
        "cooldown": 3000
    },
    4: {
        "name": "Iron",
        "price": 5000,
        "bonus": 20,
        "cooldown": 2700
    },
    5: {
        "name": "Gold",
        "price": 10000,
        "bonus": 35,
        "cooldown": 2400
    },
    6: {
        "name": "Diamond",
        "price": 25000,
        "bonus": 50,
        "cooldown": 1800
    }
}

PICKAXE_BUTTONS = {
    "🪨 Stone Pickaxe": 2,
    "🥉 Bronze Pickaxe": 3,
    "⛓ Iron Pickaxe": 4,
    "🥇 Gold Pickaxe": 5,
    "💎 Diamond Pickaxe": 6,
}

@bot.message_handler(func=lambda m: m.text in PICKAXE_BUTTONS)
def buy_pickaxe(msg):

    user = str(msg.from_user.id)

    level = PICKAXE_BUTTONS[msg.text]

    balance, xp, user_level, current_pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    # Already owns this or a better pickaxe
    if level <= current_pickaxe:
        bot.reply_to(
            msg,
            "⚒️ You already own this pickaxe or a better one.",
            reply_markup=upgrade_menu()
        )
        return

    pickaxe = PICKAXES[level]
    price = pickaxe["price"]

    # Not enough PLATS
    if balance < price:
        bot.reply_to(
            msg,
            f"❌ Not enough PLATS!\n\n"
            f"💵 Cost: {price:,} PLATS\n"
            f"💰 Balance: {balance:,} PLATS",
            reply_markup=upgrade_menu()
        )
        return

    balance -= price

    update_pickaxe(user, balance, level)

    bot.reply_to(
        msg,
        f"🎉 Upgrade Successful!\n\n"
        f"⚒️ New Pickaxe: {pickaxe['name']}\n"
        f"💰 Mining Reward: {pickaxe['min']} - {pickaxe['max']} PLATS\n"
        f"⏳ Cooldown: {pickaxe['cooldown']//60} minutes\n\n"
        f"💳 Remaining Balance: {balance:,} PLATS",
        reply_markup=mine_menu()
    )
    
# ================= COINPAPRIKA IDS =================

COINPAPRIKA_IDS = {

    # Top Coins
    "btc": "btc-bitcoin",
    "eth": "eth-ethereum",
    "bnb": "bnb-binance-coin",
    "sol": "sol-solana",
    "xrp": "xrp-xrp",
    "ada": "ada-cardano",
    "trx": "trx-tron",
    "avax": "avax-avalanche",
    "dot": "dot-polkadot",
    "link": "link-chainlink",
    "ltc": "ltc-litecoin",
    "bch": "bch-bitcoin-cash",
    "etc": "etc-ethereum-classic",
    "xlm": "xlm-stellar",
    "atom": "atom-cosmos",
    "near": "near-near-protocol",
    "algo": "algo-algorand",
    "vet": "vet-vechain",
    "fil": "fil-filecoin",
    "icp": "icp-internet-computer",
    "apt": "apt-aptos",
    "sui": "sui-sui",
    "ton": "ton-toncoin",
    "hbar": "hbar-hedera",
    "kas": "kas-kaspa",
    "cro": "cro-cronos",
    "qnt": "qnt-quant",
    "egld": "egld-multiversx",
    "xtz": "xtz-tezos",

    # DeFi
    "uni": "uni-uniswap",
    "aave": "aave-aave",
    "comp": "comp-compound",
    "crv": "crv-curve-dao-token",
    "mkr": "mkr-maker",
    "snx": "snx-synthetix",
    "cake": "cake-pancakeswap",
    "sushi": "sushi-sushiswap",
    "1inch": "1inch-1inch",
    "ldo": "ldo-lido-dao",

    # AI
    "fet": "fet-artificial-superintelligence-alliance",
    "tao": "tao-bittensor",
    "grt": "grt-the-graph",
    "render": "render-render",
    "akt": "akt-akash-network",
    "oas": "oas-oasys",

    # Meme
    "doge": "doge-dogecoin",
    "shib": "shib-shiba-inu",
    "pepe": "pepe-pepe",
    "floki": "floki-floki",
    "bonk": "bonk-bonk",
    "wif": "wif-dogwifcoin",
    "brett": "brett-brett",

    # Layer 2
    "arb": "arb-arbitrum",
    "op": "op-optimism",
    "imx": "imx-immutable-x",
    "zk": "zk-zksync",
    "strk": "strk-starknet",

    # Gaming
    "sand": "sand-the-sandbox",
    "mana": "mana-decentraland",
    "axs": "axs-axie-infinity",
    "gala": "gala-gala",
    "enj": "enj-enjin-coin",

    # RWA
    "ondo": "ondo-ondo-finance",
    "pendle": "pendle-pendle",
    "om": "om-mantra",

    # Privacy
    "xmr": "xmr-monero",
    "zec": "zec-zcash",

    # Storage
    "ar": "ar-arweave",
    "storj": "storj-storj",
    "sc": "sc-siacoin",

    # Oracle
    "band": "band-band-protocol",
    "api3": "api3-api3",

    # Exchange
    "okb": "okb-okb",
    "leo": "leo-unus-sed-leo",
    "bgb": "bgb-bitget-token",

    # Stablecoins
    "usdt": "usdt-tether",
    "usdc": "usdc-usd-coin",
    "dai": "dai-dai"
}

PICKAXES = {
    1: {"name":"🪵 Wooden","min":10,"max":30,"cooldown":1800,"price":0},
    2: {"name":"🪨 Stone","min":20,"max":45,"cooldown":1680,"price":500},
    3: {"name":"🥉 Bronze","min":30,"max":55,"cooldown":1560,"price":2000},
    4: {"name":"⛓ Iron","min":40,"max":70,"cooldown":1440,"price":5000},
    5: {"name":"🥇 Gold","min":60,"max":95,"cooldown":1320,"price":10000},
    6: {"name":"💎 Diamond","min":80,"max":120,"cooldown":1200,"price":25000},
}

def get_coin_id(symbol):
    if not symbol:
        return None
    return COINPAPRIKA_IDS.get(symbol.lower().strip())

def get_coin_data(symbol):
    coin_id = get_coin_id(symbol)

    if not coin_id:
        return None

    try:
        url = f"https://api.coinpaprika.com/v1/tickers/{coin_id}"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()
        usd = data["quotes"]["USD"]

        return {
            "id": coin_id,
            "symbol": data["symbol"],
            "name": data["name"],
            "rank": data["rank"],
            "price": usd["price"],
            "change24": usd["percent_change_24h"],
            "market_cap": usd["market_cap"],
            "volume": usd["volume_24h"]
        }

    except Exception as e:
        print(f"CoinPaprika Error: {e}")
        return None
        
def safe_get_price(symbol):
    data = get_coin_data(symbol)

    if data:
        return data["price"]

    return None

def scan_coin(symbol):
    print(f"[SCAN] {symbol}")

    data = get_coin_data(symbol)

    if not data:
        print("[SCAN] get_coin_data failed")
        return None

    print("[SCAN] get_coin_data OK")

    history = get_history(symbol)
    
    if history is not None:
        print(history.tail())

    if history is None:
        print("[SCAN] history is None")
    elif history.empty:
        print("[SCAN] history is empty")
    else:
        print(f"[SCAN] history rows: {len(history)}")

    analysis = ai_analysis(symbol)

    if not analysis:
        print("[SCAN] ai_analysis failed")
        return None

    print("[SCAN] ai_analysis OK")

    return {
        "coin": data["name"],
        "symbol": data["symbol"],
        "price": data["price"],
        "change24": data["change24"],
        "rank": data["rank"],
        "market_cap": data["market_cap"],
        "volume": data["volume"],
        "rsi": "N/A",
        "signal": analysis["signal"],
        "strength": analysis["strength"],
        "trend": analysis["trend"],
        "support": analysis["support"],
        "resistance": analysis["resistance"]
    }

def get_price(symbol):
    return safe_get_price(symbol)

    now = time.time()

    # cache
    if coin in price_cache:
        price, timestamp = price_cache[coin]
        if now - timestamp < CACHE_TIME:
            return price

    # resolve coin ID
    coin_id = resolve_coin(coin)

    print(f"[COIN INPUT] {symbol} → {coin_id}")
    
    if not coin_id:
        print(f"[COIN NOT FOUND] {coin}")
        return None

    try:
        url = f"https://api.coinpaprika.com/v1/tickers/{coin_id}"
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print(f"[API ERROR] {coin} -> {r.status_code}")
            return None

        data = r.json()
        price = float(data["quotes"]["USD"]["price"])

        price_cache[coin] = (price, now)

        return price

    except Exception as e:
        print("[ERROR]", repr(e))
        return None
        
# ================== SIGNAL ENGINE =================

def get_signal(coin):

    data = get_coin_data(coin)

    if data is None:
        return None

    price = data["price"]
    change24 = data["change24"]

    score = 50
    support = round(price * 0.97, 4)
    resistance = round(price * 1.03, 4)

    try:
        history = get_history(coin, days=60)

        if history is not None and not history.empty and len(history) >= 20 and "close" in history.columns:

            closes = history["close"].astype(float)

            # RSI(14) — oversold/overbought
            rsi = calculate_rsi(history)

            if rsi is not None:
                if rsi < 30:
                    score += 20  # oversold — leans bullish
                elif rsi > 70:
                    score -= 20  # overbought — leans bearish

            # EMA20/50 trend direction
            trend = calculate_trend(history)

            if trend == "Bullish":
                score += 15
            else:
                score -= 15

            # Real support/resistance from actual recent price action,
            # not an arbitrary flat percentage
            recent = closes.tail(30)
            support = round(float(recent.min()), 4)
            resistance = round(float(recent.max()), 4)

    except Exception as e:
        print(f"[SIGNAL] history/indicator error for {coin}: {e}")
        # falls back to the 24h-change-only scoring below

    # 24h momentum still nudges the score even when history succeeded,
    # and is the ONLY signal when history/indicators aren't available.
    if change24 > 5:
        score += 15
    elif change24 < -5:
        score -= 15

    score = max(0, min(100, round(score)))

    if score >= 65:
        action = "🟢 BUY"
    elif score <= 35:
        action = "🔴 SELL"
    else:
        action = "⚪ HOLD"

    return {
        "price": price,
        "change": change24,
        "score": score,
        "action": action,
        "support": support,
        "resistance": resistance
    }

    
def is_vip(user_id):

    # Real, persistent VIP status from an approved payment.
    if db_is_vip(user_id):
        return True

    # Fallback: manually-granted VIP (admin commands) or someone who
    # already joined the VIP Telegram channel directly.
    if user_id in vip_users:
        return True

    try:
        member = bot.get_chat_member(VIP_CHANNEL, user_id)

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception as e:
        print("VIP check error:", e)
        return False

def vip_menu():

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row("📋 View Plans")

    markup.row("📅 My Subscription", "🎁 VIP Benefits")

    markup.row("👥 VIP Channel", "📜 Payment History")

    markup.row("🔄 Renew VIP")

    markup.row("🔙 Back")

    return markup

# ==================== AI ANALYSIS ==============

def ai_analysis(symbol):
    price = safe_get_price(symbol)

    if price is None:
        return {
            "signal": "UNKNOWN",
            "strength": 0,
            "trend": "Unknown",
            "support": 0,
            "resistance": 0
        }

    data = get_coin_data(symbol)
    change = data["change24"]

    if change > 5:
        signal = "🟢 BUY"
        trend = "Bullish"
        strength = 85
    elif change < -5:
        signal = "🔴 SELL"
        trend = "Bearish"
        strength = 80
    else:
        signal = "⚪ HOLD"
        trend = "Sideways"
        strength = 65

    return {
        "signal": signal,
        "strength": strength,
        "trend": trend,
        "support": round(price * 0.97, 4),
        "resistance": round(price * 1.03, 4)
    }
    
# ================= CRYPTO NEWS =================

def get_crypto_news(coin):
    try:
        feed = feedparser.parse(
            "https://www.coindesk.com/arc/outboundfeeds/rss/"
        )

        articles = []

        coin = coin.upper()

        for entry in feed.entries:
            title = entry.title

            if coin in title.upper():
                articles.append({
                    "title": title,
                    "url": entry.link
                })

            if len(articles) == 5:
                break

        return articles

    except Exception as e:
        print("News Error:", e)
        return None
        
def calculate_rsi(df):

    rsi = RSIIndicator(df["close"]).rsi()

    return float(rsi.iloc[-1])

def calculate_trend(df):

    ema20 = EMAIndicator(df["close"], window=20).ema_indicator()

    ema50 = EMAIndicator(df["close"], window=50).ema_indicator()

    if ema20.iloc[-1] > ema50.iloc[-1]:
        return "Bullish"

    return "Bearish"

# ===================== MPESA =================

def get_mpesa_amount(message):
    if not message.text.isdigit():
        msg = bot.send_message(
            message.chat.id,
            "❌ Please enter numbers only."
        )
        bot.register_next_step_handler(msg, get_mpesa_amount)
        return

    deposit_amount[message.from_user.id] = int(message.text)

    msg = bot.send_message(
        message.chat.id,
        "📱 Enter your M-Pesa phone number.\n\nExample: 254142047838"
    )

    bot.register_next_step_handler(msg, get_mpesa_phone)

def get_mpesa_phone(message):
    user = str(message.from_user.id)

    amount = deposit_amount.get(message.from_user.id)
    phone = message.text.strip()

    create_deposit(user, amount, "M-Pesa")

    bot.send_message(
        message.chat.id,
        f"""✅ Deposit request created!

💰 Amount: KES {amount}
📱 Phone: {phone}

⏳ Your payment request has been recorded.
You'll receive an M-Pesa prompt once payment integration is enabled."""
    )

    deposit_amount.pop(message.from_user.id, None)

user_withdraw_amount = {}

def process_mpesa_amount(message):
    user = str(message.from_user.id)

    try:
        amount = int(message.text)

    except:
        bot.reply_to(message, "❌ Enter a valid number.")
        return

    balance = get_balance(user)

    if amount < 500:
        bot.reply_to(
            message,
            "❌ Minimum withdrawal is 500 Plats."
        )
        return

    if balance < amount:
        bot.reply_to(
            message,
            "❌ Insufficient balance."
        )
        return

    # Save amount temporarily
    user_withdraw_amount[user] = amount
    
    msg = bot.send_message(
        message.chat.id,
        """📱 Enter your M-Pesa phone number.

Example:
0712345678"""
    )

    bot.register_next_step_handler(
        msg,
        process_mpesa_number
    )

def process_mpesa_number(message):
    user = str(message.from_user.id)

    phone = message.text.strip()

    if not phone.isdigit() or len(phone) != 10:
        bot.reply_to(
            message,
            "❌ Invalid phone number."
        )
        return

    amount = user_withdraw_amount.get(user)

    if not add_withdrawal(user, amount, phone):
        bot.reply_to(message, "❌ Insufficient balance.")
        del user_withdraw_amount[user]
        return

    add_transaction(
    user,
    "Withdrawal",
    amount,
    "M-Pesa withdrawal"
    )

    pending_rows = get_pending_withdrawals()
    matching = [r for r in pending_rows if str(r[1]) == user and r[3] == phone]
    withdrawal_id = matching[-1][0] if matching else None

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if withdrawal_id:
        markup.row(
            types.KeyboardButton(f"✅ Approve Withdrawal #{withdrawal_id}"),
            types.KeyboardButton(f"❌ Reject Withdrawal #{withdrawal_id}")
        )

    bot.send_message(
    ADMIN_ID,
    f"""💸 New Withdrawal Request

👤 User: {user}
💰 Amount: {amount:,} Plats
📱 Phone: {phone}

Status: Pending""",
    reply_markup=markup
    )

    bot.send_message(
        message.chat.id,
        f"""✅ Withdrawal Request Received

💰 Amount: {amount:,} Plats
📱 Phone: {phone}

⏳ Your request has been submitted for review.
You will receive your payment once it is approved."""
    )

    del user_withdraw_amount[user]


@bot.message_handler(func=lambda m: m.text.startswith("✅ Approve Withdrawal #"))
def approve_withdrawal_callback(message):

    if message.from_user.id != ADMIN_ID:
        return

    withdrawal_id = message.text.replace("✅ Approve Withdrawal #", "").strip()
    result = approve_withdrawal(withdrawal_id)

    if not result:
        bot.send_message(message.chat.id, "❌ Withdrawal not found or already processed.", reply_markup=admin_menu())
        return

    user_id, amount = result

    bot.send_message(message.chat.id, f"✅ Withdrawal #{withdrawal_id} marked paid.", reply_markup=admin_menu())

    try:
        bot.send_message(
            int(user_id),
            f"✅ Your withdrawal of {amount:,} Plats has been paid out. Thank you for using MaveConnect!"
        )
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text.startswith("❌ Reject Withdrawal #"))
def reject_withdrawal_callback(message):

    if message.from_user.id != ADMIN_ID:
        return

    withdrawal_id = message.text.replace("❌ Reject Withdrawal #", "").strip()
    result = reject_withdrawal(withdrawal_id)

    if not result:
        bot.send_message(message.chat.id, "❌ Withdrawal not found or already processed.", reply_markup=admin_menu())
        return

    user_id, amount = result

    bot.send_message(message.chat.id, f"❌ Withdrawal #{withdrawal_id} rejected, {amount:,} Plats refunded to user.", reply_markup=admin_menu())

    try:
        bot.send_message(
            int(user_id),
            f"❌ Your withdrawal request was rejected and {amount:,} Plats has been refunded to your balance."
        )
    except Exception:
        pass

@bot.message_handler(commands=["withdrawals"])
def withdrawals(message):

    if message.from_user.id != ADMIN_ID:
        return

    rows = get_pending_withdrawals()

    if not rows:
        bot.reply_to(message, "✅ No pending withdrawals.")
        return

    for wid, user, amount, phone in rows:

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(
            types.KeyboardButton(f"✅ Approve Withdrawal #{wid}"),
            types.KeyboardButton(f"❌ Reject Withdrawal #{wid}")
        )

        bot.send_message(
            message.chat.id,
            f"""💸 Pending Withdrawal

ID: {wid}
User: {user}
Amount: {amount:,} Plats
Phone: {phone}""",
            reply_markup=markup
        )

def receive_txid(message):
    user = str(message.from_user.id)

    pending_deposit[user]["txid"] = message.text.strip()

    msg = bot.reply_to(
        message,
        "💰 Enter the amount you sent:"
    )

    bot.register_next_step_handler(msg, receive_amount)


def receive_amount(message):
    user = str(message.from_user.id)

    try:
        amount = float(message.text)
    except (ValueError, TypeError):
        bot.reply_to(message, "❌ Invalid amount.")
        return

    data = pending_deposit[user]

    # Check duplicate TXID
    if txid_exists(data["txid"]):
        bot.reply_to(message, "❌ This transaction has already been used.")
        return

    # Verify on blockchain
    ok, reason = verify_trc20_tx(data["txid"], amount)

    if not ok:
        bot.reply_to(message, f"❌ {reason}")
        return

    # Save as a pending deposit — balance is only credited once an admin
    # approves it below, even though the blockchain check already passed.
    # This gives a human a chance to catch anything unusual before real
    # money value gets converted into Plats.
    create_deposit(
        user,
        data["coin"],
        data["network"],
        data["txid"],
        amount
    )

    del pending_deposit[user]

    bot.send_message(
        message.chat.id,
        f"""⏳ Deposit Submitted!

We verified {amount} {data['coin']} on the blockchain.

Your deposit is now pending final admin approval — you'll be notified as soon as it's credited."""
    )

    # Look up the row we just inserted so we can attach the right id
    # to the admin's Approve/Reject buttons.
    pending_rows = get_pending_deposits()
    matching = [r for r in pending_rows if r[4] == data["txid"]]

    if not matching:
        return

    deposit_id = matching[-1][0]

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton(f"✅ Approve Deposit #{deposit_id}"),
        types.KeyboardButton(f"❌ Reject Deposit #{deposit_id}")
    )

    bot.send_message(
        ADMIN_ID,
        f"""💰 New Crypto Deposit (blockchain-verified)

👤 User: {user}
🪙 Coin: {data['coin']} ({data['network']})
💵 Amount: {amount}
🧾 TXID: {data['txid']}
""",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text.startswith("✅ Approve Deposit #"))
def approve_deposit_callback(message):

    if message.from_user.id != ADMIN_ID:
        return

    deposit_id = message.text.replace("✅ Approve Deposit #", "").strip()

    result = approve_deposit(deposit_id)

    if not result:
        bot.send_message(message.chat.id, "❌ Deposit not found or already processed.", reply_markup=admin_menu())
        return

    user_id, amount = result

    bot.send_message(message.chat.id, f"✅ Deposit approved — {amount} credited to {user_id}.", reply_markup=admin_menu())

    try:
        bot.send_message(
            int(user_id),
            f"""🎉 Deposit Approved!

✅ {amount} has been credited to your Plats balance.

Thank you for using MaveConnect!"""
        )
    except Exception:
        pass

    # Referral deposit bonus — only fires on the referred user's FIRST
    # ever approved deposit, so it can't be farmed by repeated deposits.
    if count_approved_deposits(user_id) == 1:
        referrer_id = get_referrer(user_id)

        if referrer_id:
            bonus = round(amount * REFERRAL_DEPOSIT_BONUS_RATE, 2)
            add_plats(referrer_id, bonus)

            try:
                bot.send_message(
                    int(referrer_id),
                    f"""
🎉 <b>Referral Deposit Bonus!</b>

Someone you referred just made their first deposit.

💰 +{bonus} Plats credited to your account.
""",
                    parse_mode="HTML"
                )
            except Exception:
                pass


@bot.message_handler(func=lambda m: m.text.startswith("❌ Reject Deposit #"))
def reject_deposit_callback(message):

    if message.from_user.id != ADMIN_ID:
        return

    deposit_id = message.text.replace("❌ Reject Deposit #", "").strip()

    user_id = reject_deposit(deposit_id)

    bot.send_message(message.chat.id, "❌ Deposit rejected.", reply_markup=admin_menu())

    if user_id:
        try:
            bot.send_message(
                int(user_id),
                """❌ Deposit Rejected

We couldn't verify or approve your deposit. If you believe this is an error, please contact MaveConnect Support."""
            )
        except Exception:
            pass
    
def receive_crypto_address(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw[user]["address"] = message.text.strip()

    bot.send_message(
        message.chat.id,
        "Enter the amount you want to withdraw."
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_amount
    )

def receive_crypto_amount(message):

    user = str(message.from_user.id)

    try:
        amount = float(message.text)
    except:
        bot.reply_to(message, "❌ Invalid amount.")
        return

    balance = get_balance(user)

    if amount < 10:
        bot.reply_to(message, "Minimum withdrawal is 10 Plats.")
        return

    if balance < amount:
        bot.reply_to(message, "❌ Insufficient balance.")
        return

    pending_crypto_withdraw[user]["amount"] = amount

    data = pending_crypto_withdraw[user]

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        KeyboardButton("✅ Confirm Withdrawal"),
        KeyboardButton("❌ Cancel")
    )

    bot.send_message(
        message.chat.id,
        f"""Confirm Withdrawal

Coin: {data['coin']}

Network: {data['network']}

Address:
{data['address']}

Amount:
{amount}

Press Confirm to continue.""",
        reply_markup=markup
    )

    # ================ VIP ==================

    # NOTE: VIP payment notifications are handled by vip.py's notify_admin(),
    # which uses the real vip_payments row id so admin approve/reject
    # buttons work correctly. The old notify_admin_vip_payment /
    # notify_admin_mpesa functions that used to live here duplicated that
    # with a broken callback_data scheme and have been removed.

# ==================== HISTORY ================

def get_history(symbol, days=60):
    coin_id = get_coin_id(symbol)
    print(f"Coin ID: {coin_id}")

    if not coin_id:
        return None

    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        url = (
            f"https://api.coinpaprika.com/v1/coins/"
            f"{coin_id}/ohlcv/historical?start={start}"
        )

        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code != 200:
            return None

        df = pd.DataFrame(response.json())
        
        print(df.head())
        print(df.columns)
        print(f"Rows: {len(df)}")

        if df.empty:
            return None

        df["time_open"] = pd.to_datetime(df["time_open"])
        df.set_index("time_open", inplace=True)

        return df

    except Exception as e:
        print(f"History Error: {e}")
        return None

# ================= FLASK =================

@app.route("/")
def home():
    return "LEVEL 4 AI TRADING BOT 🚀"


from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def trading_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🟢 Top Coins"),
        KeyboardButton("🤖 AI Coins")
    )

    markup.row(
        KeyboardButton("🐸 Meme Coins"),
        KeyboardButton("🏦 DeFi")
    )

    markup.row(
        KeyboardButton("⚡ Layer 1"),
        KeyboardButton("🔍 Search Coin")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

def ai_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🧠 FET"),
        KeyboardButton("⚡ TAO"),
        KeyboardButton("🤖 ICP")
    )

    markup.row(
        KeyboardButton("🔷 RENDER"),
        KeyboardButton("🛰 AKT"),
        KeyboardButton("💎 GRT")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup


def dashboard_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🏦 DeFi"),
        KeyboardButton("⚡ Layer 1")
    )

    markup.row(
        KeyboardButton("💎 RWA"),
        KeyboardButton("🎮 Games")
    )

    markup.row(
        KeyboardButton("🔎 Coin Search"),
        KeyboardButton("⭐ Favorites")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

def coin_actions():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("📊 Chart"),
        KeyboardButton("📰 News")
    )

    markup.row(
        KeyboardButton("⭐ Favorite"),
        KeyboardButton("🔔 Set Alert")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    markup.row(
        KeyboardButton("🤖 AI Analysis"),
        KeyboardButton("📊 Chart")
    )

    markup.row(
        KeyboardButton("📰 News"),
        KeyboardButton("⭐ Favorite") 
    )

    markup.row(
        KeyboardButton("🔔 Set Alert"),
        KeyboardButton("🏠 Home")
    )

    markup.row(
    KeyboardButton("🤖 AI Analysis")
    )

    return markup
    
# ================= MEME COINS ================
def memecoins_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🐕 DOGE"),
        KeyboardButton("🐶 SHIB"),
        KeyboardButton("🐸 PEPE")
    )

    markup.row(
        KeyboardButton("🐕 FLOKI"),
        KeyboardButton("🦴 BONK"),
        KeyboardButton("🐶 WIF")
    )

    markup.row(
        KeyboardButton("🍞 BRETT")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

#=============== DEFI MENU ================
def defi_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🦄 UNI"),
        KeyboardButton("👻 AAVE"),
        KeyboardButton("🏦 MKR")
    )

    markup.row(
        KeyboardButton("📈 CRV"),
        KeyboardButton("🥞 CAKE"),
        KeyboardButton("🍣 SUSHI")
    )

    markup.row(
        KeyboardButton("🔀 1INCH"),
        KeyboardButton("💧 LDO")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup
    
# ================= TOP COINS ===============

def topcoins_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("₿ BTC"),
        KeyboardButton("Ξ ETH"),
        KeyboardButton("🟡 BNB")
    )

    markup.row(
        KeyboardButton("☀️ SOL"),
        KeyboardButton("💧 XRP"),
        KeyboardButton("🔵 ADA")
    )

    markup.row(
        KeyboardButton("🐶 DOGE"),
        KeyboardButton("🔷 DOT"),
        KeyboardButton("⚡ LTC")
    )

    markup.row(
        KeyboardButton("🔺 TRX"),
        KeyboardButton("🏔 AVAX"),
        KeyboardButton("🔗 LINK")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

# ================ LAYER 1 =============

def layer1_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🌌 ATOM"),
        KeyboardButton("🌐 NEAR"),
        KeyboardButton("🚀 APT")
    )

    markup.row(
        KeyboardButton("💧 SUI"),
        KeyboardButton("💎 TON"),
        KeyboardButton("⚫ HBAR")
    )

    markup.row(
        KeyboardButton("⚡ KAS"),
        KeyboardButton("🦅 EGLD"),
        KeyboardButton("🔷 ALGO")
    )

    markup.row(
        KeyboardButton("✔️ VET")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

# ================= DEFI ===============

def rwa_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("💎 ONDO"),
        KeyboardButton("🕉 OM"),
        KeyboardButton("⏳ PENDLE")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

def mine_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("⛏️ Mine Now"),
        KeyboardButton("🎁 Daily")
    )

    markup.row(
        KeyboardButton("🏪 Shop"),
        KeyboardButton("💰 Balance")
    )

    markup.row(
        KeyboardButton("📈 Profile"),
        KeyboardButton("🏆 Leaderboard")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

def shop_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("⚒️ Upgrade Pickaxe")
    )

    markup.row(
        KeyboardButton("🔙 Back")
    )

    return markup

def upgrade_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🪨 Stone Pickaxe"),
        KeyboardButton("🥉 Bronze Pickaxe")
    )

    markup.row(
        KeyboardButton("⛓ Iron Pickaxe"),
        KeyboardButton("🥇 Gold Pickaxe")
    )

    markup.row(
        KeyboardButton("💎 Diamond Pickaxe")
    )

    markup.row(
        KeyboardButton("🔙 Back")
    )

    return markup
    
def wallet_keyboard():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("➕ Deposit"),
        KeyboardButton("➖ Withdraw")
    )

    markup.row(
        KeyboardButton("💵 Buy Plats (M-Pesa)")
    )

    markup.row(
        KeyboardButton("📈 Staking")
    )

    markup.row(
        KeyboardButton("💰 Balance"),
        KeyboardButton("📜 History")
    )

    markup.row(
        KeyboardButton("⭐ Favorite"),
        KeyboardButton("🔔 Alerts")
    )

    markup.row(
        KeyboardButton("🏠 Home")
    )

    return markup

def deposit_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("📱 M-Pesa"),
        KeyboardButton("🪙 Crypto")
    )

    markup.row(
        KeyboardButton("⬅️ Wallet")
    )

    return markup

def withdraw_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("📱 M-Pesa"),
        KeyboardButton("💸 Crypto Withdraw")
    )

    markup.row(
        KeyboardButton("💳 Wallet")
    )

    return markup

def crypto_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("💵 USDT"),
        KeyboardButton("₿ Bitcoin")
    )

    markup.row(
        KeyboardButton("Ξ Ethereum"),
        KeyboardButton("➕ Deposit")
    )

    return markup

def payment_confirm_keyboard():
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "✅ I've Paid",
            callback_data="crypto_paid"
        )
    )

    return markup

def usdt_network_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🔴 TRC20"),
        KeyboardButton("🔵 ERC20")
    )

    markup.row(
        KeyboardButton("🟡 BEP20")
    )

    markup.row(
        KeyboardButton("🔙 Back")
    )

    return markup

def payment_sent_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("✅ I've Sent Payment")
    )

    markup.row(
        KeyboardButton("🔙 Back")
    )

    return markup


def partners_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🟡 Binance"),
        KeyboardButton("⚫ OKX")
    )

    markup.row(
        KeyboardButton("🟠 Bybit"),
        KeyboardButton("🔵 Coinbase")
    )

    markup.row(
        KeyboardButton("💎 VIP Channel"),
        KeyboardButton("📢 Telegram Channel")
    )

    markup.row(KeyboardButton("🔙 Back"))

    return markup

def crypto_withdraw_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("₿ Bitcoin"),
        KeyboardButton("Ξ Ethereum")
    )

    markup.row(
        KeyboardButton("🔴 USDT TRC20"),
        KeyboardButton("🟡 USDT BEP20")
    )

    markup.row(
        KeyboardButton("🔵 USDT ERC20")
    )

    markup.row(
        KeyboardButton("⬅️ Withdraw"),
        KeyboardButton("🏠 Home")
    )

    return markup

# ================= COMMANDS ================

SIGNUP_BONUS = 20
REFERRAL_BONUS = 50
REFERRAL_DEPOSIT_BONUS_RATE = 0.10  # referrer gets 10% of a referred user's first approved deposit, as Plats


@bot.message_handler(commands=["start"])
def start(msg):

    user_id = str(msg.from_user.id)

    parts = msg.text.split(maxsplit=1)
    referrer_id = parts[1].strip() if len(parts) > 1 else None

    is_new_user = register_new_user(user_id, referrer_id)

    if is_new_user:
        add_plats(user_id, SIGNUP_BONUS)

        real_referrer = get_referrer(user_id)

        if real_referrer:
            add_plats(real_referrer, REFERRAL_BONUS)

            try:
                bot.send_message(
                    int(real_referrer),
                    f"""
🎉 <b>You earned a referral bonus!</b>

Someone joined MaveConnect using your link.

💰 +{REFERRAL_BONUS} Plats credited to your account.

Keep sharing to earn more! 👥
""",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        bot.send_message(
            msg.chat.id,
            f"👋 Welcome to MaveConnect!\n\n"
            f"🚀 LEVEL 4 AI TRADING BOT\n\n"
            f"🎁 Welcome bonus: +{SIGNUP_BONUS} Plats credited!\n\n"
            f"📢 Free Group:\n{FREE_GROUP}\n\n"
            f"💎 VIP Group:\n{VIP_GROUP}\n\n"
            f"Use the menu below 👇",
            reply_markup=main_menu()
        )
        return

    bot.send_message(
        msg.chat.id,
        f"👋 Welcome to MaveConnect!\n\n"
        f"🚀 LEVEL 4 AI TRADING BOT\n\n"
        f"📢 Free Group:\n{FREE_GROUP}\n\n"
        f"💎 VIP Group:\n{VIP_GROUP}\n\n"
        f"Use the menu below 👇",
        reply_markup=main_menu()
    )
    
@bot.message_handler(commands=["ping"])
def ping(msg):
    bot.reply_to(msg, "🏓 Pong! Bot is alive.")

@bot.message_handler(commands=["test"])
def test(msg):
    bot.reply_to(msg, "🔥 BOT ONLINE AND WORKING")

@bot.message_handler(commands=["price"])
def price_cmd(msg):
    try:
        parts = msg.text.split()

        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /price btc")
            return

        coin = parts[1].lower().strip()
        
        #Save the last coin viewed
        user_last_coin[msg.from_user.id] = coin
        
        price =get_price(coin)

        if price is not None:
            bot.reply_to(
                msg,
                f"💰 {coin.upper()} = ${price:,.4f}"
            )
        else:
            bot.reply_to(
                msg,
                "❌ Coin not found or price service unavailable."
            )

    except Exception as e:
        print("Price error:", repr(e))
        bot.reply_to(msg, "⚠️ Error getting price")

@bot.message_handler(commands=["signal"])
def signal_cmd(msg):

    if not is_vip(msg.from_user.id):
        bot.reply_to(
            msg,
            f"🔒 VIP ONLY FEATURE\n\n"
            f"Join VIP:\n{VIP_GROUP}"
        )
        return

    try:
        parts = msg.text.split()

        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /signal btc")
            return

        coin = parts[1].lower().strip()

        result = get_signal(coin)

        if result is None:
            bot.reply_to(msg, "❌ Coin not found")
            return

        bot.reply_to(
            msg,
            f"🤖 {coin.upper()} SIGNAL\n\n"
            f"{result['action']}\n"
            f"💰 Price: ${result['price']:,.4f}\n"
            f"📈 24H Change: {result['change']:.2f}%\n"
            f"🔥 Strength: {result['score']}/100\n"
            f"🟢 Support: ${result['support']:,.4f}\n"
            f"🔴 Resistance: ${result['resistance']:,.4f}"
        )

    except Exception as e:
        print("Signal error:", repr(e))
        bot.reply_to(msg, "⚠️ Error generating signal")

@bot.message_handler(commands=["scan"])
def scan(msg):

    if not is_vip(msg.from_user.id):
        bot.reply_to(
            msg,
            f"🔒 VIP ONLY FEATURE\n\n"
            f"Join VIP:\n{VIP_GROUP}"
        )
        return

    bot.reply_to(msg, "🔍 Scanning market...")

    try:
        output = "📊 LEVEL 4 MARKET SCAN\n\n"

        SCAN_COINS = ["btc", "eth", "bnb", "sol", "xrp"]

        for coin in SCAN_COINS:
            result = get_signal(coin)

            if result:
                output += (
                    f"{coin.upper()} | "
                    f"{result['action']} | "
                    f"{result['score']}/100\n"
                )

        bot.send_message(msg.chat.id, output)

    except Exception as e:
        print("Scan error:", repr(e))
        bot.reply_to(msg, "⚠️ Scan failed")

@bot.message_handler(commands=["addvip"])
def addvip(msg):

    if msg.from_user.id != ADMIN_ID:
        return

    parts = msg.text.split()

    if len(parts) < 2:
        bot.reply_to(msg, "Usage: /addvip USER_ID [plan] [days]")
        return

    try:
        user_id = parts[1]
        plan = parts[2] if len(parts) >= 3 else "basic"
        days = int(parts[3]) if len(parts) >= 4 else 30

        from datetime import datetime, timedelta
        expiry = datetime.now() + timedelta(days=days)

        activate_vip_admin(user_id, plan, expiry)

        bot.reply_to(
            msg,
            f"✅ Added {user_id} to VIP — {plan.title()} plan, {days} days"
        )

    except Exception as e:
        bot.reply_to(msg, f"Error: {e}")

@bot.message_handler(commands=["removevip"])
def removevip(msg):

    if msg.from_user.id != ADMIN_ID:
        return

    parts = msg.text.split()

    if len(parts) != 2:
        bot.reply_to(msg, "Usage: /removevip USER_ID")
        return

    try:
        user_id = parts[1]

        remove_vip_admin(user_id)

        bot.reply_to(
            msg,
            f"❌ Removed {user_id} from VIP"
        )

    except Exception as e:
        bot.reply_to(msg, f"Error: {e}")

@bot.message_handler(commands=["vipcount"])
def vipcount(msg):

    if msg.from_user.id != ADMIN_ID:
        return

    bot.reply_to(
        msg,
        f"💎 VIP Users: {get_total_vip_admin()}"
    )


@bot.message_handler(commands=["nettest"])
def nettest(msg):
    try:
        r = requests.get("https://www.google.com", timeout=10)
        bot.reply_to(msg, f"Google OK: {r.status_code}")
    except Exception as e:
        bot.reply_to(msg, str(e))
        
@bot.message_handler(commands=["paprika"])
def paprika_test(msg):
    try:
        r = requests.get(
            "https://api.coinpaprika.com/v1/tickers/btc-bitcoin",
            timeout=10
        )

        bot.reply_to(
            msg,
            f"Status: {r.status_code}\n\n{r.text[:500]}"
        )

    except Exception as e:
        bot.reply_to(msg, f"Error: {e}")

@bot.message_handler(commands=["subscribe"])
def subscribe(msg):

    bot.reply_to(
        msg,
        "💎 LEVEL 4 VIP\n\n"
        "Choose a plan:\n\n"
        "⭐ 250 Stars - 1 Month VIP\n"
        "⭐ 650 Stars - 3 Months VIP\n"
        "⭐ 2,000 Stars - Lifetime VIP\n\n"
        "Use /buyvip to purchase."
    )

@bot.message_handler(commands=["help"])
def help_cmd(msg):

    bot.reply_to(
        msg,
        "🤖 LEVEL 4 AI BOT\n\n"
        "📈 Trading\n"
        "/price btc\n"
        "/signal btc\n"
        "/scan\n\n"
        "🦆 Platypus Game\n"
        "/mine\n"
        "/daily\n"
        "/balance\n"
        "/profile\n"
        "/leaderboard\n\n"
        "💎 VIP\n"
        "/subscribe\n"
        "/help"
    )

@bot.message_handler(func=lambda m: m.text == "💳 Mave Wallet")
def wallet_menu(message):
    user = str(message.from_user.id)

    balance = get_balance(user)

    bot.send_message(
        message.chat.id,
        f"""💳 *Mave Wallet*

💰 Balance: {balance:,} Plats

Choose an option below.""",
        reply_markup=wallet_keyboard(),
        parse_mode="Markdown"
    )


# ==================== BUY PLATS (M-PESA) ====================
# NOTE: stk.py currently points at Safaricom's SANDBOX shortcode/passkey.
# Real STK prompts will only reach real phones once you swap those for
# your production Daraja credentials (shortcode + passkey) from Safaricom.
#
# Also: Safaricom's STK push is asynchronous — it normally confirms payment
# via a callback to a public URL (CALLBACK_URL) that a running web server
# would need to receive. This bot is polling-based with no web server, so
# instead of relying on that callback, the flow below asks the user to
# paste the M-Pesa confirmation code they receive by SMS, then routes it
# to you (the admin) for a one-tap approval — exactly like the crypto
# deposit flow — before any Plats are credited.

@bot.message_handler(func=lambda m: m.text == "💵 Buy Plats (M-Pesa)")
def buy_plats_start(message):
    user = str(message.from_user.id)

    buy_plats_state[user] = {}

    msg = bot.send_message(
        message.chat.id,
        "💵 How many Plats would you like to buy?\n\n(1 Plat = 1 KSh)",
        reply_markup=back_only_wallet_keyboard()
    )

    bot.register_next_step_handler(msg, buy_plats_amount)


def buy_plats_amount(message):
    user = str(message.from_user.id)

    if message.text == "🔙 Back":
        buy_plats_state.pop(user, None)
        wallet_menu(message)
        return

    try:
        plats_amount = int(message.text.replace(",", "").strip())
    except (ValueError, AttributeError):
        msg = bot.reply_to(message, "❌ Please enter a valid whole number.")
        bot.register_next_step_handler(msg, buy_plats_amount)
        return

    if plats_amount < 10:
        msg = bot.reply_to(message, "❌ Minimum purchase is 10 Plats.")
        bot.register_next_step_handler(msg, buy_plats_amount)
        return

    buy_plats_state[user]["amount"] = plats_amount

    msg = bot.send_message(
        message.chat.id,
        f"📱 Enter the M-Pesa phone number to send the STK push to (e.g. 0712345678):"
    )

    bot.register_next_step_handler(msg, buy_plats_phone)


def buy_plats_phone(message):
    user = str(message.from_user.id)

    phone = message.text.strip()

    if not phone.isdigit() or len(phone) not in (9, 10, 12):
        msg = bot.reply_to(message, "❌ Please enter a valid phone number.")
        bot.register_next_step_handler(msg, buy_plats_phone)
        return

    # Normalize to 2547XXXXXXXX for the Daraja API
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("7") or phone.startswith("1"):
        phone = "254" + phone

    amount = buy_plats_state[user]["amount"]

    try:
        result = stk_push(
            phone,
            amount,
            f"PLATS{user}",
            "Buy MaveConnect Plats"
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"⚠️ Could not send the M-Pesa prompt right now.\n\nError: {e}"
        )
        buy_plats_state.pop(user, None)
        return

    if result.get("ResponseCode") != "0":
        bot.send_message(
            message.chat.id,
            f"❌ M-Pesa did not accept the request:\n{result.get('errorMessage', result)}"
        )
        buy_plats_state.pop(user, None)
        return

    buy_plats_state[user]["phone"] = phone

    msg = bot.send_message(
        message.chat.id,
        f"""📲 Check your phone!

An M-Pesa prompt has been sent to {phone} for {amount} KSh.

Once you've entered your PIN and received the confirmation SMS, paste the M-Pesa code here."""
    )

    bot.register_next_step_handler(msg, buy_plats_code)


def buy_plats_code(message):
    user = str(message.from_user.id)

    state = buy_plats_state.get(user)

    if not state:
        bot.reply_to(message, "❌ Session expired. Please start again from 💳 Mave Wallet.")
        return

    code = message.text.strip().upper()
    amount = state["amount"]
    phone = state["phone"]

    if txid_exists(code):
        bot.reply_to(message, "❌ This M-Pesa code has already been used.")
        return

    # Reuses the deposits table (coin="KES", network="M-Pesa") so this
    # goes through the exact same admin approval path as crypto deposits.
    create_deposit(user, "KES", "M-Pesa", code, amount)

    buy_plats_state.pop(user, None)

    bot.send_message(
        message.chat.id,
        f"""⏳ Submitted for review!

💵 Amount: {amount} Plats
🧾 M-Pesa Code: {code}

You'll be notified once it's approved.""",
        reply_markup=wallet_keyboard()
    )

    pending_rows = get_pending_deposits()
    matching = [r for r in pending_rows if r[4] == code]

    if not matching:
        return

    deposit_id = matching[-1][0]

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approvedeposit_{deposit_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rejectdeposit_{deposit_id}")
    )

    bot.send_message(
        ADMIN_ID,
        f"""🇰🇪 New M-Pesa Plats Purchase

👤 User: {user}
📱 Phone: {phone}
💵 Amount: {amount} Plats
🧾 M-Pesa Code: {code}

⚠️ Please verify this code in your M-Pesa statement before approving.""",
        reply_markup=markup
    )


def back_only_wallet_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔙 Back"))
    return markup


@bot.message_handler(func=lambda m: m.text == "📜 History")
def history(message):
    user = str(message.from_user.id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT type, amount, description, created_at
        FROM transactions
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 10
    """, (user,))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        bot.reply_to(message, "📭 No transactions yet.")
        return

    text = "📜 *Recent Transactions*\n\n"

    for t in rows:
        text += (
            f"• {t[0]}\n"
            f"💰 {t[1]}\n"
            f"📝 {t[2]}\n"
            f"📅 {t[3].strftime('%d %b %Y %H:%M')}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "➕ Deposit")
def deposit_menu(message):

    bot.send_message(
        message.chat.id,
        "💳 Deposit Funds\n\n"
        "Choose your preferred payment method:",
        reply_markup=deposit_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "⬅️ Wallet")
def back_wallet(message):
    wallet_keyboard(message)

@bot.message_handler(func=lambda m: m.text == "📱 M-Pesa")
def mpesa_deposit(message):
    msg = bot.send_message(
        message.chat.id,
        "💵 Enter the amount you want to deposit (KES):"
    )

    bot.register_next_step_handler(msg, get_mpesa_amount)

@bot.message_handler(func=lambda m: m.text == "➖ Withdraw")
def withdraw(message):

    bot.send_message(
        message.chat.id,
        """➖ Withdraw

Choose your withdrawal method.""",
        reply_markup=withdraw_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📱 M-Pesa")
def mpesa_withdraw(message):

    bot.send_message(
        message.chat.id,
        """📱 M-Pesa Withdrawal

Minimum: 500 Plats

Send the amount you want to withdraw."""
    )

    bot.register_next_step_handler(
        message,
        process_mpesa_amount
    )


@bot.message_handler(func=lambda m: m.text == "🪙 Crypto Deposit")
def crypto_deposit(message):

    bot.send_message(
        message.chat.id,
        """🪙 Crypto Deposit

Choose a cryptocurrency:

• USDT (TRC20)
• USDT (ERC20)
• Bitcoin
• Ethereum

(Support for each will be added one by one.)""",
        reply_markup=crypto_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💵 USDT")
def usdt_menu(message):
    bot.send_message(
        message.chat.id,
        """💵 USDT Deposit

Choose the network you want to use.""",
        reply_markup=usdt_network_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💸 Crypto Withdraw")
def crypto_withdraw(message):

    bot.send_message(
        message.chat.id,
        "Select the cryptocurrency you want to withdraw.",
        reply_markup=crypto_withdraw_menu()
    )
    
@bot.message_handler(func=lambda m: m.text == "🔴 TRC20")
def usdt_trc20(message):
    user = str(message.from_user.id)

    pending_deposit[user] = {
        "coin": "USDT",
        "network": "TRC20"
    }

    bot.send_message(
        message.chat.id,
        """💵 *USDT Deposit*

Network: TRC20

Send USDT to:

`TCHtvSHZgSzKAg85GzJoVgxBTUUauxYGna`

Minimum Deposit: 5 USDT

After completing the transfer, tap the button below.
""",
        parse_mode="Markdown",
        reply_markup=payment_sent_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🔵 ERC20")
def usdt_erc20(message):
    user = str(message.from_user.id)

    pending_deposit[user] = {
        "coin": "USDT",
        "network": "ERC20"
    }

    bot.send_message(
        message.chat.id,
        """💵 *USDT Deposit*

Network: ERC20

Send USDT to:

`0x6E4B1b38f345764B430017D7885828f3d91DcaA0`

Minimum Deposit: 5 USDT

After completing the transfer, tap the button below.
""",
        parse_mode="Markdown",
        reply_markup=payment_sent_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🟡 BEP20")
def usdt_bep20(message):
    user = str(message.from_user.id)

    pending_deposit[user] = {
        "coin": "USDT",
        "network": "BEP20"
    }

    bot.send_message(
        message.chat.id,
        """💵 *USDT Deposit*

Network: BEP20

Send USDT to:

`0x6E4B1b38f345764B430017D7885828f3d91DcaA0`

Minimum Deposit: 5 USDT

After completing the transfer, tap the button below.
""",
        parse_mode="Markdown",
        reply_markup=payment_sent_menu()
    )

@bot.message_handler(func=lambda m: m.text == "Ξ Ethereum")
def withdraw_eth(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw[user] = {
        "coin": "ETH",
        "network": "ERC20"
    }

    bot.send_message(
        message.chat.id,
        """Ξ Ethereum Withdrawal

Send your Ethereum wallet address.

Example:

0x1234567890abcdef1234567890abcdef12345678"""
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_address
    )
    
@bot.message_handler(func=lambda m: m.text == "₿ Bitcoin")
def withdraw_btc(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw[user] = {
        "coin": "BTC",
        "network": "Bitcoin"
    }

    bot.send_message(
        message.chat.id,
        """₿ Bitcoin Withdrawal

Send your Bitcoin wallet address.

Example:

bc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxx"""
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_address
    )

@bot.message_handler(func=lambda m: m.text == "🔴 USDT TRC20")
def withdraw_usdt_trc20(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw[user] = {
        "coin": "USDT",
        "network": "TRC20"
    }

    bot.send_message(
        message.chat.id,
        """🔴 USDT (TRC20) Withdrawal

Send your TRC20 wallet address.

Example:

TJzxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"""
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_address
    )

@bot.message_handler(func=lambda m: m.text == "🟡 USDT BEP20")
def withdraw_usdt_bep20(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw[user] = {
        "coin": "USDT",
        "network": "BEP20"
    }

    bot.send_message(
        message.chat.id,
        """🟡 USDT (BEP20) Withdrawal

Send your BEP20 wallet address.

Example:

0x1234567890abcdef1234567890abcdef12345678"""
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_address
    )

@bot.message_handler(func=lambda m: m.text == "🔵 USDT ERC20")
def withdraw_usdt_erc20(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw[user] = {
        "coin": "USDT",
        "network": "ERC20"
    }

    bot.send_message(
        message.chat.id,
        """🔵 USDT (ERC20) Withdrawal

Send your ERC20 wallet address.

Example:

0x1234567890abcdef1234567890abcdef12345678"""
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_address
    )
    
@bot.message_handler(func=lambda m: m.text == "₿ Bitcoin")
def deposit_btc(message):

    bot.send_message(
        message.chat.id,
        """₿ *Bitcoin Deposit*

Network: Bitcoin

Send BTC to:

`bc1q0lr6msjjnmfw73nfdttauwhju03jvhmauu4fwk`

After completing the transfer, tap the button below.
""",
        parse_mode="Markdown",
        reply_markup=payment_sent_menu()
    )


@bot.message_handler(func=lambda m: m.text == "Ξ Ethereum")
def deposit_eth(message):
    user = str(message.from_user.id)

    pending_deposit[user] = {
        "coin": "ETH",
        "network": "ERC20"
    }

    bot.send_message(
        message.chat.id,
        """Ξ *Ethereum Deposit*

Network: ERC20

Send ETH to:

`0x6e4b1b38f345764b430017d7885828f3d91dcaa0`

Minimum Deposit: 0.001 ETH

After completing the transfer, tap the button below.
""",
        parse_mode="Markdown",
        reply_markup=payment_sent_menu()
    )


@bot.message_handler(func=lambda m: m.text == "✅ I've Sent Payment")
def sent_payment(message):
    user = str(message.from_user.id)

    if user not in pending_deposit:
        bot.reply_to(
            message,
            "❌ Start a deposit first."
        )
        return

    msg = bot.reply_to(
        message,
        "📄 Send your Transaction ID (TXID):"
    )

    bot.register_next_step_handler(msg, receive_txid)
@bot.callback_query_handler(func=lambda c: c.data == "crypto_paid")
def crypto_paid(call):

    bot.answer_callback_query(
        call.id,
        "Request received!"
    )

    bot.send_message(
        call.message.chat.id,
        """📤 Deposit Submitted

Please send your transaction hash (TXID).

Example:
`0x5f7b...`

Our team will verify your payment shortly.""",
        parse_mode="Markdown"
    )

    bot.register_next_step_handler(
        call.message,
        receive_txid
    )

@bot.message_handler(func=lambda m: m.text in CRYPTOS)
def crypto_wallet(message):

    user = str(message.from_user.id)

    coin, network = CRYPTOS[message.text]

    pending_crypto_withdraw[user] = {
        "coin": coin,
        "network": network
    }

    bot.send_message(
        message.chat.id,
        f"Send your {coin} ({network}) wallet address."
    )

    bot.register_next_step_handler(
        message,
        receive_crypto_address
    )

@bot.message_handler(func=lambda m: m.text == "✅ Confirm Withdrawal")
def confirm_crypto_withdraw(message):

    user = str(message.from_user.id)

    if user not in pending_crypto_withdraw:
        return

    data = pending_crypto_withdraw[user]

    add_transaction(
        user,
        "Withdrawal",
        data["amount"],
        f"{data['coin']} ({data['network']})"
    )

    add_crypto_withdrawal(
        user,
        data["coin"],
        data["network"],
        data["address"],
        data["amount"]
    )

    bot.send_message(
        ADMIN_ID,
        f"""💸 Crypto Withdrawal

User: {user}

Coin: {data['coin']}

Network: {data['network']}

Amount: {data['amount']}

Address:
{data['address']}"""
    )

    bot.send_message(
        message.chat.id,
        "✅ Your withdrawal request has been submitted and is awaiting approval."
    )

    del pending_crypto_withdraw[user]

@bot.message_handler(func=lambda m: m.text == "❌ Cancel")
def cancel_crypto_withdraw(message):

    user = str(message.from_user.id)

    pending_crypto_withdraw.pop(user, None)

    bot.send_message(
        message.chat.id,
        "❌ Withdrawal cancelled.",
        reply_markup=wallet_menu()
    )
    
@bot.message_handler(commands=["deposit"])
def deposit_command(message):
    bot.send_message(
        message.chat.id,
        "Choose a deposit method:",
        reply_markup=deposit_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "✅ I've Sent Payment")
def sent_payment(message):
    user = str(message.from_user.id)

    if user not in pending_deposit:
        bot.reply_to(
            message,
            "❌ Start a deposit first."
        )
        return

    msg = bot.reply_to(
        message,
        "📄 Send your Transaction ID (TXID):"
    )

    bot.register_next_step_handler(msg, receive_txid)

@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def payment_back(message):
    user = str(message.from_user.id)

    pending_deposit.pop(user, None)

    bot.send_message(
        message.chat.id,
        "💳 Mave Wallet",
        reply_markup=wallet_keyboard()
    )
    
@bot.message_handler(func=lambda m: m.text == "⛏️ Mine")
def mining_center(msg):
    user = str(msg.from_user.id)

    balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    bot.reply_to(
        msg,
        f"⛏️ Mining Center\n\n"
        f"💰 Balance: {balance} PLATS\n"
        f"⚒️ Pickaxe: {PICKAXES[pickaxe]['name']}\n"
        f"🏅 Level: {level}\n"
        f"⭐ XP: {xp}/100",
        reply_markup=mine_menu()
    )

@bot.message_handler(commands=["deposits"])
def deposits(message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    rows = get_pending_deposits()

    if not rows:
        bot.reply_to(message, "✅ No pending deposits.")
        return

    for row in rows:
        deposit_id, user, coin, network, txid, amount = row

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approvedeposit_{deposit_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rejectdeposit_{deposit_id}")
        )

        bot.send_message(
            message.chat.id,
            f"""💰 Pending Deposit

ID: {deposit_id}
User: {user}
Coin: {coin}
Network: {network}
Amount: {amount}
TXID: {txid}""",
            reply_markup=markup
        )


@bot.message_handler(func=lambda m: m.text == "🤝 Partners")
def partners(message):

    bot.send_message(
        message.chat.id,
        """
🤝 <b>MaveConnect Partner Exchanges</b>

We've teamed up with the world's top crypto exchanges so you can trade smarter, earn more, and stack rewards on top of your MaveConnect account.

💸 Sign up through our links below and unlock welcome bonuses, fee discounts, and exclusive perks — completely free.

👇 Pick an exchange to get started.
""",
        parse_mode="HTML",
        reply_markup=partners_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🟡 Binance")
def binance(message):

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟡 Join Binance Now", url=BINANCE_REFERRAL))

    bot.send_message(
        message.chat.id,
        """
🟡 <b>Binance — World's #1 Crypto Exchange</b>

Trusted by over 250 million users worldwide. This is where serious traders go.

🎁 <b>What you get:</b>
✅ Welcome rewards for new users
✅ Spot &amp; Futures Trading
✅ Binance Earn — grow your crypto passively
✅ Industry-low trading fees
✅ Launchpool &amp; Launchpad early access

Tap below to claim your bonus and start trading in minutes.

❤️ Thank you for supporting MaveConnect.
""",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "⚫ OKX")
def okx(message):

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚫ Join OKX Now", url=OKX_REFERRAL))

    bot.send_message(
        message.chat.id,
        """
⚫ <b>OKX — Trade Like a Pro</b>

One of the world's leading exchanges, built for traders who want power and speed.

🎁 <b>What you get:</b>
✅ Welcome rewards for new users
✅ Spot &amp; Futures Trading
✅ Earn products for passive income
✅ Low trading fees
✅ Advanced professional trading tools

Tap below to claim your bonus and start trading in minutes.

❤️ Thank you for supporting MaveConnect.
""",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "🟠 Bybit")
def bybit(message):

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟠 Join Bybit Now", url=BYBIT_REFERRAL))

    bot.send_message(
        message.chat.id,
        """
🟠 <b>Bybit — Fast, Reliable, Global</b>

A top-5 exchange trusted by millions for its speed, security, and generous rewards program.

🎁 <b>What you get:</b>
✅ Generous sign-up bonus
✅ Spot &amp; Derivatives Trading
✅ Bybit Earn &amp; Savings products
✅ Competitive trading fees
✅ Copy Trading — follow top traders automatically

Tap below to claim your bonus and start trading in minutes.

❤️ Thank you for supporting MaveConnect.
""",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "🔵 Coinbase")
def coinbase(message):

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔵 Join Coinbase Now", url=COINBASE_REFERRAL))

    bot.send_message(
        message.chat.id,
        """
🔵 <b>Coinbase — The Most Trusted Name in Crypto</b>

A publicly listed, fully regulated exchange used by beginners and pros alike. If you want peace of mind, this is it.

🎁 <b>What you get:</b>
✅ Easy, beginner-friendly onboarding
✅ Access to the Base app &amp; ecosystem
✅ Strong security &amp; regulatory trust
✅ Simple buy/sell for major cryptocurrencies
✅ Built-in wallet for everyday crypto use

Tap below to join and get started.

❤️ Thank you for supporting MaveConnect.
""",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "💎 VIP Channel")
def vip_channel(message):

    bot.send_message(
        message.chat.id,
        f"""
💎 *MaveConnect VIP*

Unlock premium benefits.

⭐ Premium support
⭐ Early feature access
⭐ Exclusive rewards
⭐ VIP announcements

🔗 {VIP_GROUP}
        """,
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: m.text == "📢 Telegram Channel")
def telegram_channel(message):

    bot.send_message(
        message.chat.id,
        f"""
📢 *Official MaveConnect Channel*

Stay updated with:

📈 Crypto news
🎉 Giveaways
🚀 New features
📢 Important announcements

🔗 {FREE_GROUP}
        """,
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: m.text == "🎁 VIP Benefits")
def vip_benefits(message):

    text = """
👑 VIP Benefits

✅ 2× Mining Rewards

✅ 2× Faucet Rewards

✅ Daily VIP Bonus

✅ Faster Withdrawals

✅ VIP Badge

✅ Premium Airdrops

✅ Exclusive Giveaways

✅ Early Features

✅ Priority Support
"""

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back(message):
    main_menu(message)


@bot.message_handler(func=lambda m: m.text == "⛏️ Mine Now")
def do_mine(msg):

    user = str(msg.from_user.id)

    balance, xp, level, pickaxe, last_daily, last_mine, wins, streak= get_profile(user)

    now = int(time.time())

    cooldown = PICKAXES[pickaxe]["cooldown"]

    if now - last_mine < cooldown:

        left = cooldown - (now-last_mine)

        mins = left // 60
        secs = left % 60

        bot.reply_to(
            msg,
            f"⛏️ Mine cooling down.\n\n"
            f"Try again in {mins}m {secs}s"
        )

        return

    reward = random.randint(
      PICKAXES[pickaxe]["min"],
      PICKAXES[pickaxe]["max"]
    ) + level * 5

    xp += 5

    balance += reward

    if xp >= 100:
        xp = 0
        level += 1
        balance += 50

        levelup = (
            f"\n\n🎉 LEVEL UP!\n"
            f"You reached Level {level}\n"
            f"+50 Bonus PLATS"
        )
    else:
        levelup = ""

    update_mine(
        user,
        balance,
        xp,
        level,
        pickaxe,
        now
    )

    add_transaction(
    user,
    "Mining",
    reward,
    "Mining reward"
    )
    
    if balance >= 1000 and not has_achievement(user, "First 1000"):
        unlock_achievement(user, "First 1000")
        bot.send_message(
        user,
        "🏅 Achievement Unlocked!\n\n💰 First 1,000 Plats!"
        )
    
    finds = [
        "💎 Diamond",
        "🪙 Gold",
        "🥈 Silver",
        "🪨 Stone",
        "💰 Treasure Chest",
        "🧱 Ancient Relic"
    ]

    found = random.choice(finds)
    
    bot.reply_to(
       msg,
       f"⛏️ Mining Complete!\n\n"
       f"You discovered:\n"
       f"{found}\n\n"
       f"💰 Earned: +{reward} PLATS\n"
       f"⭐ XP: +5\n\n"
       f"💳 Balance: {balance} PLATS\n"
       f"🏅 Level: {level}\n"
       f"{levelup}",
       reply_markup=mine_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🏪 Shop")
def shop(msg):

    user = str(msg.from_user.id)

    balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    # Already at max level
    if pickaxe == max(PICKAXES.keys()):
        bot.reply_to(
            msg,
            "🏪 SHOP\n\n"
            "🏆 You already own the best pickaxe!\n\n"
            f"⚒️ Current: {PICKAXES[pickaxe]['name']}",
            reply_markup=shop_menu()
        )
        return

    next_pickaxe = pickaxe + 1

    bot.reply_to(
    msg,
    f"🏪 PICKAXE SHOP\n\n"
    f"💰 Balance: {balance} PLATS\n\n"
    f"⚒️ Current: {PICKAXES[pickaxe]['name']}\n\n"
    f"⬆️ Next Upgrade: {PICKAXES[next_pickaxe]['name']}\n\n"
    f"💵 Cost: {PICKAXES[next_pickaxe]['price']} PLATS\n"
    f"💎 Reward: {PICKAXES[next_pickaxe]['min']} - {PICKAXES[next_pickaxe]['max']} PLATS\n"
    f"⏳ Cooldown: {PICKAXES[next_pickaxe]['cooldown']//60} mins",
    reply_markup=shop_menu()
    )

@bot.message_handler(func=lambda m: m.text == "⚒️ Upgrade Pickaxe")
def upgrade_pickaxe_menu(msg):

    user = str(msg.from_user.id)

    balance = get_balance(user)

    bot.reply_to(
        msg,
        f"""
⚒️ Pickaxe Upgrades

💰 Your Balance: {balance:,} PLATS

Choose a pickaxe to upgrade:

🪨 Stone pickaxe   - 500 PLATS
🥉 Bronze pickaxe   - 2,000 PLATS
🥈 Iron pickaxe      - 5,000 PLATS
🥇 Gold pickaxe      - 10,000 PLATS
💎 Diamond pickaxe   - 25,000 PLATS

Higher pickaxes increase mining rewards and may reduce cooldown.
""",
        reply_markup=upgrade_menu()
    )


@bot.message_handler(func=lambda m: m.text in PICKAXE_BUTTONS)
def buy_pickaxe(msg):

    user = str(msg.from_user.id)

    level = PICKAXE_BUTTONS[msg.text]
    pickaxe = PICKAXES[level]

    name = pickaxe["name"]
    price = pickaxe["price"]

    balance, xp, user_level, current_pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    if level <= current_pickaxe:
        bot.reply_to(
            msg,
            "❌ You already own this pickaxe or a better one."
        )
        return

    if balance < price:
        bot.reply_to(
            msg,
            f"❌ You need {price:,} PLATS.\n"
            f"💰 Balance: {balance:,} PLATS"
        )
        return

    balance -= price

    update_pickaxe(user, balance, level)

    bot.reply_to(
       msg,
       f"🎉 Upgrade Successful!\n\n"
       f"⚒️ New Pickaxe: {pickaxe['name']}\n"
       f"⭐ Mining Bonus: +{pickaxe['bonus']} PLATS\n"
       f"⏳ Cooldown: {pickaxe['cooldown']//60} minutes\n\n"
       f"💳 Remaining Balance: {balance:,} PLATS",
       reply_markup=mine_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back_to_mine(msg):

    bot.reply_to(
        msg,
        "⛏️ Mining Menu",
        reply_markup=mine_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back_from_upgrade(msg):
    bot.reply_to(
        msg,
        "⛏️ Mining Menu",
        reply_markup=mine_menu()
    )
    
@bot.message_handler(commands=["leaderboard"])
def leaderboard_cmd(msg):

    top = leaderboard()

    text = "🏆 TOP PLATYPUS MINERS\n\n"

    if not top:
        text += "No miners yet."
    else:
        for i, (uid, bal) in enumerate(top, 1):
            text += f"{i}. {bal} PLATS\n"

    bot.reply_to(msg, text)

@bot.message_handler(commands=["balance"])
def balance(msg):

    user = str(msg.from_user.id)

    balance = get_balance(user)

    bot.reply_to(
        msg,
        f"💰 Balance\n\n"
        f"{balance} PLATS"
    )

@bot.message_handler(func=lambda m: m.text == "📈 Profile")
@bot.message_handler(commands=["profile"])
def profile(msg):

    user = str(msg.from_user.id)

    balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    reward = f"{PICKAXES[pickaxe]['min']}-{PICKAXES[pickaxe]['max']}"
    cooldown = PICKAXES[pickaxe]["cooldown"] // 60

    bot.reply_to(
        msg,
        f"👤 {msg.from_user.first_name}\n\n"
        f"🏅 Level: {level}\n"
        f"⭐ XP: {xp}/100\n\n"
        f"💰 Balance: {balance} PLATS\n"
        f"⚒️ Pickaxe: {PICKAXES[pickaxe]['name']}\n"
        f"🔥 Daily Streak: {streak} days\n"
        f"💎 Reward: {reward} PLATS\n"
        f"⏳ Cooldown: {cooldown} mins\n\n"
        f"🏆 Wins: {wins}"
    )
    
@bot.message_handler(commands=["buyvip"])
def buyvip(msg):
    bot.reply_to(
        msg,
        "⭐ Telegram Stars payment is coming soon.\n\n"
        "For now contact @ultimateJoey3 to activate VIP."
    )

@bot.message_handler(commands=["activatevip"])
def activate(msg):

    if msg.from_user.id != ADMIN_ID:
        return

    parts = msg.text.split()

    if len(parts) < 2:
        bot.reply_to(msg, "Usage:\n/activatevip USER_ID [plan] [days]")
        return

    user_id = parts[1]
    plan = parts[2] if len(parts) >= 3 else "basic"
    days = int(parts[3]) if len(parts) >= 4 else 30

    from datetime import datetime, timedelta
    expiry = datetime.now() + timedelta(days=days)

    activate_vip_admin(user_id, plan, expiry)

    bot.reply_to(
        msg,
        f"✅ VIP activated for {user_id} — {plan.title()} plan, {days} days."
    )

@bot.message_handler(func=lambda m: m.text=="👤 Account")
def account_btn(msg):
    profile(msg)


@bot.message_handler(func=lambda m: m.text == "💳 Mave Wallet")
def wallet(msg):

    balance = get_balance(str(msg.from_user.id))

    bot.reply_to(
        msg,
        f"💳 Mave Wallet\n\n"
        f"💰 Balance: {balance:,} Plats\n\n"
        f"Choose an option below.",
        reply_markup=wallet_menu()
    )


@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(msg):

    balance = get_balance(str(msg.from_user.id))

    bot.reply_to(
        msg,
        f"💰 Your Wallet\n\n"
        f"🪙 Plats: {balance:,}"
    )

@bot.message_handler(func=lambda m: m.text == "📜 History")
def history(msg):

    bot.reply_to(
        msg,
        "📜 No transactions yet."
    )


@bot.message_handler(func=lambda m: m.text=="💎 VIP")
def vip_btn(msg):
    subscribe(msg)


@bot.message_handler(func=lambda m: m.text=="🏆 Leaderboard")
def leaderboard_btn(msg):
    leaderboard_cmd(msg)


@bot.message_handler(func=lambda m: m.text=="🎁 Daily")
def daily_btn(msg):
    daily(msg)


@bot.message_handler(commands=["daily"])
def daily(msg):
    user = str(msg.from_user.id)

    balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    now = int(time.time())

    cooldown = 86400  # 24 hours

    if now - last_daily < cooldown:
        left = cooldown - (now - last_daily)
        hrs = left // 3600
        mins = (left % 3600) // 60

        bot.reply_to(
            msg,
            f"🎁 You've already claimed today's reward.\n\n"
            f"Come back in {hrs}h {mins}m."
        )
        return

    reward = min(200 + (streak * 50), 500)

    DAY = 86400

    if last_daily == 0:
        streak = 1
    elif now - last_daily <= DAY * 2:
        streak += 1
    else:
        streak = 1

    balance += reward

    update_daily(user, balance, now, streak)

    bot.reply_to(
        msg,
        f"🎁 Daily Reward Claimed!\n\n"
        f"+{reward} PLATS\n"
        f"🔥 Streak: {streak} day(s)"
        f"💳 Balance: {balance} PLATS"
    )


@bot.message_handler(func=lambda m: m.text=="⛏️ Mine")
def mine_btn(msg):
    mine(msg)


@bot.message_handler(func=lambda m: m.text == "📈 Trading")
def trading(msg):

    bot.send_message(
        msg.chat.id,
        "📈 Trading Center\n\nChoose a category.",
        reply_markup=trading_menu()
    )


@bot.message_handler(func=lambda m: m.text=="👥 Refer & Earn")
def refer_btn(msg):

    user_id = str(msg.from_user.id)

    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    total_referrals = get_referral_count(user_id)

    bot.send_message(
        msg.chat.id,
        f"""
👥 <b>Refer &amp; Earn</b>

Invite your friends to MaveConnect and get rewarded every time.

🎁 <b>You earn:</b>
✅ {REFERRAL_BONUS} Plats the moment they join
✅ {int(REFERRAL_DEPOSIT_BONUS_RATE * 100)}% of their first deposit, as a bonus

🎁 <b>They get:</b>
✅ {SIGNUP_BONUS} Plats just for joining with your link

📊 <b>Your Stats</b>
👥 Total Referrals: <b>{total_referrals}</b>

🔗 <b>Your Referral Link:</b>
<code>{referral_link}</code>

Tap and hold the link above to copy it, then share it anywhere!
""",
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda m: m.text=="⚙️ Settings")
def settings_btn(msg):
    bot.reply_to(
        msg,
        "⚙️ Settings\n\n"
        "Coming Soon!"
    )


@bot.message_handler(func=lambda m: m.text == "🏠 Home")
def home_btn(msg):

    bot.send_message(
        msg.chat.id,
        "🏠 Main Menu",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: m.text == "💲 Price")
def price_menu(msg):

    bot.reply_to(
        msg,
        "Send a command like:\n\n"
        "/price btc\n"
        "/price eth\n"
        "/price sol"
    )


@bot.message_handler(func=lambda m: m.text == "🤖 Signal")
def signal_menu(msg):

    bot.reply_to(
        msg,
        "Send a command like:\n\n"
        "/signal btc\n"
        "/signal eth"
    )


@bot.message_handler(func=lambda m: m.text == "📊 Scan")
def scan_menu(msg):
    scan(msg)


@bot.message_handler(func=lambda m: m.text == "🟢 Top Coins")
def topcoins(msg):

    bot.send_message(
        msg.chat.id,
        "💰 Top Coins",
        reply_markup=topcoins_menu()
    )

@bot.message_handler(func=lambda m: m.text in PRICE_BUTTONS)
def coin_price(msg):

    coin = PRICE_BUTTONS[msg.text]

    price =get_price(coin)

    if price is None:
        bot.reply_to(msg, "❌ Price unavailable.")
        return

    bot.reply_to(
        msg,
        f"💰 {coin.upper()}\n\n"
        f"Price: ${price:,.4f}"
    )

@bot.message_handler(func=lambda m: m.text == "🏠 Home")
def home_button(msg):

    bot.send_message(
        msg.chat.id,
        "🏠 Main Menu",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🤖 AI Coins")
def ai_coins(msg):

    bot.send_message(
        msg.chat.id,
        "🤖 AI Coins",
        reply_markup=ai_menu()
    )

@bot.message_handler(func=lambda m: m.text=="📊 Market Dashboard")
def dashboard(msg):

    bot.reply_to(
        msg,
        "📊 Market Dashboard\n\nChoose a category:",
        reply_markup=dashboard_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🏦 DeFi")
def defi(msg):
    bot.send_message(
        msg.chat.id,
        "🏦 Top DeFi Coins",
        reply_markup=defi_menu()
    )
    
@bot.message_handler(func=lambda m: m.text=="💎 RWA")
def rwa(msg):

    text = (
        "💎 Real World Asset Coins\n\n"
        "ONDO\n"
        "LINK\n"
        "POLYX\n"
        "CFG\n"
        "OM\n"
        "MPL"
    )

    bot.reply_to(msg, text)

@bot.message_handler(func=lambda m: m.text == "🔎 Coin Search")
def coin_search(msg):

    search_users.add(msg.from_user.id)

    bot.reply_to(
        msg,
        "🔎 Send a coin symbol.\n\n"
        "Examples:\n"
        "BTC\n"
        "ETH\n"
        "SOL\n"
        "SUI\n"
        "ONDO"
    )

@bot.message_handler(func=lambda m: m.text == "⭐ Favorite")
def favorite_coin(msg):

    coin = current_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ Search a coin first.")
        return

    favorites = get_favorites(str(msg.from_user.id))

    if coin in favorites:
        bot.reply_to(
            msg,
            f"⭐ {coin.upper()} is already in your favorites."
        )
        return

    add_favorite(
        str(msg.from_user.id),
        coin
    )

    bot.reply_to(
        msg,
        f"✅ {coin.upper()} added to favorites."
    )

@bot.message_handler(func=lambda m: m.text == "⭐ Favorites")
def show_favorites(msg):

    coins = get_favorites(str(msg.from_user.id))

    if not coins:
        bot.reply_to(msg, "You don't have any favorite coins yet.")
        return

    text = "⭐ Your Favorite Coins\n\n"

    for coin in coins:
        text += f"• {coin.upper()}\n"

    bot.reply_to(msg, text)
    
@bot.message_handler(func=lambda m: m.text == "🐸 Meme Coins")
def meme_coins(msg):

    bot.send_message(
        msg.chat.id,
        "🐸 Meme Coins",
        reply_markup=memecoins_menu()
    )

@bot.message_handler(func=lambda m: m.text == "⚡ Layer 1")
def layer1(msg):

    bot.send_message(
        msg.chat.id,
        "⚡ Top Layer 1 Coins",
        reply_markup=layer1_menu()
    )

@bot.message_handler(func=lambda m: m.text == "💎 RWA")
def rwa(msg):

    bot.send_message(
        msg.chat.id,
        "💎 Real World Asset (RWA) Coins",
        reply_markup=rwa_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🔍 Search Coin")
def search_coin(msg):

    search_users.add(msg.from_user.id)

    bot.send_message(
        msg.chat.id,
        "🔎 Send a coin symbol.\n\nExamples:\nBTC\nETH\nDOGE\nSUI\nONDO"
    )


@bot.message_handler(func=lambda m: m.from_user.id in search_users)
def search_coin_result(msg):

    search_users.discard(msg.from_user.id)

    coin = msg.text.lower().strip()

    user_last_coin[msg.from_user.id] = coin
    current_coin[msg.from_user.id] = coin

    scan = scan_coin(coin)

    if scan is None:
        bot.reply_to(msg, "❌ Coin not found.")
        return

    if isinstance(scan["rsi"], (int, float)):
        rsi_status = (
           "Oversold 🟢" if scan["rsi"] < 30 else
           "Overbought 🔴" if scan["rsi"] > 70 else
           "Neutral ⚪"
       )
    else:
       rsi_status = "Unavailable"
    
    current_coin[msg.from_user.id] = coin
    
    bot.reply_to(
       msg,
       f"🪙 {scan['coin']} ({scan['symbol']})\n\n"
       f"💰 Price: ${scan['price']:,.6f}\n"
       f"📈 24H: {scan['change24']:.2f}%\n"
       f"🏆 Rank: #{scan['rank']}\n"
       f"💎 Market Cap: ${scan['market_cap']:,.0f}\n"
       f"📊 Volume: ${scan['volume']:,.0f}\n\n"
       f"🤖 AI Analysis\n"
       f"📊 RSI (14): {scan['rsi']} ({rsi_status})\n"
       f"Signal: {scan['signal']}\n"
       f"Strength: {scan['strength']}/100\n"
       f"Trend: {scan['trend']}\n"
       f"Support: ${scan['support']:,.4f}\n"
       f"Resistance: ${scan['resistance']:,.4f}",
       reply_markup=coin_actions()    
    )

#@bot.message_handler(func=lambda m: m.from_user.id in search_users)
#def handle_coin_input(msg):

   # coin = msg.text.upper().strip()

    #user_last_coin[msg.from_user.id] = coin
    #search_users.discard(msg.from_user.id)

   # bot.reply_to(
      #  msg,
       # f"✅ Coin selected: {coin}\n\n"
       # f"You can now use:\n📊 Chart\n📰 News\n🔔 Set Alert"
  #  )
    
@bot.message_handler(func=lambda m: m.text == "📊 Chart")
def chart(msg):

    coin = user_last_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ Open a coin first.")
        return

    bot.reply_to(
        msg,
        f"📈 {coin.upper()} Chart\n\n"
        f"https://www.tradingview.com/symbols/{coin.upper()}USDT/"
    )

@bot.message_handler(func=lambda m: m.text == "📰 News")
def news(msg):

    coin = user_last_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ Open a coin first.")
        return

    articles = get_crypto_news(coin)

    if not articles:
        bot.reply_to(
            msg,
            f"❌ No recent news found for {coin.upper()}."
        )
        return

    text = f"📰 Latest {coin.upper()} News\n\n"

    for article in articles:
        text += (
            f"📰 {article['title']}\n"
            f"🔗 {article['url']}\n\n"
        )

    bot.reply_to(msg, text)
    
@bot.message_handler(func=lambda m: m.text == "⭐ Favorite")
def favorite(msg):
    bot.reply_to(
        msg,
        "⭐ Added to Favorites!"
    )

@bot.message_handler(func=lambda m: m.text == "🔔 Set Alert")
def set_alert(msg):
    coin = user_last_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "Search a coin first.")
        return

    waiting_alert[msg.from_user.id] = coin

    bot.reply_to(
        msg,
        f"Enter the target price for {coin.upper()}.\n\nExample:\n120000"
    )


@bot.message_handler(func=lambda m: m.from_user.id in waiting_alert)
def save_alert(msg):
    coin = waiting_alert.pop(msg.from_user.id)

    try:
        target = float(msg.text)

        add_alert(
            str(msg.from_user.id),
            coin,
            target
        )

        bot.reply_to(
            msg,
            f"✅ Alert set!\n{coin.upper()} → ${target:,.2f}"
        )

    except:
        bot.reply_to(msg, "Invalid price.")

@bot.message_handler(func=lambda m: m.text == "📊 Chart")
def chart(msg):

    coin = user_last_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ View a coin first.")
        return

    symbol = coin.upper()

    bot.reply_to(
        msg,
        f"📈 Live {symbol} Chart\n\n"
        f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}USDT"
)

@bot.message_handler(func=lambda m: m.text == "📰 News")
def news(msg):

    coin = current_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ Open a coin first.")
        return

    bot.reply_to(
        msg,
        f"📰 Fetching the latest news for {coin.upper()}..."
    )

@bot.message_handler(func=lambda m: m.text == "⭐ Favorite")
def favorite(msg):

    coin = current_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ Open a coin first.")
        return

    bot.reply_to(
        msg,
        f"⭐ {coin.upper()} added to your favorites."
    )
    
@bot.message_handler(func=lambda m: m.text == "🔔 Set Alert")
def alert(msg):

    coin = current_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "❌ Open a coin first.")
        return

    bot.reply_to(
        msg,
        f"🔔 Enter the target price for {coin.upper()}."
    )
    
@bot.message_handler(func=lambda m: m.from_user.id in alert_users)
def save_alert(msg):

    alert_users.discard(msg.from_user.id)

    coin = current_coin[msg.from_user.id]

    try:
        target = float(msg.text)

    except ValueError:
        bot.reply_to(msg, "❌ Invalid price.")
        return

    add_alert(
        str(msg.from_user.id),
        coin,
        target
    )

    bot.reply_to(
        msg,
        f"✅ Alert created!\n\n{coin.upper()} → ${target:,.2f}"
    )

@bot.message_handler(func=lambda m: m.text == "🤖 AI Analysis")
def ai_analysis_handler(msg):

    coin = user_last_coin.get(msg.from_user.id)

    if not coin:
        bot.reply_to(msg, "Open a coin first.")
        return

    result = get_ai_analysis(coin)

    if result is None:
        bot.reply_to(msg, "Unable to analyze this coin.")
        return

    bot.reply_to(
        msg,
        f"🤖 AI Analysis for {coin.upper()}\n\n"
        f"📈 Trend: {result['trend']}\n"
        f"🎯 Signal: {result['signal']}\n"
        f"🛡 Risk: {result['risk']}\n"
        f"💪 Confidence: {result['confidence']}%\n\n"
        f"🟢 Support: ${result['support']:,.4f}\n"
        f"🔴 Resistance: ${result['resistance']:,.4f}"
    )

# ================= ALERTS =================

def alert_checker():

    while True:

        try:
            for user, coin, target in get_alerts():

                price = get_price(coin)

                if price is None:
                    continue

                if price >= target:

                    bot.send_message(
                        int(user),
                        f"🚨 Price Alert!\n\n"
                        f"{coin.upper()} has reached ${price:,.2f}\n"
                        f"Target: ${target:,.2f}"
                    )

                    delete_alert(user, coin, target)

        except Exception as e:
            print(f"Alert Checker Error: {e}")

        time.sleep(60)
        
def reminder_checker():

    while True:

        try:
            for user_id in get_users_needing_daily_reminder():

                try:
                    bot.send_message(
                        int(user_id),
                        "🎁 Your daily bonus is ready to claim!\n\n"
                        "Open 🎮 Games → 🎁 Daily Bonus to grab it before you lose your streak."
                    )
                except Exception:
                    pass

                mark_reminder_sent(user_id, "daily")

        except Exception as e:
            print(f"Daily Reminder Error: {e}")

        try:
            for stake_id, user_id, amount, reward in get_newly_matured_stakes():

                try:
                    bot.send_message(
                        int(user_id),
                        f"🎉 Your stake #{stake_id} has matured!\n\n"
                        f"💰 {amount:,.0f} Plats + {reward:,.0f} Plats reward is ready to claim.\n\n"
                        f"Open 💳 Mave Wallet → 📈 Staking → 📊 My Stakes to claim it."
                    )
                except Exception:
                    pass

                mark_stake_notified(stake_id)

        except Exception as e:
            print(f"Stake Reminder Error: {e}")

        time.sleep(900)


def build_daily_insight_message():

    lines = ["👑 <b>MaveConnect VIP Daily Crypto Insights</b>\n"]

    any_data = False

    for symbol in DAILY_INSIGHT_COINS:

        result = get_signal(symbol)

        if not result:
            continue

        any_data = True
        change = result["change"]
        arrow = "🟢 ▲" if change >= 0 else "🔴 ▼"

        lines.append(
            f"<b>{symbol.upper()}</b> — ${result['price']:,.2f}  {arrow} {change:+.2f}%\n"
            f"   {result['action']} • Strength {result['score']}/100"
        )

    if not any_data:
        return None

    lines.append("\n💡 Not financial advice — always do your own research.")
    lines.append("👑 Exclusive to MaveConnect VIP")

    return "\n".join(lines)


def daily_insight_checker():

    last_posted_date = None

    while True:

        try:
            if VIP_GROUP_CHAT_ID:
                now = datetime.now()

                if now.hour == DAILY_INSIGHT_HOUR and last_posted_date != now.date():

                    message_text = build_daily_insight_message()

                    if message_text:
                        bot.send_message(VIP_GROUP_CHAT_ID, message_text, parse_mode="HTML")
                        last_posted_date = now.date()

        except Exception as e:
            print(f"Daily Insight Error: {e}")

        time.sleep(60)


# ================= COMMANDS =================

@bot.message_handler(commands=["debug"])
def debug(msg):
    bot.reply_to(msg, "✅ Debug command works")


# ================= FALLBACK =================

@bot.message_handler(func=lambda m: m.chat.type == "private")
def unknown(msg):
    bot.reply_to(
        msg,
        "❓ Unknown command.\n\n"
        "Use one of these commands:\n\n"
        "/price btc\n"
        "/signal btc\n"
        "/scan\n"
        "/mine\n"
        "/balance\n"
        "/leaderboard\n"
        "/daily\n"
        "/subscribe\n"
        "/help\n"
        "/ping\n"
        "/test"
    )

# ================= BOT LOOP =================

def run_bot():
    while True:
        try:
            print("Polling started...")

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30,
                allowed_updates=["message", "callback_query"]
            )

        except Exception as e:
            print("POLLING CRASH:", repr(e))

            if "409" in str(e):
                print("⚠️ Another instance is using this token")

            time.sleep(5)

# ================= START =================

if __name__ == "__main__":
    print("Starting application...")

    try:
        bot.delete_webhook(drop_pending_updates=True)
        bot.remove_webhook()

        me = bot.get_me()
        print(f"Connected as @{me.username}")
        bot.send_message(6384391560, "✅ Bot restarted successfully")

    except Exception as e:
        print("Startup error:", repr(e))

    # Start alert checker
    Thread(target=alert_checker, daemon=True).start()
    Thread(target=reminder_checker, daemon=True).start()
    Thread(target=daily_insight_checker, daemon=True).start()
    
    print("Alert checker started")

    # Start Telegram bot
    Thread(target=run_bot, daemon=True).start()

    print("Bot thread started")

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
