# kamikaze_game.py
#
# Kamikaze as a Telegram Mini App (WebApp) living inside MaveConnect —
# launched from a button, opens in-chat, no BotFather Games registration needed.
#
# SECURITY MODEL:
#   The game page cannot be trusted to self-report "give this user N Plats".
#   Instead, Telegram signs a payload (`initData`) with your bot token whenever
#   the Mini App is opened. The frontend sends that raw initData back to us on
#   game-over; we re-derive the signature server-side and only trust the user
#   identity if it matches. This is the same mechanism Telegram itself uses to
#   secure Mini Apps: https://core.telegram.org/bots/webapps#validating-data
#
# ANTI-CHEAT:
#   - Each initData payload can only be redeemed once (hash tracked in memory).
#   - initData older than MAX_SESSION_AGE_SECONDS is rejected (can't stockpile).
#   - Reported Plats are capped by elapsed time since the session started
#     (MAX_PLATS_PER_SECOND), so a forged/inflated score can't out-earn what's
#     physically possible to collect in that time.
#   - A daily-per-user cap bounds total exposure even across many sessions.
#
# NOTE ON STORAGE: session/daily-cap tracking below is in-memory (a Python
# dict), which is simplest to ship but resets if the bot process restarts,
# and won't work correctly across multiple worker processes. That's fine for
# a single-process deploy. If you later run multiple workers or want the caps
# to survive restarts, move USED_HASHES and DAILY_CREDITED into a database
# table instead — happy to do that once I can see database.py.
#
# SETUP REQUIRED:
#   1. Host kamikaze.html somewhere public over HTTPS (e.g. GitHub Pages).
#   2. Set GAME_URL below to that link.
#   3. Add the Kamikaze button (kamikaze_inline_button / kamikaze_keyboard_button)
#      into wherever your Games menu is built (games_keyboard.py), or just use
#      the /kamikaze command included here to test immediately.

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from telebot import types

GAME_URL = "https://YOUR-USERNAME.github.io/kamikaze.html"  # <-- update this

MAX_SESSION_AGE_SECONDS = 20 * 60      # a launched session is valid for 20 minutes
MAX_PLATS_PER_SECOND = 0.4             # generous cap: ~1 Plat every 2.5s of play
MAX_PLATS_PER_DAY = 150                # hard ceiling per user per day

USED_HASHES = set()                    # initData hashes already redeemed
DAILY_CREDITED = {}                    # {(user_id, "YYYY-MM-DD"): plats_credited_today}


def _verify_init_data(init_data: str, bot_token: str):
    """
    Returns (user_dict, auth_date, received_hash) if valid, else (None, None, None).
    """
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None, None, None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None, None, None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None, None, None

    try:
        auth_date = int(parsed.get("auth_date", 0))
    except ValueError:
        return None, None, None

    if time.time() - auth_date > MAX_SESSION_AGE_SECONDS:
        return None, None, None

    user_raw = parsed.get("user")
    if not user_raw:
        return None, None, None

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None, None, None

    return user, auth_date, received_hash


def kamikaze_inline_button(text="🛩️ Kamikaze"):
    """Use inside an InlineKeyboardMarkup, e.g. markup.add(kamikaze_inline_button())"""
    return types.InlineKeyboardButton(
        text=text, web_app=types.WebAppInfo(url=GAME_URL)
    )


def kamikaze_keyboard_button(text="🛩️ Kamikaze"):
    """Use inside a ReplyKeyboardMarkup, matching the style of your other menu buttons."""
    return types.KeyboardButton(text=text, web_app=types.WebAppInfo(url=GAME_URL))


def register_kamikaze_handlers(bot, app, add_plats_fn):
    """
    Call once from bot.py:
        register_kamikaze_handlers(bot, app, add_plats)
    where add_plats is your existing database.add_plats function.

    NOTE: assumes add_plats(user_id: str, amount: int/float) — adjust the
    call below if your actual signature differs.
    """

    # ---------- Quick test trigger (remove once wired into your Games menu) ----------
    @bot.message_handler(commands=["kamikaze"])
    def send_kamikaze(message):
        markup = types.InlineKeyboardMarkup()
        markup.add(kamikaze_inline_button())
        bot.send_message(
            message.chat.id,
            "🛩️ *KAMIKAZE*\n\nDodge, shoot, collect Plats. Tap below to launch.",
            reply_markup=markup,
            parse_mode="Markdown",
        )

    # ---------- Score submission ----------
    @app.route("/kamikaze/score", methods=["POST"])
    def kamikaze_score():
        from flask import request, jsonify

        data = request.get_json(silent=True) or {}
        init_data = data.get("initData", "")
        reported_plats = data.get("plats", 0)
        reported_score = data.get("score", 0)

        try:
            reported_plats = max(0, int(reported_plats))
            reported_score = max(0, int(reported_score))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid payload"}), 400

        user, auth_date, received_hash = _verify_init_data(init_data, bot.token)
        if not user:
            return jsonify({"ok": False, "error": "could not verify session"}), 403

        if received_hash in USED_HASHES:
            return jsonify({"ok": False, "error": "session already redeemed"}), 409
        USED_HASHES.add(received_hash)

        user_id = user.get("id")
        if not user_id:
            return jsonify({"ok": False, "error": "no user id"}), 400

        # Plausibility cap: can't have earned more than elapsed-time allows.
        elapsed = max(1, time.time() - auth_date)
        max_plausible = int(elapsed * MAX_PLATS_PER_SECOND) + 3
        capped_plats = min(reported_plats, max_plausible)

        # Daily cap.
        today = time.strftime("%Y-%m-%d", time.gmtime())
        day_key = (user_id, today)
        already_today = DAILY_CREDITED.get(day_key, 0)
        remaining_allowance = max(0, MAX_PLATS_PER_DAY - already_today)
        credited = min(capped_plats, remaining_allowance)

        if credited > 0:
            try:
                add_plats_fn(str(user_id), credited)
            except Exception as e:
                print("Kamikaze add_plats error:", repr(e))
                return jsonify({"ok": False, "error": "credit failed"}), 500

        DAILY_CREDITED[day_key] = already_today + credited

        try:
            bot.send_message(
                user_id,
                f"🛩️ Kamikaze run complete!\n\n"
                f"Score: {reported_score}\n"
                f"Plats credited: +{credited}"
                + ("" if credited == reported_plats else " (capped)")
            )
        except Exception:
            pass

        return jsonify({"ok": True, "credited": credited})
