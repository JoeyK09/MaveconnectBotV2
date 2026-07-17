from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def games_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("🪙 Coin Flip"),
        KeyboardButton("🎲 Dice Roll")
    )

    markup.row(
        KeyboardButton("🎰 Slot Machine"),
        KeyboardButton("🎯 Lucky Number")
    )

    markup.row(
        KeyboardButton("🎫 Convert Plats → Luck Points")
    )

    markup.row(
        KeyboardButton("🎁 Daily Bonus"),
        KeyboardButton("🏆 Leaderboard")
    )

    markup.row(
        KeyboardButton("📜 Game History"),
        KeyboardButton("🔙 Back")
    )

    markup.row(
        KeyboardButton("🏆 Predictions")
    )

    return markup
