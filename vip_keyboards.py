from telebot import types


def vip_menu():

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row("📋 View Plans")
    kb.row("📅 My Subscription", "🎁 VIP Benefits")
    kb.row("👥 VIP Channel", "📜 Payment History")
    kb.row("🔄 Renew VIP")
    kb.row("🔙 Back")

    return kb


def vip_plans_keyboard():

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row("🥉 Basic • KSh299")
    markup.row("🥈 Premium • KSh799")
    markup.row("🥇 Elite • KSh2499")

    markup.row("🔙 Back")

    return markup


from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def payment_keyboard():

    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row(
        KeyboardButton("🇰🇪 M-Pesa")
    )

    kb.row(
        KeyboardButton("💵 USDT (TRC20)")
    )

    kb.row(
        KeyboardButton("💵 USDT (BEP20)")
    )

    kb.row(
        KeyboardButton("₿ Bitcoin")
    )

    kb.row(
        KeyboardButton("♦ Ethereum")
    )

    kb.row(
        KeyboardButton("🔙 Back")
    )

    return kb
    
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def mpesa_paid_keyboard():

    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row(
        KeyboardButton("✅ I've Paid")
    )

    kb.row(
        KeyboardButton("🔙 Back")
    )

    return kb
