# kamikaze_game.py
#
# Backend for Kamikaze, a Telegram Mini App (WebApp) endless runner living
# inside MaveConnect. Handles:
#   1. /session -> tells the game the player's current Plats balance,
#      shields, and arrows when it opens.
#   2. /shop    -> buying shields / arrow packs with real Plats.
#   3. /score   -> crediting Plats mined during a run, and syncing shield/
#      arrow usage back to the player's inventory.
#
# SECURITY MODEL:
#   Nothing the game page says about itself is trusted. Every request carries
#   Telegram's signed `initData`, which we verify server-side with your bot
#   token (same mechanism Telegram uses to secure Mini Apps:
#   https://core.telegram.org/bots/webapps#validating-data). Only requests
#   with a valid signature are allowed to touch a wallet.
#
# ANTI-CHEAT ON EARNED PLATS:
#   - Each /score submission (identified by its initData hash) can only be
#     redeemed once.
#   - initData older than MAX_SESSION_AGE_SECONDS is rejected.
#   - Reported Plats mined are capped by elapsed time since the session
#     started (MAX_PLATS_PER_SECOND) — a forged score can't out-earn what's
#     physically possible to collect in that time.
#   - A daily-per-user cap bounds total exposure across many runs.
#   - Arrow/shield usage reported at game-over is clamped so a run can never
#     "spend" more than the player actually had.
#
# NOTE ON STORAGE: inventory (shields/arrows) and daily-earned tracking below
# live in an in-memory dict — simplest to ship, but resets on process restart
# and won't sync across multiple worker processes. Fine for a single-process
# deploy. If you want this to survive restarts, move INVENTORY and
# DAILY_CREDITED into a real database table — happy to do that once I can
# see database.py.
#
# SETUP REQUIRED:
#   1. Host kamikaze.html somewhere public over HTTPS (e.g. GitHub Pages).
#   2. Set GAME_URL below to that link.
#   3. Add the Kamikaze button (already done in games_keyboard.py) — it
#      points the WebApp at GAME_URL + "?apiBase=<your deployed app URL>/kamikaze"

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from telebot import types

GAME_URL = "https://joeyk09.github.io/MaveconnectbotV2/kamikaze.html"
PUBLIC_BASE_URL = "https://maveconnectbotv2.onrender.com"

_API_BASE = f"{PUBLIC_BASE_URL}/kamikaze"
_LAUNCH_URL = f"{GAME_URL}?apiBase={_API_BASE}"

MAX_SESSION_AGE_SECONDS = 20 * 60      # a launched session is valid for 20 minutes
MAX_PLATS_PER_SECOND = 0.5             # generous cap on mined Plats per second of play
MAX_PLATS_PER_DAY = 200                # hard ceiling per user per day

SHOP_ITEMS = {
    "shield":  {"cost": 20, "grants": {"shields": 1}},
    "arrows5": {"cost": 15, "grants": {"arrows": 5}},
}

PLAT_VALUE_KES = 20     # 1 Plat = KES 20 (your existing MaveConnect rate)
KES_PER_USD = 130       # standard approximate rate — update to your current one if it moves

def _usd_price(plat_cost):
    return round((plat_cost * PLAT_VALUE_KES) / KES_PER_USD, 2)

SHOP_DISPLAY = {
    "shield":  {"plats": SHOP_ITEMS["shield"]["cost"], "usd": _usd_price(SHOP_ITEMS["shield"]["cost"])},
    "arrows5": {"plats": SHOP_ITEMS["arrows5"]["cost"], "usd": _usd_price(SHOP_ITEMS["arrows5"]["cost"])},
}

USED_HASHES = set()                    # score submissions already redeemed
DAILY_CREDITED = {}                    # {(user_id, "YYYY-MM-DD"): plats_credited_today}
INVENTORY = {}                         # {user_id: {"shields": int, "arrows": int}}
BEST_SCORE = {}                        # {user_id: highest score ever submitted}


def _get_inventory(user_id):
    return INVENTORY.setdefault(user_id, {"shields": 0, "arrows": 0})


def _verify_init_data(init_data: str, bot_token: str):
    """Returns (user_dict, auth_date, received_hash) if valid, else (None, None, None)."""
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None, None, None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None, None, None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

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


def kamikaze_keyboard_button(text="🛩️ Kamikaze"):
    """Use inside a ReplyKeyboardMarkup, matching the style of your other menu buttons."""
    return types.KeyboardButton(text=text, web_app=types.WebAppInfo(url=_LAUNCH_URL))


