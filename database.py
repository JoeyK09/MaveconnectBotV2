import os
import psycopg2
from config import PICKAXES

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not found")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def get_cursor():
    conn = get_connection()
    return conn, conn.cursor()

conn, cursor = get_cursor()

# ================= CREATE TABLE =================

PICKAXES = {
    1: {"name": "Wood", "price": 0, "bonus": 0},
    2: {"name": "Stone", "price": 500, "bonus": 5},
    3: {"name": "Bronze", "price": 2000, "bonus": 10},
    4: {"name": "Iron", "price": 5000, "bonus": 20},
    5: {"name": "Gold", "price": 10000, "bonus": 35},
    6: {"name": "Diamond", "price": 25000, "bonus": 50},
}

cursor.execute("""
CREATE TABLE IF NOT EXISTS plats(
    user_id TEXT PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    pickaxe INTEGER DEFAULT 1,
    last_daily BIGINT DEFAULT 0,
    last_mine BIGINT DEFAULT 0,
    wins INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    referred_by TEXT,
    mining_bonus INTEGER DEFAULT 0
)
""")

cursor.execute("""
ALTER TABLE plats
ADD COLUMN IF NOT EXISTS mave_coins BIGINT DEFAULT 0;

ALTER TABLE plats
ADD COLUMN IF NOT EXISTS games_played INTEGER DEFAULT 0;

ALTER TABLE plats
ADD COLUMN IF NOT EXISTS games_won INTEGER DEFAULT 0;

ALTER TABLE plats
ADD COLUMN IF NOT EXISTS win_streak INTEGER DEFAULT 0;

ALTER TABLE plats
ADD COLUMN IF NOT EXISTS highest_win BIGINT DEFAULT 0;

ALTER TABLE plats
ADD COLUMN IF NOT EXISTS last_daily_bonus TIMESTAMP;
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS game_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    game_name VARCHAR(50) NOT NULL,
    bet BIGINT DEFAULT 0,
    reward BIGINT DEFAULT 0,
    result VARCHAR(20) NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cursor.execute("""
ALTER TABLE plats
ADD COLUMN IF NOT EXISTS vip BOOLEAN DEFAULT FALSE
""")

cursor.execute("""
ALTER TABLE plats
ADD COLUMN IF NOT EXISTS vip_plan TEXT DEFAULT 'Free'
""")

cursor.execute("""
ALTER TABLE plats
ADD COLUMN IF NOT EXISTS vip_start TIMESTAMP
""")

cursor.execute("""
ALTER TABLE plats
ADD COLUMN IF NOT EXISTS vip_expiry TIMESTAMP
""")

cursor.execute("""
ALTER TABLE deposits
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS favorites(
    user_id TEXT,
    coin TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS alerts(
    user_id TEXT NOT NULL,
    coin TEXT NOT NULL,
    target DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS achievements(
    user_id TEXT,
    achievement TEXT,
    PRIMARY KEY(user_id, achievement)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS deposits(
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    coin TEXT NOT NULL,
    network TEXT NOT NULL,
    txid TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS withdrawals(
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    phone TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions(
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS crypto_withdrawals(
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    coin TEXT NOT NULL,
    network TEXT NOT NULL,
    address TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_payments(
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    method TEXT NOT NULL,
    reference TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stakes(
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    rate DOUBLE PRECISION NOT NULL,
    days INTEGER NOT NULL,
    reward DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'active',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP NOT NULL,
    claimed_at TIMESTAMP
)
""")

cursor.execute("""
ALTER TABLE stakes
ADD COLUMN IF NOT EXISTS notified BOOLEAN DEFAULT FALSE
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders_sent(
    user_id TEXT NOT NULL,
    reminder_type TEXT NOT NULL,
    sent_date DATE NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY(user_id, reminder_type, sent_date)
)
""")

# ---- Sports Prediction Game ----
# IMPORTANT DESIGN NOTE: this is a free-to-play prediction game, not
# betting. Users never put Plats at risk — there's no "stake" or "wager"
# field anywhere here, only an optional flat reward for guessing right.
# That distinction is what keeps this out of sports-betting territory,
# which requires gambling licensing almost everywhere. Do not add a
# stake/wager amount to this feature without getting real legal advice
# first — that would turn it into licensed-gambling territory.

cursor.execute("""
CREATE TABLE IF NOT EXISTS prediction_events(
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    options TEXT NOT NULL,
    reward DOUBLE PRECISION NOT NULL DEFAULT 20,
    status TEXT DEFAULT 'open',
    correct_option TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS prediction_picks(
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    choice TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, user_id)
)
""")

conn = get_connection()
cur = conn.cursor()

#cur.execute("""
#ALTER TABLE users
#ADD COLUMN IF NOT EXISTS vip BOOLEAN DEFAULT FALSE;
#""")

conn.commit()
cursor.close()
conn.close()

# ================= FUNCTIONS =================

def get_profile(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT balance, xp, level, pickaxe,
               last_daily, last_mine, wins,streak
        FROM plats
        WHERE user_id=%s
    """, (str(user_id),))

    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "INSERT INTO plats(user_id) VALUES(%s)",
            (user_id,)
        )

        row = (0, 0, 1, 1, 0, 0, 0, 0)

    cursor.close()
    conn.close()

    return row
    

def get_balance(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance FROM plats WHERE user_id=%s",
       (str(user_id),)
    )

    row = cursor.fetchone()

    print("Database returned now:",row)

    cursor.close()
    conn.close()

    return row[0] if row else 0
    

def add_plats(user_id, amount):
    user_id= str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    balance = get_balance(user_id)

    cursor.execute("""
        INSERT INTO plats(user_id, balance)
        VALUES(%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET balance=%s
    """, (
        user_id,
        balance + amount,
        balance + amount
    ))

    conn.commit()
    cursor.close()
    conn.close()


def remove_plats(user_id, amount):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    balance = get_balance(user_id)
    new_balance = max(0, balance - amount)

    cursor.execute("""
        UPDATE plats
        SET balance=%s
        WHERE user_id=%s
    """, (
        new_balance,
        user_id
    ))

    conn.commit()
    cursor.close()
    conn.close()


def update_mine(user_id, balance, xp, level, pickaxe, last_mine):
    user_id= str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET balance=%s,
            xp=%s,
            level=%s,
            pickaxe=%s,
            last_mine=%s
        WHERE user_id=%s
    """, (
        balance,
        xp,
        level,
        pickaxe,
        last_mine,
        user_id
    ))

    conn.commit()
    cursor.close()
    conn.close()


def update_pickaxe(user_id, balance, pickaxe):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET balance=%s,
            pickaxe=%s
        WHERE user_id=%s
    """, (
        balance,
        pickaxe,
        user_id
    ))

    conn.commit()
    cursor.close()
    conn.close()


def update_daily(user_id, balance, last_daily, streak):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET balance=%s,
            last_daily=%s,
            streak=%s
        WHERE user_id=%s
    """, (
        balance,
        last_daily,
        streak,
        user_id
    ))

    conn.commit()
    cursor.close()
    conn.close()
    

def add_win(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET wins = wins + 1
        WHERE user_id=%s
    """, (str(user_id),))

    conn.commit()
    cursor.close()
    conn.close()
    

def leaderboard(limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, balance
        FROM plats
        ORDER BY balance DESC
        LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()

    conn.commit()
    cursor.close()
    conn.close()

    return rows
    

def add_favorite(user, coin):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM favorites
        WHERE user_id=%s
        AND coin=%s
        """,
        (str(user), coin)
    )

    if cursor.fetchone():
        cursor.close()
        conn.close()
        return

    cursor.execute(
        """
        INSERT INTO favorites(user_id, coin)
        VALUES(%s, %s)
        """,
        (str(user), coin)
    )

    conn.commit()
    cursor.close()
    conn.close()
    

def get_favorites(user):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT coin FROM favorites WHERE user_id=%s",
        (str(user),)
    )

    rows = [x[0] for x in cursor.fetchall()]

    cursor.close()
    conn.close()

    return rows


def add_alert(user, coin, target):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO alerts(user_id, coin, target) VALUES (%s,%s,%s)",
        (str(user), coin, target)
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_alerts():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id, coin, target FROM alerts"
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def delete_alert(user, coin, target):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM alerts WHERE user_id=%s AND coin=%s AND target=%s",
        (str(user), coin, target)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    
def has_achievement(user_id, achievement):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1 FROM achievements
        WHERE user_id=%s AND achievement=%s
    """, (user_id, achievement))

    found = cursor.fetchone() is not None

    cursor.close()
    conn.close()

    return found

def unlock_achievement(user_id, achievement):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO achievements(user_id, achievement)
        VALUES(%s, %s)
        ON CONFLICT DO NOTHING
    """, (user_id, achievement))

    cursor.close()
    conn.close()


def get_pickaxe(user_id):
    user_id = str(user_id)

    get_profile(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT pickaxe FROM plats WHERE user_id=%s",
        (user_id,)
    )

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return row[0] if row else 1


def get_mining_bonus(user):
    balance, xp, level, pickaxe, last_daily, last_mine, wins, streak = get_profile(user)

    return PICKAXES[pickaxe]["bonus"]


def create_deposit(user_id, coin, network, txid, amount):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO deposits
        (user_id, coin, network, txid, amount)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user_id,
        coin,
        network,
        txid,
        amount
    ))

    conn.commit()
    cursor.close()
    conn.close()


def add_withdrawal(user_id, amount, phone):
    """Creates a pending withdrawal AND locks the funds immediately by
    deducting the balance — closing a gap where the same Plats could be
    spent elsewhere while a manual M-Pesa payout was also pending.
    Returns False if the user doesn't have enough balance."""

    user_id = str(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT balance FROM plats WHERE user_id=%s", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    if balance < amount:
        cursor.close()
        conn.close()
        return False

    cursor.execute("""
        UPDATE plats SET balance = balance - %s WHERE user_id=%s
    """, (amount, user_id))

    cursor.execute("""
        INSERT INTO withdrawals(user_id, amount, phone)
        VALUES(%s, %s, %s)
    """, (
        user_id,
        amount,
        phone
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return True


def get_pending_withdrawals():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_id, amount, phone
        FROM withdrawals
        WHERE status='pending'
        ORDER BY id
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def approve_withdrawal(withdrawal_id):
    """Marks a withdrawal as paid. Funds were already locked at request
    time, so this just finalizes the record. Returns (user_id, amount)."""

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, amount FROM withdrawals
            WHERE id=%s AND status='pending'
        """, (withdrawal_id,))

        row = cursor.fetchone()

        if not row:
            return None

        user_id, amount = row

        cursor.execute("""
            UPDATE withdrawals SET status='paid' WHERE id=%s
        """, (withdrawal_id,))

        conn.commit()
        return (str(user_id), amount)

    except Exception as e:
        conn.rollback()
        print("approve_withdrawal error:", e)
        return None

    finally:
        cursor.close()
        conn.close()


def reject_withdrawal(withdrawal_id):
    """Rejects a withdrawal and refunds the locked balance back to the user."""

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, amount FROM withdrawals
            WHERE id=%s AND status='pending'
        """, (withdrawal_id,))

        row = cursor.fetchone()

        if not row:
            return None

        user_id, amount = row

        cursor.execute("""
            UPDATE withdrawals SET status='rejected' WHERE id=%s
        """, (withdrawal_id,))

        cursor.execute("""
            UPDATE plats SET balance = balance + %s WHERE user_id=%s
        """, (amount, user_id))

        conn.commit()
        return (str(user_id), amount)

    except Exception as e:
        conn.rollback()
        print("reject_withdrawal error:", e)
        return None

    finally:
        cursor.close()
        conn.close()


def add_deposit(user_id, coin, txid):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO deposits(user_id, coin, txid)
        VALUES(%s, %s, %s)
    """, (
        user_id,
        coin,
        txid
    ))

    conn.commit()
    cursor.close()
    conn.close()


def get_pending_deposits():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_id, coin, network, txid, amount
        FROM deposits
        WHERE status='pending'
        ORDER BY id
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def approve_deposit(deposit_id):
    """Approve a pending deposit by its row id and credit the user's Plats balance.

    Returns (user_id, amount) on success, or None if there was no matching
    pending deposit.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, amount
            FROM deposits
            WHERE id=%s
            AND status='pending'
        """, (deposit_id,))

        row = cursor.fetchone()

        if not row:
            return None

        user_id, amount = row
        user_id = str(user_id)

        cursor.execute("""
            UPDATE deposits
            SET status='approved'
            WHERE id=%s
        """, (deposit_id,))

        cursor.execute("""
            UPDATE plats
            SET balance = balance + %s
            WHERE user_id=%s
        """, (amount, user_id))

        conn.commit()
        return (user_id, amount)

    except Exception as e:
        conn.rollback()
        print("approve_deposit error:", e)
        return None

    finally:
        cursor.close()
        conn.close()


def reject_deposit(deposit_id):
    """Reject a pending deposit by its row id.

    Returns the user_id on success, or None if there was no matching
    pending deposit.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id
            FROM deposits
            WHERE id=%s
            AND status='pending'
        """, (deposit_id,))

        row = cursor.fetchone()

        if not row:
            return None

        user_id = str(row[0])

        cursor.execute("""
            UPDATE deposits
            SET status='rejected'
            WHERE id=%s
        """, (deposit_id,))

        conn.commit()
        return user_id

    except Exception as e:
        conn.rollback()
        print("reject_deposit error:", e)
        return None

    finally:
        cursor.close()
        conn.close()

    
def credit_balance(user_id, amount):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET balance = balance + %s
        WHERE user_id = %s
    """, (amount, user_id))

    conn.commit()
    cursor.close()
    conn.close()

def txid_exists(txid):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM deposits
        WHERE txid = %s
        LIMIT 1
    """, (txid,))

    exists = cursor.fetchone() is not None

    cursor.close()
    conn.close()

    return exists

def update_deposit_status(txid, status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE deposits
        SET status=%s,
            approved_at=CURRENT_TIMESTAMP
        WHERE txid=%s
    """, (status, txid))

    conn.commit()
    cursor.close()
    conn.close()


def add_transaction(user_id, tx_type, amount, description):
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO transactions
        (user_id, type, amount, description)
        VALUES (%s, %s, %s, %s)
    """, (
        user_id,
        tx_type,
        amount,
        description
    ))

    conn.commit()
    cursor.close()
    conn.close()


def add_crypto_withdrawal(user_id, coin, network, address, amount):
    user_id=str(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO crypto_withdrawals
        (user_id, coin, network, address, amount)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        user_id,
        coin,
        network,
        address,
        amount
    ))

    conn.commit()

    cursor.close()
    conn.close()


def is_vip(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT vip, vip_expiry
        FROM plats
        WHERE user_id=%s
    """, (str(user_id),))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return False

    vip, expiry = row

    if not vip:
        return False

    if expiry and expiry < datetime.now():
        remove_vip(user_id)
        return False

    return True


def activate_vip(user_id, plan, expiry):
    user_id=str(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET
            vip=TRUE,
            vip_plan=%s,
            vip_start=NOW(),
            vip_expiry=%s
        WHERE user_id=%s
    """, (
        plan,
        expiry,
        user_id
    ))

    conn.commit()

    cursor.close()
    conn.close()


def remove_vip(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET
            vip=FALSE,
            vip_plan='Free',
            vip_start=NULL,
            vip_expiry=NULL
        WHERE user_id=%s
    """, (str(user_id),))

    conn.commit()

    cursor.close()
    conn.close()


def get_vip_info(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT vip,
               vip_plan,
               vip_start,
               vip_expiry
        FROM plats
        WHERE user_id=%s
    """, (str(user_id),))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return row


def save_vip_payment(user_id, plan, amount, method, reference):
    user_id = str(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO vip_payments
        (user_id, plan, amount, method, reference)
        VALUES(%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        user_id,
        plan,
        amount,
        method,
        reference
    ))

    payment_id = cursor.fetchone()[0]

    conn.commit()

    cursor.close()
    conn.close()

    return payment_id

from datetime import datetime, timedelta

VIP_PLAN_DURATIONS = {
    "basic": 30,
    "premium": 90,
    "elite": 365,
}


def get_vip_payment_history(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT plan, amount, method, status, created_at
        FROM vip_payments
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 10
    """, (str(user_id),))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def save_game_history(user_id, game_name, bet, reward, result):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO game_history(user_id, game_name, bet, reward, result)
        VALUES(%s, %s, %s, %s, %s)
    """, (
        int(user_id),
        game_name,
        bet,
        reward,
        result
    ))

    conn.commit()
    cursor.close()
    conn.close()


def get_game_history(user_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT game_name, bet, reward, result, played_at
        FROM game_history
        WHERE user_id=%s
        ORDER BY played_at DESC
        LIMIT %s
    """, (int(user_id), limit))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def create_stake(user_id, amount, rate, days):
    from datetime import datetime, timedelta

    user_id = str(user_id)
    reward = round(amount * rate, 2)
    end_time = datetime.now() + timedelta(days=days)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE plats
        SET balance = balance - %s
        WHERE user_id=%s
    """, (amount, user_id))

    cursor.execute("""
        INSERT INTO stakes(user_id, amount, rate, days, reward, end_time)
        VALUES(%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, amount, rate, days, reward, end_time))

    stake_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return stake_id


def get_user_stakes(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, amount, rate, days, reward, status, start_time, end_time
        FROM stakes
        WHERE user_id=%s
        ORDER BY start_time DESC
    """, (str(user_id),))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def claim_stake(stake_id, user_id):
    """Claim a matured stake, returning principal + reward to the balance.

    Returns (amount, reward) on success, or a string error reason on
    failure ('not_found', 'not_matured', 'already_claimed').
    """

    from datetime import datetime

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT amount, reward, status, end_time
            FROM stakes
            WHERE id=%s AND user_id=%s
        """, (stake_id, str(user_id)))

        row = cursor.fetchone()

        if not row:
            return "not_found"

        amount, reward, status, end_time = row

        if status != "active":
            return "already_claimed"

        if datetime.now() < end_time:
            return "not_matured"

        cursor.execute("""
            UPDATE stakes
            SET status='claimed', claimed_at=NOW()
            WHERE id=%s
        """, (stake_id,))

        cursor.execute("""
            UPDATE plats
            SET balance = balance + %s
            WHERE user_id=%s
        """, (amount + reward, str(user_id)))

        conn.commit()
        return (amount, reward)

    except Exception as e:
        conn.rollback()
        print("claim_stake error:", e)
        return "error"

    finally:
        cursor.close()
        conn.close()


def get_active_stake_liability():
    """Total Plats currently promised out to active (unclaimed) stakes —
    principal + reward. Useful for the admin to see real exposure."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(SUM(amount + reward), 0)
        FROM stakes
        WHERE status='active'
    """)

    total = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return total


def register_new_user(user_id, referrer_id=None):
    """Creates the user's row if this is their first time using the bot,
    attaching whoever referred them (if anyone, and not themselves).

    Returns True if this was a brand-new signup, False if the user
    already existed (so referral/signup bonuses only ever fire once).
    """

    user_id = str(user_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM plats WHERE user_id=%s", (user_id,))
    exists = cursor.fetchone()

    if exists:
        cursor.close()
        conn.close()
        return False

    if referrer_id is not None:
        referrer_id = str(referrer_id)
        if referrer_id == user_id:
            referrer_id = None

    cursor.execute(
        "INSERT INTO plats(user_id, referred_by) VALUES(%s, %s)",
        (user_id, referrer_id)
    )

    cursor.close()
    conn.close()

    return True


def get_referrer(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT referred_by FROM plats WHERE user_id=%s",
        (str(user_id),)
    )

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return row[0] if row else None


def get_referral_count(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM plats WHERE referred_by=%s",
        (str(user_id),)
    )

    total = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return total


def count_approved_deposits(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM deposits WHERE user_id=%s AND status='approved'",
        (str(user_id),)
    )

    total = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return total


def get_users_needing_daily_reminder():
    """Users whose 24h daily-bonus cooldown has passed and who haven't
    already been reminded today."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.user_id
        FROM plats p
        WHERE p.last_daily IS NOT NULL
        AND p.last_daily > 0
        AND EXTRACT(EPOCH FROM NOW()) - p.last_daily >= 86400
        AND NOT EXISTS (
            SELECT 1 FROM reminders_sent r
            WHERE r.user_id = p.user_id
            AND r.reminder_type = 'daily'
            AND r.sent_date = CURRENT_DATE
        )
    """)

    rows = [r[0] for r in cursor.fetchall()]

    cursor.close()
    conn.close()

    return rows


def mark_reminder_sent(user_id, reminder_type):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reminders_sent(user_id, reminder_type, sent_date)
        VALUES(%s, %s, CURRENT_DATE)
        ON CONFLICT DO NOTHING
    """, (str(user_id), reminder_type))

    cursor.close()
    conn.close()


def get_newly_matured_stakes():
    """Active stakes that just matured and haven't been notified about yet."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_id, amount, reward
        FROM stakes
        WHERE status='active'
        AND notified=FALSE
        AND end_time <= NOW()
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def mark_stake_notified(stake_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE stakes SET notified=TRUE WHERE id=%s",
        (stake_id,)
    )

    cursor.close()
    conn.close()


def create_prediction_event(title, options, reward=20):
    """options: list of strings, e.g. ['Arsenal', 'Draw', 'Chelsea']"""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO prediction_events(title, options, reward)
        VALUES(%s, %s, %s)
        RETURNING id
    """, (title, "|".join(options), reward))

    event_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return event_id


def get_open_prediction_events():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, options, reward
        FROM prediction_events
        WHERE status='open'
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [(r[0], r[1], r[2].split("|"), r[3]) for r in rows]


def get_prediction_event(event_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, options, reward, status, correct_option
        FROM prediction_events
        WHERE id=%s
    """, (event_id,))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return None

    return (row[0], row[1], row[2].split("|"), row[3], row[4], row[5])


