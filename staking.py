from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from database import (
    get_balance,
    get_profile,
    create_stake,
    get_user_stakes,
    claim_stake
)

from keyboards import main_menu

# ============================================
# STAKING PLANS
# Returns are the TOTAL payout for the whole term (not annualized).
# Kept conservative on purpose: Plats can be bought with real money and
# withdrawn, so staking rewards are a real liability, not just points.
# ============================================

STAKE_PLANS = {
    1: {"days": 3,  "rate": 0.01,  "label": "3 Days — 1% return"},
    2: {"days": 7,  "rate": 0.025, "label": "7 Days — 2.5% return"},
    3: {"days": 30, "rate": 0.08,  "label": "30 Days — 8% return"},
}

MIN_STAKE = 100
MAX_STAKE = 20000

stake_state = {}


def staking_menu_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📈 New Stake"))
    markup.row(KeyboardButton("📊 My Stakes"))
    markup.row(KeyboardButton("🔙 Back"))
    return markup


def plans_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for pid, plan in STAKE_PLANS.items():
        markup.row(KeyboardButton(plan["label"]))
    markup.row(KeyboardButton("🔙 Back"))
    return markup


def back_only_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🔙 Back"))
    return markup


def register_staking_handlers(bot):

    @bot.message_handler(func=lambda m: m.text == "📈 Staking")
    def staking_menu(message):

        user_id = str(message.from_user.id)
        get_profile(user_id)
        balance = get_balance(user_id)

        bot.send_message(
            message.chat.id,
            f"""
📈 <b>MaveConnect Staking</b>

💰 Balance: <code>{balance:,}</code> Plats

Lock up your Plats for a fixed term and earn a guaranteed return when it matures.

⚠️ Staked Plats are locked until the term ends — you can't use or withdraw them early.
""",
            parse_mode="HTML",
            reply_markup=staking_menu_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "🔙 Back")
    def staking_back(message):
        stake_state.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🏠 Main Menu", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: m.text == "📈 New Stake")
    def new_stake(message):

        lines = ["📈 <b>Choose a Staking Plan</b>\n"]

        for pid, plan in STAKE_PLANS.items():
            lines.append(f"• {plan['label']}")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=plans_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text in [p["label"] for p in STAKE_PLANS.values()])
    def plan_selected(message):

        user_id = message.from_user.id

        plan = next(p for p in STAKE_PLANS.values() if p["label"] == message.text)

        stake_state[user_id] = {"days": plan["days"], "rate": plan["rate"]}

        balance = get_balance(user_id)

        msg = bot.send_message(
            message.chat.id,
            f"""
💰 Balance: <code>{balance:,}</code> Plats

How many Plats would you like to stake for {plan['days']} days?
""",
            parse_mode="HTML",
            reply_markup=back_only_keyboard()
        )

        bot.register_next_step_handler(msg, collect_stake_amount)

    def collect_stake_amount(message):

        user_id = message.from_user.id

        if message.text == "🔙 Back":
            stake_state.pop(user_id, None)
            staking_menu(message)
            return

        state = stake_state.get(user_id)

        if not state:
            return

        try:
            amount = int(message.text.replace(",", "").strip())
        except (ValueError, AttributeError):
            msg = bot.reply_to(message, "❌ Please enter a valid whole number.")
            bot.register_next_step_handler(msg, collect_stake_amount)
            return

        if amount < MIN_STAKE:
            msg = bot.reply_to(message, f"❌ Minimum stake is {MIN_STAKE:,} Plats.")
            bot.register_next_step_handler(msg, collect_stake_amount)
            return

        if amount > MAX_STAKE:
            msg = bot.reply_to(message, f"❌ Maximum stake per lock is {MAX_STAKE:,} Plats.")
            bot.register_next_step_handler(msg, collect_stake_amount)
            return

        balance = get_balance(user_id)

        if amount > balance:
            msg = bot.reply_to(message, f"❌ You only have {balance:,} Plats.")
            bot.register_next_step_handler(msg, collect_stake_amount)
            return

        days = state["days"]
        rate = state["rate"]
        reward = round(amount * rate, 2)

        stake_id = create_stake(user_id, amount, rate, days)

        stake_state.pop(user_id, None)

        new_balance = get_balance(user_id)

        bot.send_message(
            message.chat.id,
            f"""
✅ <b>Stake Created!</b>

🆔 Stake #{stake_id}
💰 Staked: <code>{amount:,}</code> Plats
📅 Term: {days} days
🎁 Reward at maturity: <code>{reward:,}</code> Plats
💵 Total payout: <code>{amount + reward:,.0f}</code> Plats

💰 Remaining Balance: <code>{new_balance:,}</code> Plats
""",
            parse_mode="HTML",
            reply_markup=staking_menu_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "📊 My Stakes")
    def my_stakes(message):

        user_id = message.from_user.id
        rows = get_user_stakes(user_id)

        if not rows:
            bot.send_message(
                message.chat.id,
                "📊 You have no stakes yet. Tap 📈 New Stake to get started."
            )
            return

        from datetime import datetime
        now = datetime.now()

        lines = ["📊 <b>Your Stakes</b>\n"]
        markup = ReplyKeyboardMarkup(resize_keyboard=True)

        for stake_id, amount, rate, days, reward, status, start_time, end_time in rows:

            if status == "claimed":
                lines.append(f"✅ #{stake_id} — {amount:,.0f} Plats — Claimed")
            elif now >= end_time:
                lines.append(f"🎉 #{stake_id} — {amount:,.0f} Plats — MATURED, ready to claim!")
                markup.row(KeyboardButton(f"Claim #{stake_id}"))
            else:
                remaining = end_time - now
                lines.append(
                    f"⏳ #{stake_id} — {amount:,.0f} Plats — "
                    f"matures in {remaining.days}d {remaining.seconds // 3600}h"
                )

        markup.row(KeyboardButton("🔙 Back"))

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.message_handler(func=lambda m: m.text.startswith("Claim #"))
    def claim_stake_button(message):

        user_id = message.from_user.id

        try:
            stake_id = int(message.text.replace("Claim #", "").strip())
        except ValueError:
            return

        result = claim_stake(stake_id, user_id)

        if result == "not_found":
            bot.send_message(message.chat.id, "❌ Stake not found.")
        elif result == "not_matured":
            bot.send_message(message.chat.id, "⏳ This stake hasn't matured yet.")
        elif result == "already_claimed":
            bot.send_message(message.chat.id, "✅ This stake was already claimed.")
        elif result == "error":
            bot.send_message(message.chat.id, "⚠️ Something went wrong claiming this stake. Please try again.")
        else:
            amount, reward = result
            new_balance = get_balance(user_id)

            bot.send_message(
                message.chat.id,
                f"""
🎉 <b>Stake Claimed!</b>

💰 Principal: <code>{amount:,.0f}</code> Plats
🎁 Reward: <code>{reward:,.0f}</code> Plats

💵 New Balance: <code>{new_balance:,.0f}</code> Plats
""",
                parse_mode="HTML",
                reply_markup=staking_menu_keyboard()
            )
