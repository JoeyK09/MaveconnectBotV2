from telebot.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        KeyboardButton("📈 Trading"),
        KeyboardButton("⛏️ Mine")
    )

    markup.row(
        KeyboardButton("💳 Mave Wallet"),
        KeyboardButton("👑 VIP MEMBERSHIP")
    )

    markup.row(
        KeyboardButton("💵 Buy Plats"),
        KeyboardButton("💸 Redeem Plats")
    )

    markup.row(
        KeyboardButton("👥 Refer & Earn"),
        KeyboardButton("🎁 Daily")
    )

    markup.row(
        KeyboardButton("👤 Account"),
        KeyboardButton("🏆 Leaderboard")
    )

    markup.row(
        KeyboardButton("🎮 Games"),
        KeyboardButton("⚙️ Settings")
    )

    markup.row(
        KeyboardButton("📈 Staking"),
        KeyboardButton("➖ Withdraw")
    )

    markup.row(
        KeyboardButton("🎨 Collectibles")
    )

    markup.row(
        KeyboardButton("🤝 Partners"),
        KeyboardButton("🎁 USDT Airdrop")
    )

    return markup
