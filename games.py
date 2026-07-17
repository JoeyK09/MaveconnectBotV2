import random
import time
from datetime import datetime

from keyboards import main_menu
from games_keyboard import games_menu

from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from database import (
    get_balance,
    get_profile,
    add_plats,
    remove_plats,
    add_win,
    leaderboard,
    save_game_history,
    get_game_history,
    update_daily,
    update_pickaxe,
    get_luck_points,
    add_luck_points,
    remove_luck_points,
    convert_plats_to_luck
)

from config import PICKAXES
from collectibles import maybe_drop_collectible

# ===============USER STATE ==============================

game_states = {}


# ============================================
# SHARED KEYBOARDS
# ============================================

def back_only_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔙 Back"))
    return markup


def coinflip_choice_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        KeyboardButton("🟡 Heads"),
        KeyboardButton("⚪ Tails")
    )
    markup.row(KeyboardButton("🔙 Back"))
    return markup


# ============================================
# REGISTER ALL GAME HANDLERS
# ============================================

def register_game_handlers(bot):

    # ==========================================
    # GAMES MENU
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎮 Games")
    def open_games(message):

        user_id = str(message.from_user.id)

        get_profile(user_id)

        balance = get_balance(user_id)
        luck = get_luck_points(user_id)

        bot.send_message(
            message.chat.id,
            f"""
🎮 <b>Welcome to MaveConnect Games!</b>

💰 <b>Plats Balance:</b> <code>{balance:,}</code>
🎫 <b>Luck Points:</b> <code>{luck:,}</code>

━━━━━━━━━━━━━━━━━━━

🎲 <b>Available Games</b>  (played with 🎫 Luck Points — for fun, not cashable)

🪙 Coin Flip
🎲 Dice Roll
🎰 Slot Machine
🎯 Lucky Number

━━━━━━━━━━━━━━━━━━━

🎫 Out of Luck Points? Convert Plats → Luck Points below.
🥇 Climb the Leaderboard
📜 View Game History

👇 <b>Select a game below.</b>
""",
            parse_mode="HTML",
            reply_markup=games_menu()
        )

    # ==========================================
    # BACK BUTTON
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🔙 Back")
    def games_back_button(message):

        game_states.pop(message.from_user.id, None)

        bot.send_message(
            message.chat.id,
            "🏠 Main Menu",
            reply_markup=main_menu()
        )

    # ==========================================
    # CONVERT PLATS -> LUCK POINTS (one-way, bonus rate)
    # ==========================================

    LUCK_CONVERSION_RATE = 1.5  # 1 Plat -> 1.5 Luck Points, one-way only

    @bot.message_handler(func=lambda m: m.text == "🎫 Convert Plats → Luck Points")
    def convert_start(message):

        user_id = str(message.from_user.id)
        balance = get_balance(user_id)
        luck = get_luck_points(user_id)

        if balance <= 0:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("💵 Buy Plats (M-Pesa)"))
            markup.row(KeyboardButton("🔙 Back"))
            bot.send_message(
                message.chat.id,
                "❌ You don't have any Plats to convert.",
                reply_markup=markup
            )
            return

        bot.send_message(
            message.chat.id,
            f"""
🎫 <b>Convert Plats → Luck Points</b>

💰 Plats Balance: <code>{balance:,}</code>
🎫 Luck Points: <code>{luck:,}</code>

Rate: 1 Plat → {LUCK_CONVERSION_RATE} Luck Points
⚠️ This is one-way — Luck Points can't be converted back to Plats or cashed out.

Enter how many Plats you'd like to convert.
""",
            parse_mode="HTML",
            reply_markup=back_only_keyboard()
        )

        bot.register_next_step_handler(message, convert_amount)

    def convert_amount(message):

        if message.text == "🔙 Back":
            games_back_button(message)
            return

        user_id = str(message.from_user.id)

        try:
            amount = int(message.text.replace(",", "").strip())
        except (ValueError, AttributeError):
            bot.send_message(message.chat.id, "❌ Please enter a valid number.")
            bot.register_next_step_handler(message, convert_amount)
            return

        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Enter an amount greater than 0.")
            bot.register_next_step_handler(message, convert_amount)
            return

        balance = get_balance(user_id)

        if amount > balance:
            bot.send_message(message.chat.id, f"❌ You only have {balance:,} Plats.")
            bot.register_next_step_handler(message, convert_amount)
            return

        luck_awarded = int(amount * LUCK_CONVERSION_RATE)
        convert_plats_to_luck(user_id, amount, luck_awarded)

        new_balance = get_balance(user_id)
        new_luck = get_luck_points(user_id)

        bot.send_message(
            message.chat.id,
            f"""
✅ Converted {amount:,} Plats → {luck_awarded:,} Luck Points!

💰 Plats Balance: <code>{new_balance:,}</code>
🎫 Luck Points: <code>{new_luck:,}</code>
""",
            parse_mode="HTML",
            reply_markup=games_menu()
        )

    # ==========================================
    # SHARED BET COLLECTION HELPER
    # ==========================================

    def ask_for_bet(message, game_name, resolver, min_bet=10, max_bet=100000):
        """Sends the balance/bet prompt and queues up the next-step resolver.
        Games are played with Luck Points — a separate, non-cashable
        currency — not real Plats."""

        user_id = message.from_user.id
        get_profile(user_id)
        luck = get_luck_points(user_id)

        if luck < min_bet:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("🎫 Convert Plats → Luck Points"))
            markup.row(KeyboardButton("🔙 Back"))

            bot.send_message(
                message.chat.id,
                f"""
❌ You need at least {min_bet:,} 🎫 Luck Points to play.

🎫 You have: {luck:,} Luck Points

Convert some Plats into Luck Points below 👇
""",
                reply_markup=markup
            )
            return

        bot.send_message(
            message.chat.id,
            f"""
{game_name}

🎫 Luck Points: <code>{luck:,}</code>

Enter the amount you want to bet.

<b>Minimum Bet:</b> {min_bet:,} Luck Points
<b>Maximum Bet:</b> {max_bet:,} Luck Points
""",
            parse_mode="HTML",
            reply_markup=back_only_keyboard()
        )

        bot.register_next_step_handler(message, collect_bet, resolver, min_bet, max_bet)

    def collect_bet(message, resolver, min_bet, max_bet):

        if message.text == "🔙 Back":
            games_back_button(message)
            return

        user_id = message.from_user.id

        try:
            bet = int(message.text.replace(",", "").strip())
        except (ValueError, AttributeError):
            bot.send_message(message.chat.id, "❌ Please enter a valid number.")
            bot.register_next_step_handler(message, collect_bet, resolver, min_bet, max_bet)
            return

        if bet < min_bet:
            bot.send_message(message.chat.id, f"❌ Minimum bet is {min_bet:,} Luck Points.")
            bot.register_next_step_handler(message, collect_bet, resolver, min_bet, max_bet)
            return

        if bet > max_bet:
            bot.send_message(message.chat.id, f"❌ Maximum bet is {max_bet:,} Luck Points.")
            bot.register_next_step_handler(message, collect_bet, resolver, min_bet, max_bet)
            return

        luck = get_luck_points(user_id)

        if bet > luck:
            bot.send_message(message.chat.id, f"❌ You only have {luck:,} Luck Points.")
            bot.register_next_step_handler(message, collect_bet, resolver, min_bet, max_bet)
            return

        resolver(message, bet)

    def finish_game(message, game_name, bet, won, reward, result_text):
        """Applies Luck Points changes, records history, and reports the outcome.
        Luck Points only — never touches real Plats balance."""

        user_id = message.from_user.id

        remove_luck_points(user_id, bet)

        if won:
            add_luck_points(user_id, reward)
            add_win(user_id)

        new_luck = get_luck_points(user_id)

        save_game_history(
            user_id,
            game_name,
            bet,
            reward if won else 0,
            "win" if won else "loss"
        )

        bot.send_message(
            message.chat.id,
            f"""
{result_text}

🎫 New Luck Points: <code>{new_luck:,}</code>
""",
            parse_mode="HTML",
            reply_markup=games_menu()
        )

    # ==========================================
    # COIN FLIP
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🪙 Coin Flip")
    def start_coinflip(message):
        ask_for_bet(message, "🪙 <b>Coin Flip</b>", resolve_coinflip)

    def resolve_coinflip(message, bet):

        game_states[message.from_user.id] = {"game": "coinflip", "bet": bet}

        bot.send_message(
            message.chat.id,
            f"""
🪙 <b>Coin Flip</b>

Bet: <code>{bet:,}</code> Luck Points

Choose your side.
""",
            parse_mode="HTML",
            reply_markup=coinflip_choice_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text in ["🟡 Heads", "⚪ Tails"])
    def coinflip_choice(message):

        user_id = message.from_user.id
        state = game_states.get(user_id)

        if not state or state.get("game") != "coinflip":
            return

        bet = state["bet"]
        game_states.pop(user_id, None)

        choice = "heads" if message.text == "🟡 Heads" else "tails"
        outcome = random.choice(["heads", "tails"])
        won = choice == outcome

        outcome_emoji = "🟡 Heads" if outcome == "heads" else "⚪ Tails"

        if won:
            reward = bet * 2
            text = f"🎉 The coin landed on {outcome_emoji}!\n\n✅ You won <code>{reward:,}</code> Luck Points!"
        else:
            reward = 0
            text = f"😢 The coin landed on {outcome_emoji}.\n\n❌ You lost <code>{bet:,}</code> Luck Points."

        finish_game(message, "Coin Flip", bet, won, reward, text)

    # ==========================================
    # DICE ROLL
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎲 Dice Roll")
    def start_dice(message):
        ask_for_bet(message, "🎲 <b>Dice Roll</b>\n\nGuess the number (1-6). Match it to win 5x!", resolve_dice_bet)

    def resolve_dice_bet(message, bet):
        game_states[message.from_user.id] = {"game": "dice", "bet": bet}

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3"))
        markup.row(KeyboardButton("4"), KeyboardButton("5"), KeyboardButton("6"))
        markup.row(KeyboardButton("🔙 Back"))

        bot.send_message(
            message.chat.id,
            f"🎲 Bet: <code>{bet:,}</code> Luck Points\n\nPick a number from 1 to 6.",
            parse_mode="HTML",
            reply_markup=markup
        )

        bot.register_next_step_handler(message, dice_guess)

    def dice_guess(message):

        user_id = message.from_user.id
        state = game_states.get(user_id)

        if message.text == "🔙 Back":
            games_back_button(message)
            return

        if not state or state.get("game") != "dice":
            return

        if message.text not in ["1", "2", "3", "4", "5", "6"]:
            bot.send_message(message.chat.id, "❌ Please pick a number between 1 and 6.")
            bot.register_next_step_handler(message, dice_guess)
            return

        bet = state["bet"]
        game_states.pop(user_id, None)

        guess = int(message.text)
        roll = random.randint(1, 6)
        won = guess == roll

        if won:
            reward = bet * 5
            text = f"🎲 The dice rolled a {roll}!\n\n✅ You guessed right and won <code>{reward:,}</code> Luck Points!"
        else:
            reward = 0
            text = f"🎲 The dice rolled a {roll}.\n\n❌ You guessed {guess} — you lost <code>{bet:,}</code> Luck Points."

        finish_game(message, "Dice Roll", bet, won, reward, text)

    # ==========================================
    # SLOT MACHINE
    # ==========================================

    SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "💎", "7️⃣"]

    @bot.message_handler(func=lambda m: m.text == "🎰 Slot Machine")
    def start_slots(message):
        ask_for_bet(message, "🎰 <b>Slot Machine</b>\n\n3 matching symbols = 10x. 2 matching = 2x.", resolve_slots)

    def resolve_slots(message, bet):

        spin = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        display = " | ".join(spin)

        if spin[0] == spin[1] == spin[2]:
            reward = bet * 10
            won = True
            text = f"🎰 {display}\n\n🎉 JACKPOT! All three match!\n\n✅ You won <code>{reward:,}</code> Luck Points!"
        elif spin[0] == spin[1] or spin[1] == spin[2] or spin[0] == spin[2]:
            reward = bet * 2
            won = True
            text = f"🎰 {display}\n\n✅ Two matched! You won <code>{reward:,}</code> Luck Points!"
        else:
            reward = 0
            won = False
            text = f"🎰 {display}\n\n❌ No match. You lost <code>{bet:,}</code> Luck Points."

        finish_game(message, "Slot Machine", bet, won, reward, text)

    # ==========================================
    # LUCKY NUMBER
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎯 Lucky Number")
    def start_lucky(message):
        ask_for_bet(message, "🎯 <b>Lucky Number</b>\n\nGuess a number 1-10. Correct guess pays 8x!", resolve_lucky_bet)

    def resolve_lucky_bet(message, bet):
        game_states[message.from_user.id] = {"game": "lucky", "bet": bet}

        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=5)
        markup.add(*[KeyboardButton(str(n)) for n in range(1, 11)])
        markup.row(KeyboardButton("🔙 Back"))

        bot.send_message(
            message.chat.id,
            f"🎯 Bet: <code>{bet:,}</code> Luck Points\n\nPick a number from 1 to 10.",
            parse_mode="HTML",
            reply_markup=markup
        )

        bot.register_next_step_handler(message, lucky_guess)

    def lucky_guess(message):

        user_id = message.from_user.id
        state = game_states.get(user_id)

        if message.text == "🔙 Back":
            games_back_button(message)
            return

        if not state or state.get("game") != "lucky":
            return

        if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
            bot.send_message(message.chat.id, "❌ Please pick a number between 1 and 10.")
            bot.register_next_step_handler(message, lucky_guess)
            return

        bet = state["bet"]
        game_states.pop(user_id, None)

        guess = int(message.text)
        winning_number = random.randint(1, 10)
        won = guess == winning_number

        if won:
            reward = bet * 8
            text = f"🎯 The lucky number was {winning_number}!\n\n✅ You guessed right and won <code>{reward:,}</code> Luck Points!"
        else:
            reward = 0
            text = f"🎯 The lucky number was {winning_number}.\n\n❌ You guessed {guess} — you lost <code>{bet:,}</code> Luck Points."

        finish_game(message, "Lucky Number", bet, won, reward, text)

    # ==========================================
    # JACKPOT (high risk, high reward)
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎉 Jackpot")
    def start_jackpot(message):
        ask_for_bet(
            message,
            "🎉 <b>Jackpot</b>\n\nHigh risk, high reward. 15% chance to win 6x your bet.",
            resolve_jackpot,
            min_bet=50
        )

    def resolve_jackpot(message, bet):

        won = random.random() < 0.15

        if won:
            reward = bet * 6
            text = f"🎉 JACKPOT! You won <code>{reward:,}</code> Luck Points!"
        else:
            reward = 0
            text = f"😢 No jackpot this time. You lost <code>{bet:,}</code> Luck Points."

        finish_game(message, "Jackpot", bet, won, reward, text)

    # ==========================================
    # DAILY BONUS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎁 Daily Bonus")
    def daily_bonus(message):

        user_id = message.from_user.id
        balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user_id)

        now = int(time.time())
        seconds_in_day = 86400

        if last_daily and now - last_daily < seconds_in_day:
            remaining = seconds_in_day - (now - last_daily)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60

            bot.send_message(
                message.chat.id,
                f"⏳ You've already claimed today's bonus.\n\nCome back in {hours}h {minutes}m."
            )
            return

        # Reset streak if more than 48h have passed since the last claim
        if last_daily and now - last_daily > seconds_in_day * 2:
            streak = 0

        streak += 1
        reward = 50 + min(streak, 30) * 10

        new_balance = balance + reward

        update_daily(user_id, new_balance, now, streak)

        save_game_history(user_id, "Daily Bonus", 0, reward, "win")

        bot.send_message(
            message.chat.id,
            f"""
🎁 <b>Daily Bonus Claimed!</b>

✅ Reward: <code>{reward:,}</code> Plats
🔥 Streak: {streak} days

💰 New Balance: <code>{new_balance:,}</code> Plats
""",
            parse_mode="HTML"
        )

        maybe_drop_collectible(bot, user_id)

    # ==========================================
    # GAME HISTORY
    # ==========================================

    @bot.message_handler(func=lambda m: m.text in ["📜 History", "📜 Game History"])
    def game_history(message):

        rows = get_game_history(message.from_user.id)

        if not rows:
            bot.send_message(message.chat.id, "📜 You haven't played any games yet.")
            return

        lines = ["📜 <b>Your Recent Games</b>\n"]

        for game_name, bet, reward, result, played_at in rows:
            icon = "✅" if result == "win" else "❌"
            unit = "Plats" if game_name == "Daily Bonus" else "Luck Points"
            lines.append(
                f"{icon} {game_name} • Bet {bet:,} • "
                f"{'+' + format(reward, ',') if result == 'win' else '-' + format(bet, ',')} {unit} "
                f"• {played_at:%Y-%m-%d %H:%M}"
            )

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML"
        )

    # ==========================================
    # MINING SHOP
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🛒 Mining Shop")
    def mining_shop(message):

        user_id = message.from_user.id
        balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user_id)

        lines = [
            "🛒 <b>Mining Shop</b>\n",
            f"💰 Balance: <code>{balance:,}</code> Plats",
            f"⚒️ Current Pickaxe: {PICKAXES[pickaxe]['name']}\n"
        ]

        markup = ReplyKeyboardMarkup(resize_keyboard=True)

        for pid, data in PICKAXES.items():
            owned = " (Owned)" if pid <= pickaxe else ""
            lines.append(f"{data['name']} — {data['price']:,} Plats{owned}")

            if pid > pickaxe:
                markup.row(KeyboardButton(f"Buy {data['name']}"))

        markup.row(KeyboardButton("🔙 Back"))

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=markup
        )

        bot.register_next_step_handler(message, buy_pickaxe)

    def buy_pickaxe(message):

        if message.text == "🔙 Back":
            games_back_button(message)
            return

        user_id = message.from_user.id
        balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user_id)

        target_id = None
        for pid, data in PICKAXES.items():
            if message.text == f"Buy {data['name']}":
                target_id = pid
                break

        if target_id is None:
            bot.send_message(message.chat.id, "❌ Please choose a pickaxe from the shop.")
            return

        if target_id <= pickaxe:
            bot.send_message(message.chat.id, "✅ You already own this pickaxe or better.")
            return

        price = PICKAXES[target_id]["price"]

        if balance < price:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("💵 Buy Plats (M-Pesa)"))
            markup.row(KeyboardButton("🔙 Back"))

            bot.send_message(
                message.chat.id,
                f"""
❌ You need {price:,} Plats for {PICKAXES[target_id]['name']}.

💰 You have: {balance:,} Plats
💸 You're short: {price - balance:,} Plats

Top up instantly with M-Pesa 👇
""",
                reply_markup=markup
            )
            return

        new_balance = balance - price
        update_pickaxe(user_id, new_balance, target_id)

        bot.send_message(
            message.chat.id,
            f"""
✅ <b>Purchased {PICKAXES[target_id]['name']}!</b>

💰 New Balance: <code>{new_balance:,}</code> Plats
""",
            parse_mode="HTML",
            reply_markup=games_menu()
        )
