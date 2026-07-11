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


cursor.execute("DROP TABLE IF EXISTS deposits")

cursor.execute("""
CREATE TABLE deposits(
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    coin TEXT,
    network TEXT,
    txid TEXT,
    amount DOUBLE PRECISION,
    status TEXT DEFAULT 'pending',
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
    user_id=str(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()

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
        SELECT id, user_id, coin, txid
        FROM deposits
        WHERE status='pending'
        ORDER BY id
    """)

    rows = cursor.fetchall()

    conn.commit()
    cursor.close()
    conn.close()

    return rows

    
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
        
