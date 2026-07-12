from telebot import types

from vip_config import ADMIN_ID

from database import get_all_pending_vip_payments

from admin_keyboards import admin_menu

from database import (
    get_total_users,
    get_total_vip,
    get_pending_vip_payments,
    count_pending_withdrawals,
    get_all_pending_vip_payments,
    approve_vip_payment,
    reject_vip_payment,
    get_active_stake_liability,
    create_prediction_event,
    get_open_prediction_events,
    resolve_prediction_event,
    get_active_vip_members,
    get_all_user_ids,
    get_pending_withdrawals,
    approve_withdrawal,
    reject_withdrawal
)

from vip_config import VIP_PLANS


def register_admin_handlers(bot):

    broadcast_waiting = {}

    # ================= ADMIN PANEL =================

    @bot.message_handler(commands=["admin"])
    def admin_panel(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            bot.reply_to(
                message,
                "❌ You are not authorized."
            )
            return

        bot.send_message(
            message.chat.id,
            """
👑 *MaveConnect Admin Panel*

Welcome Administrator.

Choose an option below.
""",
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )

    # ================= PREDICTION GAME (ADMIN) =================

    new_prediction_state = {}

    @bot.message_handler(commands=["newprediction"])
    def new_prediction_start(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        msg = bot.reply_to(
            message,
            "🏆 New Prediction Event\n\n"
            "Enter the title (e.g. 'Arsenal vs Chelsea — Who wins?'):"
        )

        bot.register_next_step_handler(msg, new_prediction_title)

    def new_prediction_title(message):
        new_prediction_state[message.from_user.id] = {"title": message.text.strip()}

        msg = bot.reply_to(
            message,
            "Enter the options, separated by commas.\n\n"
            "Example: Arsenal, Draw, Chelsea"
        )

        bot.register_next_step_handler(msg, new_prediction_options)

    def new_prediction_options(message):
        options = [o.strip() for o in message.text.split(",") if o.strip()]

        if len(options) < 2:
            msg = bot.reply_to(message, "❌ Please enter at least 2 options, separated by commas.")
            bot.register_next_step_handler(msg, new_prediction_options)
            return

        new_prediction_state[message.from_user.id]["options"] = options

        msg = bot.reply_to(
            message,
            "How many Plats should the reward be for a correct guess? (e.g. 20)"
        )

        bot.register_next_step_handler(msg, new_prediction_reward)

    def new_prediction_reward(message):

        try:
            reward = float(message.text.strip())
        except ValueError:
            msg = bot.reply_to(message, "❌ Please enter a valid number.")
            bot.register_next_step_handler(msg, new_prediction_reward)
            return

        state = new_prediction_state.pop(message.from_user.id)

        event_id = create_prediction_event(state["title"], state["options"], reward)

        bot.reply_to(
            message,
            f"✅ Prediction event #{event_id} created!\n\n"
            f"🏆 {state['title']}\n"
            f"Options: {', '.join(state['options'])}\n"
            f"Reward: {reward:,.0f} Plats\n\n"
            f"It's now live for users to pick."
        )

    @bot.message_handler(commands=["resolveprediction"])
    def resolve_prediction_start(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        events = get_open_prediction_events()

        if not events:
            bot.reply_to(message, "✅ No open predictions to resolve.")
            return

        markup = types.InlineKeyboardMarkup()

        for event_id, title, options, reward in events:
            markup.add(
                types.InlineKeyboardButton(
                    f"#{event_id} — {title}",
                    callback_data=f"resolveevent_{event_id}"
                )
            )

        bot.send_message(
            message.chat.id,
            "🏆 Select the event to resolve:",
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("resolveevent_"))
    def resolve_pick_event(call):

        if call.from_user.id != ADMIN_ID:
            return

        event_id = int(call.data.split("_")[1])
        events = dict((e[0], e) for e in get_open_prediction_events())
        event = events.get(event_id)

        if not event:
            bot.answer_callback_query(call.id, "This event is no longer open.")
            return

        _, title, options, reward = event

        markup = types.InlineKeyboardMarkup()
        for option in options:
            markup.add(
                types.InlineKeyboardButton(
                    option,
                    callback_data=f"resolveoutcome_{event_id}_{option}"
                )
            )

        bot.edit_message_text(
            f"🏆 {title}\n\nWhich option was correct?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("resolveoutcome_"))
    def resolve_pick_outcome(call):

        if call.from_user.id != ADMIN_ID:
            return

        _, event_id, correct_option = call.data.split("_", 2)
        event_id = int(event_id)

        result = resolve_prediction_event(event_id, correct_option)

        if not result:
            bot.answer_callback_query(call.id, "This event was already resolved.")
            return

        reward, winners = result

        bot.edit_message_text(
            f"✅ Resolved! Correct answer: {correct_option}\n\n"
            f"🏆 {len(winners)} winner(s) paid {reward:,.0f} Plats each.",
            call.message.chat.id,
            call.message.message_id
        )

        for winner_id in winners:
            try:
                bot.send_message(
                    int(winner_id),
                    f"""
🎉 <b>You predicted it right!</b>

The correct answer was: <b>{correct_option}</b>

💰 +{reward:,.0f} Plats credited to your account.
""",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    # ================= VIP MEMBERS =================

    @bot.message_handler(func=lambda m: m.text == "👥 VIP Members")
    def vip_members(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        members = get_active_vip_members()

        if not members:
            bot.send_message(message.chat.id, "👑 No active VIP members right now.")
            return

        lines = ["👥 *Active VIP Members*\n"]

        for user_id, plan, expiry in members:
            plan_label = (plan or "Unknown").title()
            expiry_label = expiry.strftime("%Y-%m-%d") if expiry else "N/A"
            lines.append(f"`{user_id}` — {plan_label} — expires {expiry_label}")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="Markdown"
        )

    # ================= BROADCAST =================

    @bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
    def broadcast_start(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        msg = bot.send_message(
            message.chat.id,
            "📢 Send the message you want to broadcast to *all users*.\n\n"
            "Type /cancel to abort.",
            parse_mode="Markdown"
        )

        bot.register_next_step_handler(msg, broadcast_confirm)

    def broadcast_confirm(message):

        if message.text and message.text.strip() == "/cancel":
            bot.send_message(message.chat.id, "❌ Broadcast cancelled.", reply_markup=admin_menu())
            return

        broadcast_waiting[message.from_user.id] = message.text

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(
            types.KeyboardButton("✅ Send Broadcast"),
            types.KeyboardButton("❌ Cancel Broadcast")
        )

        bot.send_message(
            message.chat.id,
            f"📢 Preview:\n\n{message.text}\n\n"
            f"Send this to every user?",
            reply_markup=markup
        )

    @bot.message_handler(func=lambda m: m.text == "✅ Send Broadcast")
    def broadcast_send(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        text = broadcast_waiting.pop(message.from_user.id, None)

        if not text:
            bot.send_message(message.chat.id, "❌ Nothing to broadcast.", reply_markup=admin_menu())
            return

        user_ids = get_all_user_ids()

        sent = 0
        failed = 0

        status_msg = bot.send_message(message.chat.id, f"📢 Sending to {len(user_ids)} users...")

        for user_id in user_ids:
            try:
                bot.send_message(int(user_id), text)
                sent += 1
            except Exception:
                failed += 1

        bot.send_message(
            message.chat.id,
            f"✅ Broadcast complete.\n\nSent: {sent}\nFailed: {failed}",
            reply_markup=admin_menu()
        )

    @bot.message_handler(func=lambda m: m.text == "❌ Cancel Broadcast")
    def broadcast_cancel(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        broadcast_waiting.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "❌ Broadcast cancelled.", reply_markup=admin_menu())

    # ================= WITHDRAWALS =================

    @bot.message_handler(func=lambda m: m.text == "💰 Withdrawals")
    def withdrawals_list(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        rows = get_pending_withdrawals()

        if not rows:
            bot.send_message(message.chat.id, "✅ No pending withdrawals.")
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

    # NOTE: the actual approve/reject logic for these buttons lives in
    # bot.py (approve_withdrawal_callback / reject_withdrawal_callback) —
    # they match the same "✅ Approve Withdrawal #<id>" text regardless of
    # which module sent the button, so no duplicate logic needed here.

    # ================= VIP SETTINGS =================

    @bot.message_handler(func=lambda m: m.text == "⚙ VIP Settings")
    def vip_settings(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        lines = ["⚙️ *Current VIP Plans*\n"]

        for key, plan in VIP_PLANS.items():
            lines.append(
                f"{plan['name']} — KSh {plan['price']} — {plan['days']} days"
            )

        lines.append(
            "\nℹ️ To change prices or durations, edit VIP_PLANS in "
            "`vip_config.py` and redeploy — there's no in-chat editor for "
            "this yet."
        )

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="Markdown"
        )

    # ================= STATISTICS =================

    @bot.message_handler(func=lambda m: m.text == "📊 Statistics")
    def statistics(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        try:

            users = get_total_users()
            vip = get_total_vip()
            pending = get_pending_vip_payments()
            withdrawals = count_pending_withdrawals()
            stake_liability = get_active_stake_liability()

            bot.send_message(
                message.chat.id,
                f"""
📊 *MaveConnect Statistics*

👥 Total Users: *{users}*

👑 Active VIP Members: *{vip}*

💳 Pending VIP Payments: *{pending}*

💰 Pending Withdrawals: *{withdrawals}*

📈 Active Staking Liability: *{stake_liability:,.0f} Plats*
""",
                parse_mode="Markdown"
            )

        except Exception as e:

            bot.send_message(
                message.chat.id,
                f"❌ Error loading statistics:\n\n`{e}`",
                parse_mode="Markdown"
            )

    # ================= PENDING PAYMENTS =================

    @bot.message_handler(func=lambda m: m.text == "💳 Pending Payments")
    def pending_payments(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        try:

            payments = get_all_pending_vip_payments()

            if not payments:

                bot.send_message(
                    message.chat.id,
                    "✅ There are no pending VIP payments."
                )
                return

            for payment in payments:

                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(
                    types.KeyboardButton(f"✅ Approve VIP #{payment['id']}"),
                    types.KeyboardButton(f"❌ Reject VIP #{payment['id']}")
                )

                bot.send_message(
                    message.chat.id,
                    f"""
👤 User: `{payment['user_id']}`

💎 Plan: *{payment['plan'].title()}*

💰 Amount: *{payment['amount']}*

💳 Method: *{payment['payment_method']}*

🧾 Reference:

`{payment['reference']}`
""",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

        except Exception as e:

            bot.send_message(
                message.chat.id,
                f"❌ {e}"
                )
            
    # ================= APPROVE VIP =================

    @bot.message_handler(func=lambda m: m.text.startswith("✅ Approve VIP #"))
    def approve_vip_callback(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        payment_id = message.text.replace("✅ Approve VIP #", "").strip()

        result = approve_vip_payment(payment_id)

        if result:

            user_id, plan = result

            bot.send_message(
                message.chat.id,
                "✅ VIP payment approved successfully.",
                reply_markup=admin_menu()
            )

            try:
                bot.send_message(
                    int(user_id),
                    f"""
🎉 *Congratulations!*

Your {plan.title()} VIP payment has been approved.

👑 Welcome to *MaveConnect VIP!*

Enjoy your exclusive benefits!

Thank you for supporting MaveConnect ❤️
""",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        else:

            bot.send_message(
                message.chat.id,
                "❌ Payment not found or already processed.",
                reply_markup=admin_menu()
            )


    # ================= REJECT VIP =================

    @bot.message_handler(func=lambda m: m.text.startswith("❌ Reject VIP #"))
    def reject_vip_callback(message):

        if str(message.from_user.id) != str(ADMIN_ID):
            return

        payment_id = message.text.replace("❌ Reject VIP #", "").strip()

        user_id = reject_vip_payment(payment_id)

        bot.send_message(
            message.chat.id,
            "❌ VIP payment rejected.",
            reply_markup=admin_menu()
        )

        if user_id:
            try:
                bot.send_message(
                    int(user_id),
                    """
❌ *VIP Payment Rejected*

Unfortunately we could not verify your payment.

If you believe this is an error, please contact MaveConnect Support.
""",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
