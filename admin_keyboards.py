from telebot import types

def admin_menu():

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row("💳 Pending Payments", "👥 VIP Members")
    markup.row("📊 Statistics", "💰 Withdrawals")
    markup.row("📢 Broadcast", "⚙ VIP Settings")
    markup.row("🔙 Back")

    return markup
