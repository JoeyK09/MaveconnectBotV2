from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from database import (
    get_open_prediction_events,
    get_prediction_event,
    get_user_pick,
    submit_prediction
)

from keyboards import main_menu


def predictions_menu_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🏆 Open Predictions"))
    markup.row(KeyboardButton("🔙 Back"))
    return markup


def register_prediction_handlers(bot):

    @bot.message_handler(func=lambda m: m.text == "🏆 Predictions")
    def predictions_intro(message):
        bot.send_message(
            message.chat.id,
            """
🏆 <b>MaveConnect Predictions</b>

Guess the outcome of upcoming matches and events — <b>100% free to play</b>.

🎁 Get it right, win Plats. Get it wrong, you lose nothing — there's never anything to risk here.

👇 Check what's open right now.
""",
            parse_mode="HTML",
            reply_markup=predictions_menu_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "🔙 Back")
    def predictions_back(message):
        bot.send_message(message.chat.id, "🏠 Main Menu", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: m.text == "🏆 Open Predictions")
    def open_predictions(message):

        events = get_open_prediction_events()

        if not events:
            bot.send_message(
                message.chat.id,
                "🏆 No predictions are open right now. Check back soon!"
            )
            return

        user_id = message.from_user.id

        for event_id, title, options, reward in events:

            existing_pick = get_user_pick(event_id, user_id)

            if existing_pick:
                bot.send_message(
                    message.chat.id,
                    f"""
🏆 <b>{title}</b>

✅ You picked: <b>{existing_pick}</b>

🎁 Reward if correct: {reward:,.0f} Plats

Results will be posted once the event is resolved. Good luck!
""",
                    parse_mode="HTML"
                )
                continue

            markup = types.InlineKeyboardMarkup()
            for option in options:
                markup.add(
                    types.InlineKeyboardButton(
                        option,
                        callback_data=f"predict_{event_id}_{option}"
                    )
                )

            bot.send_message(
                message.chat.id,
                f"""
🏆 <b>{title}</b>

🎁 Reward if correct: {reward:,.0f} Plats
🆓 100% free — nothing to lose

Make your pick:
""",
                parse_mode="HTML",
                reply_markup=markup
            )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("predict_"))
    def handle_prediction_pick(call):

        _, event_id, choice = call.data.split("_", 2)
        event_id = int(event_id)
        user_id = call.from_user.id

        event = get_prediction_event(event_id)

        if not event or event[4] != "open":
            bot.answer_callback_query(call.id, "This prediction has already closed.")
            return

        success = submit_prediction(event_id, user_id, choice)

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        if not success:
            bot.answer_callback_query(call.id, "You've already picked for this one!")
            return

        bot.answer_callback_query(call.id, f"Picked: {choice}!")

        bot.send_message(
            call.message.chat.id,
            f"""
✅ <b>Pick locked in!</b>

Your guess: <b>{choice}</b>

We'll let you know when this event is resolved. Good luck! 🍀
""",
            parse_mode="HTML"
        )
