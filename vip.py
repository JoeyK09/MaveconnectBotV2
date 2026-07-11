from telebot import types
from datetime import datetime, timedelta

from vip_keyboards import (
    vip_menu,
    vip_plans_keyboard,
    payment_keyboard
)

from vip_config import (
    VIP_PLANS,
    VIP_WALLETS,
    VIP_CHANNEL,
    ADMIN_ID
)

from database import (
    get_vip_info,
    save_vip_payment,
    get_vip_payment_history,
    is_vip
)

from keyboards import main_menu


# ================= ADMIN NOTIFICATION =================

def notify_admin(bot, user, plan, payment, reference, payment_id):

    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "✅ Approve",
            callback_data=f"approvevip_{payment_id}"
        ),
        types.InlineKeyboardButton(
            "❌ Reject",
            callback_data=f"rejectvip_{payment_id}"
        )
    )

    bot.send_message(
        ADMIN_ID,
        f"""
👑 VIP Payment Received

👤 User ID: {user}

💎 Plan: {VIP_PLANS[plan]["name"]}

💰 Amount: KSh {VIP_PLANS[plan]["price"]}

💳 Payment:
{payment}

🧾 Reference:
{reference}
""",
        reply_markup=markup
    )


# =====================================================
# REGISTER VIP HANDLERS
# =====================================================

