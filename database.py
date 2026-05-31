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
        conn.commit() # CRITICAL: This pushes the data to the file
    except Exception as e:
        print(f"Database Error: {e}")
        raise e
    finally:
        conn.close()  # CRITICAL: This unlocks the file so create_embed can read it

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
    """Inserts or replaces a leader's profile records."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO leaders (username, rank, roles)
        VALUES (?, ?, ?)
    ''', (username, rank, roles))
    conn.commit()
    conn.close()

def save_leader_profiles_batch(profiles: list):
    """
    Saves a list of leader profiles in a single transactional batch.
    profiles format: [ (username, rank, roles), (username, rank, roles), ... ]
    """
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Using an UPSERT style query (or REPLACE) depending on your schema
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

import sqlite3
import discord
from datetime import datetime
import pytz  # Add this import

def create_embed(date, title=None, raiddescription=None, embedcolor=None, startTime="20:00"):
    # 1. Database count logic
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM signups WHERE signup_date=?", (date,))
    count = cursor.fetchone()[0]
    conn.close()

    try:
        # 2. Define the European Timezone (Berlin/Paris/Rome/etc are all the same)
        tz = pytz.timezone("Europe/Berlin")
        
        # 3. Create a "Naive" datetime object from your strings
        naive_dt = datetime.strptime(f"{date} {startTime}", "%Y-%m-%d %H:%M")
        
        # 4. "Localize" it. This is where pytz automatically checks the date for DST
        localized_dt = tz.localize(naive_dt)
        
        # 5. Get the Unix Timestamp
        unix_time = int(localized_dt.timestamp())
        
        # Discord Dynamic Format
        discord_time = f"<t:{unix_time}:F> (<t:{unix_time}:R>)"
    except Exception as e:
        print(f"Time conversion error: {e}")
        discord_time = f"{date} at {startTime} CET/CEST"

    # 3. Build Embed (rest of your existing code)
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
    embed.add_field(name="👥 Current Signups", value=f"{count} Player(s)", inline=True)
    embed.add_field(name="📜 Requirements", value="Minimum 3 bosses selected", inline=True)
    
    embed.set_footer(text="Times are localized to your device's timezone.")
    return embed

async def update_raid_embed(interaction: discord.Interaction, training_date: str, message: discord.Message = None):
    """Refreshes the embed by targeting the specific card message."""
    from database import create_embed
    new_embed = create_embed(date=training_date)
    
    # 1. Use the explicitly passed message first (most reliable)
    target = message or interaction.message

    try:
        if target:
            await target.edit(embed=new_embed)
        else:
            # 2. Fallback for interactions where the message wasn't passed
            msg = await interaction.original_response()
            await msg.edit(embed=new_embed)
    except Exception as e:
        print(f"Embed Update Error: {e}")