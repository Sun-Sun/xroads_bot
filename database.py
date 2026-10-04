import sqlite3
import discord
from datetime import datetime, timedelta, timezone
import pytz
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "raids.db")

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Signups table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signups (
            user_id TEXT,
            username TEXT,
            discord_ping TEXT,
            gw2_acc TEXT,
            training_name TEXT,
            roles TEXT,
            comment TEXT,
            signup_date TEXT,
            PRIMARY KEY (user_id, training_name, signup_date)
        )
    ''')

    # Users profile table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            gw2_acc TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaders (
            username TEXT PRIMARY KEY,
            account_name TEXT,
            rank TEXT, -- 'Commander' or 'Aide'
            roles TEXT  -- Comma-separated roles (e.g., 'qheal, aheal, dps')
        )
    ''')

    conn.commit()
    conn.close()

def save_signup(user_id, username, discord_ping, gw2_acc, training_name, roles, comment, signup_date):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO signups (user_id, username, discord_ping, gw2_acc, training_name, roles, comment, signup_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, discord_ping, gw2_acc, training_name, roles, comment, signup_date))
        conn.commit()
    except Exception as e:
        print(f"Database Error: {e}")
        raise e
    finally:
        conn.close()

def save_user_profile(user_id, gw2_acc):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO user_profiles (user_id, gw2_acc) VALUES (?, ?)', (user_id, gw2_acc))
        conn.commit()
    finally:
        conn.close()

def get_user_profile(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT gw2_acc FROM user_profiles WHERE user_id=?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def remove_user_profile(user_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profiles WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def delete_signup(user_id, signup_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM signups 
        WHERE user_id=? AND signup_date=?
    ''', (user_id, signup_date))
    conn.commit()
    conn.close()

def get_signup_by_date(user_id, signup_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM signups 
        WHERE user_id=? AND signup_date=?
    ''', (user_id, signup_date))
    results = cursor.fetchall()
    conn.close()
    return results

def wipe_date(signup_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM signups WHERE signup_date=?", (signup_date,))
    conn.commit()
    conn.close()

def save_leader_profile(username, rank, roles):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO leaders (username, rank, roles)
        VALUES (?, ?, ?)
    ''', (username, rank, roles))
    conn.commit()
    conn.close()

def save_leader_profiles_batch(profiles: list):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.executemany(
            """
            INSERT INTO leaders (username, rank, roles)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                rank = excluded.rank,
                roles = excluded.roles
            """,
            profiles
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ==========================================
# == EMBED CREATION & UPDATING ==
# ==========================================

def create_embed(date, title=None, raiddescription=None, embedcolor=None, startTime="20:00"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Get total unique players signed up
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM signups WHERE signup_date=?", (date,))
    count = cursor.fetchone()[0]

    # 🌟 NEW: 2. Fetch the top 3 most requested bosses to build the Hype Board
    cursor.execute("""
        SELECT training_name, COUNT(*) as signup_count 
        FROM signups 
        WHERE signup_date = ? 
        GROUP BY training_name 
        ORDER BY signup_count DESC 
        LIMIT 3
    """, (date,))
    top_bosses = cursor.fetchall()
    conn.close()

    try:
        tz = pytz.timezone("Europe/Berlin")
        naive_dt = datetime.strptime(f"{date} {startTime}", "%Y-%m-%d %H:%M")
        localized_dt = tz.localize(naive_dt)
        unix_time = int(localized_dt.timestamp())
        discord_time = f"<t:{unix_time}:F> (<t:{unix_time}:R>)"
    except Exception as e:
        print(f"Time conversion error: {e}")
        discord_time = f"{date} at {startTime} CET/CEST"

    if not title:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            title = f"{date_obj.strftime('%A')} Raid Training"
        except:
            title = "Raid Training"

    embed = discord.Embed(
        title=f"⚔️ {title}",
        description=raiddescription or "Click the buttons below to manage your signup.",
        color=embedcolor or discord.Color.blue()
    )
            
    embed.add_field(name="⏰ Start Time", value=discord_time, inline=False)
    
    # 🌟 NEW: Wrapped in a Markdown code block (```) for a background box effect
    if top_bosses:
        hype_text = "```\n"
        for i, (boss, requests) in enumerate(top_bosses):
            display_name = "QTP" if boss == "Qadim the Peerless" else boss
            icon = "🔥" if i == 0 else "📈"
            hype_text += f"{icon} {display_name}: {requests} signup(s)\n"
        hype_text += "```"
    else:
        hype_text = "```\nNo signups yet. Be the first!\n```"

    # Changed inline=False to give the box full width and remove horizontal clutter
    embed.add_field(name="🎯 Trending Bosses", value=hype_text, inline=False)
    
    # Separated total count to its own clean line below the box
    embed.add_field(name="👥 Total Roster Size", value=f"**{count}** Player(s)", inline=False)
    
    embed.set_footer(text="Requirements: Minimum 3 bosses selected | Times are localized to your device.")
    return embed

async def update_raid_embed(interaction: discord.Interaction, training_date: str, message: discord.Message = None):
    """Refreshes the embed by targeting the specific card message."""
    new_embed = create_embed(date=training_date)
    
    target = message or interaction.message

    try:
        if target:
            await target.edit(embed=new_embed)
        else:
            msg = await interaction.original_response()
            await msg.edit(embed=new_embed)
    except Exception as e:
        print(f"Embed Update Error: {e}")