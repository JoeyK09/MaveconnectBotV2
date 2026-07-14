# ============ PASTE 1: near your other constants (e.g. right after VIP_GROUP / FREE_GROUP) ============

VIP_GROUP_ID = 0    # <-- replace with your real VIP group's numeric chat ID (looks like -1001234567890)
FREE_GROUP_ID = 0   # <-- replace with your real Free group's numeric chat ID

# Coins to consider each cycle when picking "most active" — extend freely,
# but every symbol here must already exist in COINPAPRIKA_IDS above.
INSIGHT_COINS = [
    "btc", "eth", "bnb", "sol", "xrp", "ada", "avax", "dot",
    "link", "ltc", "near", "apt", "sui", "ton", "hbar", "kas", "cro", "icp"
]


# ============ PASTE 2: anywhere below scan_coin()/ai_analysis(), above the "if __name__" block ============

def get_trending_coins(limit=3):
    """
    One bulk CoinPaprika call, ranks our whitelist by |24h % change|
    so we don't hammer the API with a request per coin every hour.
    """
    try:
        r = requests.get("https://api.coinpaprika.com/v1/tickers", timeout=15)
        if r.status_code != 200:
            print("Trending fetch failed:", r.status_code)
            return []

        all_tickers = r.json()
        id_to_symbol = {COINPAPRIKA_IDS[s]: s for s in INSIGHT_COINS if s in COINPAPRIKA_IDS}

        candidates = []
        for t in all_tickers:
            symbol = id_to_symbol.get(t.get("id"))
            if symbol:
                change = abs(t["quotes"]["USD"]["percent_change_24h"])
                candidates.append((symbol, change))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:limit]]

    except Exception as e:
        print("Trending Coins Error:", repr(e))
        return []


def build_vip_insight(coin):
    scan = scan_coin(coin)
    if not scan:
        return None
    arrow = "🟢" if scan["change24"] >= 0 else "🔴"
    return (
        f"{arrow} {scan['symbol']} — {scan['coin']}\n"
        f"💰 ${scan['price']:,.4f}  ({scan['change24']:+.2f}% 24h)\n"
        f"📊 Signal: {scan['signal']}  |  Strength: {scan['strength']}/100\n"
        f"📈 Trend: {scan['trend']}\n"
        f"🛡️ Support: ${scan['support']:,.4f}  |  Resistance: ${scan['resistance']:,.4f}\n"
        f"🏦 Rank #{scan['rank']}  |  Vol 24h: ${scan['volume']:,.0f}"
    )


def build_free_update(coin):
    data = get_coin_data(coin)
    if not data:
        return None
    arrow = "🟢📈" if data["change24"] >= 0 else "🔴📉"
    return f"{arrow} {data['symbol']}: ${data['price']:,.4f} ({data['change24']:+.2f}% 24h)"


def insight_poster():
    while True:
        try:
            if not VIP_GROUP_ID or not FREE_GROUP_ID:
                print("Insight poster skipped: VIP_GROUP_ID / FREE_GROUP_ID not configured yet.")
            else:
                trending = get_trending_coins(limit=3)

                if trending:
                    # ---- VIP: detailed breakdown per coin ----
                    vip_lines = [f"📡 VIP MARKET INSIGHT — {time.strftime('%H:%M UTC')}"]
                    for coin in trending:
                        block = build_vip_insight(coin)
                        if block:
                            vip_lines.append(block)
                    try:
                        bot.send_message(VIP_GROUP_ID, "\n\n".join(vip_lines))
                    except Exception as e:
                        print("VIP insight send error:", repr(e))

                    # ---- Free group: lighter, fewer coins, VIP upsell ----
                    free_lines = [f"📊 Hourly Market Update — {time.strftime('%H:%M UTC')}"]
                    for coin in trending[:2]:
                        line = build_free_update(coin)
                        if line:
                            free_lines.append(line)
                    free_lines.append(f"\n💎 Want RSI, trend & support/resistance? Join VIP:\n{VIP_GROUP}")
                    try:
                        bot.send_message(FREE_GROUP_ID, "\n".join(free_lines))
                    except Exception as e:
                        print("Free update send error:", repr(e))
                else:
                    print("Insight poster: no trending coins found this cycle")

        except Exception as e:
            print("Insight Poster Error:", repr(e))

        time.sleep(3600)  # every hour


# ============ PASTE 3: alongside your other Thread(...).start() lines, e.g. near ============
# ============ Thread(target=alert_checker, daemon=True).start()                    ============

    Thread(target=insight_poster, daemon=True).start()