def get_user_pick(event_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT choice FROM prediction_picks
        WHERE event_id=%s AND user_id=%s
    """, (event_id, str(user_id)))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return row[0] if row else None


def submit_prediction(event_id, user_id, choice):
    """Returns True if the pick was recorded, False if this user already
    picked for this event or the event isn't open anymore."""

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT status FROM prediction_events WHERE id=%s",
            (event_id,)
        )
        row = cursor.fetchone()

        if not row or row[0] != "open":
            return False

        cursor.execute("""
            INSERT INTO prediction_picks(event_id, user_id, choice)
            VALUES(%s, %s, %s)
            ON CONFLICT (event_id, user_id) DO NOTHING
        """, (event_id, str(user_id), choice))

        if cursor.rowcount == 0:
            return False

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        print("submit_prediction error:", e)
        return False

    finally:
        cursor.close()
        conn.close()


def resolve_prediction_event(event_id, correct_option):
    """Marks the event resolved and pays the flat reward to everyone who
    picked correctly. Returns (reward, [winner_user_ids]) or None if the
    event doesn't exist / was already resolved."""

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT reward, status FROM prediction_events WHERE id=%s
        """, (event_id,))

        row = cursor.fetchone()

        if not row or row[1] != "open":
            return None

        reward = row[0]

        cursor.execute("""
            UPDATE prediction_events
            SET status='resolved', correct_option=%s, resolved_at=NOW()
            WHERE id=%s
        """, (correct_option, event_id))

        cursor.execute("""
            SELECT user_id FROM prediction_picks
            WHERE event_id=%s AND choice=%s
        """, (event_id, correct_option))

        winners = [r[0] for r in cursor.fetchall()]

        for winner_id in winners:
            cursor.execute("""
                UPDATE plats SET balance = balance + %s WHERE user_id=%s
            """, (reward, winner_id))

        conn.commit()
        return (reward, winners)

    except Exception as e:
        conn.rollback()
        print("resolve_prediction_event error:", e)
        return None

    finally:
        cursor.close()
        conn.close()


def get_total_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM plats")
    total = cur.fetchone()[0]

    cur.close()
    conn.close()
    return total


def get_total_vip():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM plats WHERE vip=TRUE")
    total = cur.fetchone()[0]

    cur.close()
    conn.close()
    return total


def get_pending_vip_payments():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM vip_payments
        WHERE LOWER(status)='pending'
    """)

    total = cur.fetchone()[0]

    cur.close()
    conn.close()

    return total