def register_vip_handlers(bot):

    selected_plan = {}
    mpesa_code_waiting = {}
    crypto_waiting = {}

    # ================= VIP DASHBOARD =================

    @bot.message_handler(func=lambda m: m.text == "👑 VIP MEMBERSHIP")
    def vip_dashboard(message):

        info = get_vip_info(str(message.from_user.id))

        if info:
            active, plan, start, expiry = info
        else:
            active = False
            plan = "Free"
            expiry = None

        if active:

            text = f"""
👑 *MaveConnect VIP Dashboard*

🟢 Status: *ACTIVE*

💎 Plan: *{plan.title()}*

📅 Expires:
`{expiry}`

Choose an option below.
"""

        else:

            text = """
👑 *MaveConnect VIP Dashboard*

⚪ Status: *FREE MEMBER*

Upgrade today and unlock:

⛏️ 2× Mining Rewards

💰 2× Faucet Rewards

🎁 Daily VIP Bonus

⚡ Faster Withdrawals

🎉 Exclusive Giveaways

Choose an option below.
"""

        bot.send_message(
            message.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=vip_menu()
        )

    # ================= VIEW PLANS =================

    @bot.message_handler(func=lambda m: m.text == "📋 View Plans")
    def view_plans(message):

        bot.send_message(
            message.chat.id,
            """
👑 *Choose Your VIP Plan*

Select one of the plans below.
""",
            parse_mode="Markdown",
            reply_markup=vip_plans_keyboard()
        )

    # ================= VIP CHANNEL =================

    @bot.message_handler(func=lambda m: m.text == "👥 VIP Channel")
    def vip_channel_link(message):

        bot.send_message(
            message.chat.id,
            f"""
👥 *MaveConnect VIP Channel*

Join our exclusive VIP channel for premium signals, announcements and giveaways.

🔗 {VIP_CHANNEL}
""",
            parse_mode="Markdown"
        )

    # ================= PAYMENT HISTORY =================

    @bot.message_handler(func=lambda m: m.text == "📜 Payment History")
    def payment_history(message):

        rows = get_vip_payment_history(message.from_user.id)

        if not rows:
            bot.send_message(
                message.chat.id,
                "📜 You have no VIP payment history yet."
            )
            return

        lines = ["📜 *Your VIP Payment History*\n"]

        for plan, amount, method, status, created_at in rows:
            lines.append(
                f"💎 {plan.title()} • KSh{amount} • {method}\n"
                f"Status: {status.title()} • {created_at:%Y-%m-%d}\n"
            )

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="Markdown"
        )

    # ================= RENEW VIP =================

    @bot.message_handler(func=lambda m: m.text == "🔄 Renew VIP")
    def renew_vip(message):

        bot.send_message(
            message.chat.id,
            """
🔄 *Renew Your VIP*

Select a plan below to renew or upgrade your membership.
""",
            parse_mode="Markdown",
            reply_markup=vip_plans_keyboard()
        )

    # ================= BACK =================

    @bot.message_handler(func=lambda m: m.text == "🔙 Back")
    def vip_back(message):

        bot.send_message(
            message.chat.id,
            "🏠 Main Menu",
            reply_markup=main_menu()
        )

    @bot.message_handler(func=lambda m: m.text == "📅 My Subscription")
    def my_subscription(message):

        info = get_vip_info(str(message.from_user.id))

        if not info or not info[0]:
            bot.send_message(
                message.chat.id,
                "❌ You don't have an active VIP subscription."
            )
            return

        active, plan, start, expiry = info

        bot.send_message(
            message.chat.id,
            f"""
👑 *Your VIP Subscription*

💎 Plan: *{plan.title()}*

📅 Started:
`{start}`

⏳ Expires:
`{expiry}`

🟢 Status: *Active*
""",
            parse_mode="Markdown"
        )

    # ================= CHOOSE PLAN =================

    @bot.message_handler(func=lambda m: m.text in [
        "🥉 Basic • KSh299",
        "🥈 Premium • KSh799",
        "🥇 Elite • KSh2499"
    ])
    def choose_plan(message):

        plans = {
            "🥉 Basic • KSh299": ("basic", 299),
            "🥈 Premium • KSh799": ("premium", 799),
            "🥇 Elite • KSh2499": ("elite", 2499)
        }

        plan, price = plans[message.text]

        selected_plan[message.from_user.id] = {
            "plan": plan,
            "price": price
        }

        bot.send_message(
            message.chat.id,
            f"""
👑 *{plan.title()} VIP*

💰 Price: *KSh {price}*

Choose your preferred payment method.
""",
            parse_mode="Markdown",
            reply_markup=payment_keyboard()
        )

    # ================= PAYMENT METHODS =================

    @bot.message_handler(func=lambda m: m.text in [
        "🇰🇪 M-Pesa",
        "💵 USDT (TRC20)",
        "💵 USDT (BEP20)",
        "₿ Bitcoin",
        "♦ Ethereum"
    ])
    def payment_method(message):

        user = message.from_user.id

        if user not in selected_plan:
            bot.send_message(
                message.chat.id,
                "❌ Please choose a VIP plan first."
            )
            return

        plan = selected_plan[user]["plan"]
        price = selected_plan[user]["price"]

        # ---------- M-PESA ----------

        if message.text == "🇰🇪 M-Pesa":

            markup = types.ReplyKeyboardMarkup(
                resize_keyboard=True,
                one_time_keyboard=True
            )

            markup.add("✅ I've Paid")

            bot.send_message(
                message.chat.id,
                f"""
🇰🇪 *M-PESA PAYMENT*

👑 Plan: *{plan.title()}*

💰 Amount: *KSh {price}*

━━━━━━━━━━━━━━

📱 Pay To:
*0142047838*

👤 Name:
*Joseph Gichimu*

━━━━━━━━━━━━━━

After making the payment, tap *✅ I've Paid* below.
""",
                parse_mode="Markdown",
                reply_markup=markup
            )

            return

        # ---------- CRYPTO ----------

        wallets = {
            "💵 USDT (TRC20)": VIP_WALLETS["trc20"],
            "💵 USDT (BEP20)": VIP_WALLETS["bep20"],
            "₿ Bitcoin": VIP_WALLETS["btc"],
            "♦ Ethereum": VIP_WALLETS["eth"]
        }

        crypto_waiting[user] = {
            "payment": message.text
        }

        bot.send_message(
            message.chat.id,
            f"""
💳 *{message.text}*

👑 Plan: *{plan.title()}*

💰 Amount: *KSh {price}*

Send payment to:

`{wallets[message.text]}`

After sending payment, reply with your TXID (Transaction Hash).
""",
            parse_mode="Markdown"
    )
            # ================= I'VE PAID =================

    @bot.message_handler(func=lambda m: m.text == "✅ I've Paid")
    def mpesa_paid(message):

        user = message.from_user.id

        if user not in selected_plan:
            bot.send_message(
                message.chat.id,
                "❌ Please select a VIP plan first."
            )
            return

        mpesa_code_waiting[user] = True

        markup = types.ReplyKeyboardRemove()

        bot.send_message(
            message.chat.id,
            """
🧾 *Enter your M-PESA Transaction Code.*

Example:

`TIQ8ABC123`

We'll verify your payment before activating your VIP membership.
""",
            parse_mode="Markdown",
            reply_markup=markup
        )

    # ================= RECEIVE MPESA CODE =================

    @bot.message_handler(func=lambda m: m.from_user.id in mpesa_code_waiting)
    def receive_mpesa_code(message):

        user = message.from_user.id

        mpesa_code_waiting.pop(user)

        if user not in selected_plan:

            bot.send_message(
                message.chat.id,
                "❌ VIP plan not found. Please start again."
            )
            return

        plan = selected_plan[user]["plan"]
        price = selected_plan[user]["price"]

        payment_id = save_vip_payment(
            str(user),
            plan,
            price,
            "M-Pesa",
            message.text.strip().upper()
        )

        notify_admin(
            bot,
            user,
            plan,
            "M-Pesa",
            message.text.strip().upper(),
            payment_id
        )

        bot.send_message(
            message.chat.id,
            """
✅ Payment submitted successfully.

⏳ Your payment is awaiting verification.

You'll receive a notification once your VIP membership is activated.
"""
        )

    # ================= RECEIVE CRYPTO TXID =================

    @bot.message_handler(func=lambda m: m.from_user.id in crypto_waiting)
    def receive_crypto_txid(message):

        user = message.from_user.id

        payment = crypto_waiting[user]["payment"]

        crypto_waiting.pop(user)

        if user not in selected_plan:

            bot.send_message(
                message.chat.id,
                "❌ VIP plan not found."
            )
            return

        plan = selected_plan[user]["plan"]
        price = selected_plan[user]["price"]

        payment_id = save_vip_payment(
            str(user),
            plan,
            price,
            payment,
            message.text.strip()
        )

        notify_admin(
            bot,
            user,
            plan,
            payment,
            message.text.strip(),
            payment_id
        )

        bot.send_message(
            message.chat.id,
            """
✅ Transaction submitted successfully.

⏳ Your payment has been received and is awaiting verification.

You'll be notified once your VIP membership is activated.
"""
    )
            # ================= ADMIN APPROVE / REJECT =================
    # NOTE: Approve/Reject for VIP payments is handled centrally in
    # admin.py's approve_vip_callback / reject_vip_callback, which operate
    # on the vip_payments row id (matching the payment_id now passed into
    # notify_admin above). Having a second handler here on the same
    # "approvevip_"/"rejectvip_" callback prefixes caused conflicting,
    # crash-prone behavior since the two files disagreed on whether the
    # value was a user id or a payment id — so it's been removed in favor
    # of the single implementation in admin.py.
