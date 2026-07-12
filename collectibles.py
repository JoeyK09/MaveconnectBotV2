import random

from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from database import (
    get_balance,
    remove_plats,
    get_user_collectibles,
    owns_collectible,
    grant_collectible
)

from keyboards import main_menu

# ============================================
# COLLECTIBLE CATALOG
# Cosmetic-only — profile flair, not a financial asset. No resale, no
# secondary market, no claim of value. Just fun stuff to collect.
# ============================================

RARITY_STYLE = {
    "common":    {"emoji": "⚪", "label": "Common"},
    "rare":      {"emoji": "🔵", "label": "Rare"},
    "epic":      {"emoji": "🟣", "label": "Epic"},
    "legendary": {"emoji": "🟡", "label": "Legendary"},
}

COLLECTIBLES = {
    1: {"name": "Bronze Miner Badge",     "rarity": "common",    "price": 200,   "icon": "🥉"},
    2: {"name": "Silver Miner Badge",     "rarity": "rare",      "price": 800,   "icon": "🥈"},
    3: {"name": "Lucky Four-Leaf Charm",  "rarity": "rare",      "price": 1000,  "icon": "🍀"},
    4: {"name": "Golden Pickaxe Skin",    "rarity": "epic",      "price": 2500,  "icon": "🏆"},
    5: {"name": "Diamond Crown",          "rarity": "legendary", "price": 10000, "icon": "👑"},
    6: {"name": "Phoenix Wings",          "rarity": "legendary", "price": 15000, "icon": "🔥"},
}

# Items eligible for a small free chance on Daily Bonus claim (common/rare
# only — legendary/epic stay purchase-only or special-event-only so they
# keep meaning).
DAILY_DROP_POOL = [1, 2, 3]
DAILY_DROP_CHANCE = 0.05  # 5% per claim


def collectibles_menu_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🎒 My Collection"))
    markup.row(KeyboardButton("🛍️ Collectibles Shop"))
    markup.row(KeyboardButton("🔙 Back"))
    return markup


def maybe_drop_collectible(bot, user_id):
    """Call this after a Daily Bonus claim — small chance of a free item."""

    if random.random() > DAILY_DROP_CHANCE:
        return

    candidates = [i for i in DAILY_DROP_POOL if not owns_collectible(user_id, i)]

    if not candidates:
        return

    item_id = random.choice(candidates)
    item = COLLECTIBLES[item_id]

    if grant_collectible(user_id, item_id):
        style = RARITY_STYLE[item["rarity"]]

        try:
            bot.send_message(
                int(user_id),
                f"""
🎉 <b>Bonus Drop!</b>

You found a collectible in today's daily bonus:

{item['icon']} <b>{item['name']}</b>
{style['emoji']} {style['label']}

Check it out in 🎒 My Collection!
""",
                parse_mode="HTML"
            )
        except Exception:
            pass


def register_collectible_handlers(bot):

    @bot.message_handler(func=lambda m: m.text == "🎨 Collectibles")
    def collectibles_intro(message):
        bot.send_message(
            message.chat.id,
            """
🎨 <b>MaveConnect Collectibles</b>

Collect rare badges, skins, and charms to show off on your profile.

🛍️ Buy them in the shop, or earn a lucky drop from your Daily Bonus.

⚪ Common · 🔵 Rare · 🟣 Epic · 🟡 Legendary
""",
            parse_mode="HTML",
            reply_markup=collectibles_menu_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "🔙 Back")
    def collectibles_back(message):
        bot.send_message(message.chat.id, "🏠 Main Menu", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: m.text == "🎒 My Collection")
    def my_collection(message):

        user_id = message.from_user.id
        owned = get_user_collectibles(user_id)

        if not owned:
            bot.send_message(
                message.chat.id,
                "🎒 Your collection is empty. Visit 🛍️ Collectibles Shop to get started!"
            )
            return

        lines = ["🎒 <b>Your Collection</b>\n"]

        for item_id, obtained_at in owned:
            item = COLLECTIBLES.get(item_id)
            if not item:
                continue
            style = RARITY_STYLE[item["rarity"]]
            lines.append(f"{item['icon']} <b>{item['name']}</b> — {style['emoji']} {style['label']}")

        lines.append(f"\n📦 Total: {len(owned)}/{len(COLLECTIBLES)} items")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: m.text == "🛍️ Collectibles Shop")
    def collectibles_shop(message):

        user_id = message.from_user.id
        balance = get_balance(user_id)

        lines = [f"🛍️ <b>Collectibles Shop</b>\n\n💰 Balance: {balance:,.0f} Plats\n"]
        markup = ReplyKeyboardMarkup(resize_keyboard=True)

        for item_id, item in COLLECTIBLES.items():
            style = RARITY_STYLE[item["rarity"]]
            owned = owns_collectible(user_id, item_id)

            status = " ✅ Owned" if owned else f" — {item['price']:,} Plats"
            lines.append(f"{item['icon']} <b>{item['name']}</b> ({style['emoji']} {style['label']}){status}")

            if not owned:
                markup.row(KeyboardButton(f"Buy {item['name']}"))

        markup.row(KeyboardButton("🔙 Back"))

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.message_handler(func=lambda m: any(m.text == f"Buy {item['name']}" for item in COLLECTIBLES.values()))
    def buy_collectible(message):

        user_id = message.from_user.id

        item_id = next(
            (iid for iid, item in COLLECTIBLES.items() if message.text == f"Buy {item['name']}"),
            None
        )

        if item_id is None:
            return

        item = COLLECTIBLES[item_id]

        if owns_collectible(user_id, item_id):
            bot.send_message(message.chat.id, "✅ You already own this item.")
            return

        balance = get_balance(user_id)

        if balance < item["price"]:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("💵 Buy Plats (M-Pesa)"))
            markup.row(KeyboardButton("🔙 Back"))

            bot.send_message(
                message.chat.id,
                f"""
❌ You need {item['price']:,} Plats for {item['name']}.

💰 You have: {balance:,.0f} Plats

Top up with M-Pesa 👇
""",
                reply_markup=markup
            )
            return

        remove_plats(user_id, item["price"])
        grant_collectible(user_id, item_id)

        style = RARITY_STYLE[item["rarity"]]

        bot.send_message(
            message.chat.id,
            f"""
🎉 <b>Purchased!</b>

{item['icon']} <b>{item['name']}</b>
{style['emoji']} {style['label']}

It's now in your 🎒 Collection.
""",
            parse_mode="HTML",
            reply_markup=collectibles_menu_keyboard()
        )