def register_kamikaze_handlers(bot, app, get_balance_fn, add_plats_fn, remove_plats_fn):
    """
    Call once from bot.py:
        register_kamikaze_handlers(bot, app, get_balance, add_plats, remove_plats)

    NOTE: assumes get_balance(user_id) -> number, add_plats(user_id, amount),
    remove_plats(user_id, amount) — matching your existing database.py signatures.
    Uses GAME_URL and PUBLIC_BASE_URL set at the top of this file.
    """

    api_base = _API_BASE

    # ---------- Quick test trigger (safe to keep even after adding the menu button) ----------
    @bot.message_handler(commands=["kamikaze"])
    def send_kamikaze(message):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "🛩️ Play Kamikaze",
            web_app=types.WebAppInfo(url=_LAUNCH_URL)
        ))
        bot.send_message(
            message.chat.id,
            "🛩️ *KAMIKAZE*\n\nMine Plats, dodge the dragonflies, hop the platypuses. Tap below to launch.",
            reply_markup=markup,
            parse_mode="Markdown",
        )

    # ---------- Session: balance + inventory on load ----------
    @app.route("/kamikaze/session", methods=["POST"])
    def kamikaze_session():
        from flask import request, jsonify

        data = request.get_json(silent=True) or {}
        user, _, _ = _verify_init_data(data.get("initData", ""), bot.token)
        if not user:
            return jsonify({"ok": False, "error": "could not verify session"}), 403

        user_id = user.get("id")
        inv = _get_inventory(user_id)
        try:
            balance = get_balance_fn(str(user_id))
        except Exception as e:
            print("Kamikaze get_balance error:", repr(e))
            balance = 0

        return jsonify({
            "ok": True,
            "balance": balance,
            "shields": inv["shields"],
            "arrows": inv["arrows"],
            "shop": SHOP_DISPLAY,
            "best_score": BEST_SCORE.get(user_id, 0),
        })

    # ---------- Shop: buy shields / arrows with Plats ----------
    @app.route("/kamikaze/shop", methods=["POST"])
    def kamikaze_shop():
        from flask import request, jsonify

        data = request.get_json(silent=True) or {}
        user, _, _ = _verify_init_data(data.get("initData", ""), bot.token)
        if not user:
            return jsonify({"ok": False, "error": "could not verify session"}), 403

        item_id = data.get("item")
        item = SHOP_ITEMS.get(item_id)
        if not item:
            return jsonify({"ok": False, "error": "unknown item"}), 400

        user_id = user.get("id")
        try:
            balance = get_balance_fn(str(user_id))
        except Exception as e:
            print("Kamikaze get_balance error:", repr(e))
            return jsonify({"ok": False, "error": "could not check balance"}), 500

        if balance < item["cost"]:
            return jsonify({"ok": False, "error": "insufficient Plats"}), 402

        try:
            remove_plats_fn(str(user_id), item["cost"])
        except Exception as e:
            print("Kamikaze remove_plats error:", repr(e))
            return jsonify({"ok": False, "error": "purchase failed"}), 500

        inv = _get_inventory(user_id)
        for k, v in item["grants"].items():
            inv[k] = inv.get(k, 0) + v

        try:
            new_balance = get_balance_fn(str(user_id))
        except Exception:
            new_balance = balance - item["cost"]

        return jsonify({
            "ok": True,
            "balance": new_balance,
            "shields": inv["shields"],
            "arrows": inv["arrows"],
        })

    # ---------- Score: credit mined Plats, sync inventory usage ----------
    @app.route("/kamikaze/score", methods=["POST"])
    def kamikaze_score():
        from flask import request, jsonify

        data = request.get_json(silent=True) or {}
        try:
            reported_plats = max(0, int(data.get("plats", 0)))
            reported_score = max(0, int(data.get("score", 0)))
            arrows_used = max(0, int(data.get("arrows_used", 0)))
            shields_used = max(0, int(data.get("shields_used", 0)))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid payload"}), 400

        user, auth_date, received_hash = _verify_init_data(data.get("initData", ""), bot.token)
        if not user:
            return jsonify({"ok": False, "error": "could not verify session"}), 403

        if received_hash in USED_HASHES:
            return jsonify({"ok": False, "error": "session already redeemed"}), 409
        USED_HASHES.add(received_hash)

        user_id = user.get("id")

        # Plausibility cap on earned Plats.
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

        # Sync inventory usage — clamp so a run can never spend more than was held.
        inv = _get_inventory(user_id)
        inv["arrows"] = max(0, inv["arrows"] - arrows_used)
        inv["shields"] = max(0, inv["shields"] - shields_used)

        # Track best score ever, per user.
        is_new_best = reported_score > BEST_SCORE.get(user_id, 0)
        if is_new_best:
            BEST_SCORE[user_id] = reported_score

        try:
            balance = get_balance_fn(str(user_id))
        except Exception:
            balance = None

        try:
            bot.send_message(
                user_id,
                f"🛩️ Kamikaze complete!\n\n"
                f"Score: {reported_score}" + (" 🎉 New best!" if is_new_best else "") + "\n"
                f"Plats mined: +{credited}"
                + ("" if credited == reported_plats else " (capped)")
            )
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "credited": credited,
            "balance": balance,
            "shields": inv["shields"],
            "arrows": inv["arrows"],
            "best_score": BEST_SCORE.get(user_id, 0),
        })