def count_pending_withdrawals():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM withdrawals
        WHERE status='pending'
    """)

    total = cur.fetchone()[0]

    cur.close()
    conn.close()
    return total


def get_all_pending_vip_payments():
    """Returns a list of dicts for every pending VIP payment, newest last."""

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, plan, amount, method, reference
        FROM vip_payments
        WHERE LOWER(status) = 'pending'
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    payments = []

    for row in rows:
        payments.append({
            "id": row[0],
            "user_id": row[1],
            "plan": row[2],
            "amount": row[3],
            "payment_method": row[4],
            "reference": row[5]
        })

    return payments


def approve_vip_payment(payment_id):
    """Approve a specific VIP payment by its row id and activate VIP for that user.

    Returns (user_id, plan) on success, or None if there was no matching
    pending payment.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, plan
            FROM vip_payments
            WHERE id=%s
            AND LOWER(status)='pending'
        """, (payment_id,))

        row = cursor.fetchone()

        if not row:
            return None

        user_id, plan = row
        user_id = str(user_id)

        days = VIP_PLAN_DURATIONS.get(plan.lower(), 30)
        expiry = datetime.now() + timedelta(days=days)

        cursor.execute("""
            UPDATE vip_payments
            SET status='approved'
            WHERE id=%s
        """, (payment_id,))

        cursor.execute("""
            UPDATE plats
            SET
                vip=TRUE,
                vip_plan=%s,
                vip_start=NOW(),
                vip_expiry=%s
            WHERE user_id=%s
        """, (plan, expiry, user_id))

        conn.commit()
        return (user_id, plan)

    except Exception as e:
        conn.rollback()
        print("approve_vip_payment error:", e)
        return None

    finally:
        cursor.close()
        conn.close()


def reject_vip_payment(payment_id):
    """Reject a specific VIP payment by its row id.

    Returns the user_id on success, or None if there was no matching
    pending payment.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id
            FROM vip_payments
            WHERE id=%s
            AND LOWER(status)='pending'
        """, (payment_id,))

        row = cursor.fetchone()

        if not row:
            return None

        user_id = str(row[0])

        cursor.execute("""
            UPDATE vip_payments
            SET status='rejected'
            WHERE id=%s
        """, (payment_id,))

        conn.commit()
        return user_id

    except Exception as e:
        conn.rollback()
        print("reject_vip_payment error:", e)
        return None

    finally:
        cursor.close()
        conn.close()
        
