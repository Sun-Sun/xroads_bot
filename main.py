import os
import discord
from discord import app_commands
from discord.ext import commands
import csv
import io
import sqlite3
from dotenv import load_dotenv
from database import setup_db, save_signup, delete_signup, create_embed, update_raid_embed, wipe_date
from datetime import datetime, timedelta
import pytz

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        setup_db()
        MY_GUILD = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)

        # Fetch all unique dates currently in your database
        conn = sqlite3.connect('raids.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT signup_date FROM signups")
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Register a view for every date so buttons work after a restart
        for date in dates:
            self.add_view(PersistentSignupView(training_date=date))

class DeleteConfirmationView(discord.ui.View):
    def __init__(self, training_date, original_message):
        super().__init__(timeout=60) # Times out after 1 minute
        self.training_date = training_date
        self.original_message = original_message

    @discord.ui.button(label="Confirm Delete & Wipe", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Clear DB
        wipe_date(self.training_date)
        # 2. Delete the actual Raid Card
        await self.original_message.delete()
        # 3. Clean up the confirmation message
        await interaction.response.edit_message(content=f"🗑️ Session for {self.training_date} has been fully removed.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Cancelled. No changes made.", view=None)

class PersistentSignupView(discord.ui.View):
    def __init__(self, training_date: str, is_locked: bool = False):
        super().__init__(timeout=None)
        self.training_date = training_date
        self.is_locked = is_locked

        # We manually set the custom_id to include the date
        # This tells Discord EXACTLY which date this button belongs to
        self.signup.custom_id = f"signup_{training_date}"
        self.signout.custom_id = f"signout_{training_date}"
        self.check_signup.custom_id = f"check_{training_date}"
        self.lock_toggle.custom_id = f"lock_{training_date}"
        self.remove_card.custom_id = f"remove_{training_date}"

        # Visually disable Sign Up if locked
        if self.is_locked:
            self.signup.disabled = True
            self.signup.label = "Locked 🔒"
            self.lock_toggle.label = "🔓 Unlock"
            self.lock_toggle.style = discord.ButtonStyle.green

    @discord.ui.button(label="Sign Up", style=discord.ButtonStyle.green)
    async def signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        user_role_names = [role.name for role in interaction.user.roles]
        
        # They are allowed full access if they have any role higher than Rookie
        ADVANCED_ROLES = ["Regular", "Adventurer", "Legend", "Commander", "Aide", "Innkeeper", "Bartender", "Squadmaker"]
        is_regular = any(role in user_role_names for role in ADVANCED_ROLES)
        
        # Fallback: If they lack advanced roles but have the Rookie role, gate them
        # (If your server has no tag roles at all, default to True or False depending on safety preference)
        if not is_regular and "Rookie" in user_role_names:
            is_regular = False
        elif not is_regular:
            # Default fallback for users with no setup roles yet
            is_regular = False

        from views import UnifiedBossView
        view = UnifiedBossView(is_regular, self.training_date, interaction.message)
        
        if is_regular:
            msg_text = "Check the bosses you want to train (use multiple menus if needed):"
        else:
            msg_text = "🔰 **Rookie Tier Menu:** You only have access to Beginner-classified training runs."

        await interaction.response.send_message(msg_text, view=view, ephemeral=True)
    
    @discord.ui.button(label="Sign Out", style=discord.ButtonStyle.red)
    async def signout(self, interaction: discord.Interaction, button: discord.ui.Button):
        from database import delete_signup, update_raid_embed
        await interaction.response.defer(ephemeral=True)
        
        delete_signup(str(interaction.user.id), self.training_date)
        
        # Explicitly pass interaction.message (the card the button is on)
        await update_raid_embed(interaction, self.training_date, message=interaction.message)
        
        await interaction.followup.send(f"✅ Removed from {self.training_date}.", ephemeral=True)

    @discord.ui.button(label="📋 Check Signup", style=discord.ButtonStyle.blurple)
    async def check_signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        from database import get_signup_by_date
        signups = get_signup_by_date(str(interaction.user.id), self.training_date)

        if not signups:
           return await interaction.response.send_message("❌ You are not signed up for this date.", ephemeral=True)
        
        # Since GW2 Acc and Discord info are the same for all rows, we take them from the first entry
        # Based on the SELECT order in database.py: 0:acc, 1:user, 2:ping, 3:boss, 4:roles, 5:comm
        first = signups[0]
        
        # Build a list of all bosses signed up for
        boss_list = "\n".join([f"• **{s[4]}** (Roles: {s[5] or 'N/A'})" for s in signups])
        
        # We take the comment from the first entry as well (or you could list them all)
        comment = first[6] if first[6] else "No comment provided"

        response_text = (
            f"📋 **Your Signup Details for {self.training_date}:**\n\n"
            f"**GW2 Account:** `{first[3]}`\n"
            f"**Discord:** {first[1]} ({first[2]})\n\n"
            f"**Bosses & Roles:**\n{boss_list}\n\n"
            f"**Comment:** {comment}"
        )

        await interaction.response.send_message(response_text, ephemeral=True)


    # --- STAFF ONLY BUTTONS ---
    
    @discord.ui.button(label="🔒 Lock", style=discord.ButtonStyle.secondary, row=1)
    async def lock_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        STAFF = ["Innkeeper", "Squadmaker"]
        if not any(role.name in STAFF for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        self.is_locked = not self.is_locked
        
        # We refresh the embed to show the locked status
        embed = create_embed(date=self.training_date)
        if self.is_locked:
            embed.description = "🔒 **Signups are currently locked.**"
            embed.color = discord.Color.red()
        
        await interaction.message.edit(embed=embed, view=PersistentSignupView(self.training_date, self.is_locked))
        await interaction.response.send_message(f"✅ Session {'locked' if self.is_locked else 'unlocked'}.", ephemeral=True)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def remove_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        STAFF = ["Innkeeper", "Squadmaker"]
        if not any(role.name in STAFF for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        view = DeleteConfirmationView(self.training_date, interaction.message)
        await interaction.response.send_message(
            content=f"⚠️ **Are you sure?** This will delete the card and wipe all signups for **{self.training_date}**.",
            view=view,
            ephemeral=True
        )

class MondayCorrectionView(discord.ui.View):
    def __init__(self, suggested_monday, original_interaction):
        super().__init__(timeout=60)
        self.suggested_monday = suggested_monday
        self.original_interaction = original_interaction

    @discord.ui.button(label="Yes, use this Monday", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We call a modified version of your setup logic here
        await interaction.response.defer(ephemeral=True)
        # Assuming you have a function called run_weekly_setup
        await run_weekly_setup(interaction, self.suggested_monday)
        await interaction.edit_original_response(content=f"✅ Setup complete for week of {self.suggested_monday}.", view=None)

    @discord.ui.button(label="No, cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Setup cancelled. Please provide a valid Monday.", view=None)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
async def run_weekly_setup(interaction: discord.Interaction, monday_date: str):
    # This function would contain the logic to create the Tuesday, Thursday, and Saturday sessions based on the provided Monday
    try:
        base_date = datetime.strptime(monday_date, "%Y-%m-%d")
        for offset in [1, 3, 5]:  # Tuesday, Thursday, Saturday
            target_date = (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")
            embed = create_embed(date=target_date)
            await interaction.channel.send(embed=embed, view=PersistentSignupView(training_date=target_date))
    except Exception as e:
        await interaction.followup.send(f"❌ Error during setup: {e}", ephemeral=True)


# ==========================================
# SLASH COMMANDS
# ==========================================

bot = MyBot()

@bot.tree.command(name="setup_week", description="Automatically setup Tuesday, Thursday, and Saturday signups")
@app_commands.describe(monday_date="Enter the Monday of the week (YYYY-MM-DD), The bot will create signups for the following Tuesday, Thursday, and Saturday")
async def setup_week(interaction: discord.Interaction, monday_date: str):

    await interaction.response.defer(ephemeral=True) # Acknowledge the command to avoid timeout while processing

    try:
        # Convert the input string into a date object
        start_date = datetime.strptime(monday_date, "%Y-%m-%d")

        if start_date.weekday() != 0:
            # Calculate the Monday of that week (subtract the current weekday)
            monday_of_week = start_date - timedelta(days=start_date.weekday())
            monday_str = monday_of_week.strftime("%Y-%m-%d")
            
            view = MondayCorrectionView(suggested_monday=monday_str, original_interaction=interaction)
            return await interaction.followup.send(
                f"❓ The date you provided ({monday_date}) is a {start_date.strftime('%A')}.\n"
                f"Did you mean to setup for **Monday, {monday_str}**?",
                view=view,
                ephemeral=True
            )
        
        # If it's already a Monday, we can proceed directly
        await run_weekly_setup(interaction, monday_date)

        # 2. Confirm to the user that it's finished
        await interaction.followup.send(f"✅ Successfully set up the week of {monday_date}.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="setup_single", description="Setup a single raid session")
@app_commands.describe(date="YYYY-MM-DD", title="Optional Title", start_time="HH:MM in CET (24-hour format, e.g. 20:30)")
async def setup_single(interaction: discord.Interaction, date: str, title: str = None, start_time: str = "20:00"):
    await interaction.response.defer(ephemeral=True)

    try:
        # Validate Date
        datetime.strptime(date, "%Y-%m-%d")
        
        # Validate Time Format
        try:
            datetime.strptime(start_time, "%H:%M")
        except ValueError:
            return await interaction.followup.send("❌ Invalid **Time** format. Please use HH:MM (e.g., 20:00 or 09:30).", ephemeral=True)

        embed = create_embed(date=date, title=title, startTime=start_time)
        await interaction.channel.send(embed=embed, view=PersistentSignupView(training_date=date))
        await interaction.followup.send(f"✅ Raid session set for {date} at {start_time}.", ephemeral=True)

    except ValueError:
        await interaction.followup.send("❌ Invalid **Date** format. Use YYYY-MM-DD.", ephemeral=True)

@bot.tree.command(name="remove_session", description="Remove a raid session and all associated signups")
async def remove_session(interaction: discord.Interaction, date: str):
    await interaction.response.defer(ephemeral=True)

    try:
        conn = sqlite3.connect('raids.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM signups WHERE signup_date=?", (date,))
        conn.commit()
        conn.close()
        await interaction.followup.send(f"✅ Successfully removed the raid session for {date}.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="lock_session", description="Prevent new signups for a specific date")
@app_commands.describe(date="Date to lock (YYYY-MM-DD)")
async def lock_session(interaction: discord.Interaction, date: str):
    await interaction.response.defer(ephemeral=True)
    
    from database import create_embed
    # We generate a fresh embed but change the description to "LOCKED"
    embed = create_embed(date=date)
    embed.description = "🔒 **SIGNUPS ARE NOW CLOSED.**\nThis session is full or the deadline has passed."
    embed.color = discord.Color.red()
    
    # We send a fresh message without a View (buttons) to 'lock' it visually,
    # or you'd need to find the old message and edit it to remove the view.
    await interaction.channel.send(embed=embed)
    await interaction.followup.send(f"✅ Session for {date} is now visually locked.", ephemeral=True)

@bot.tree.command(name="training_download")
@discord.app_commands.describe(day="The training day to download (Format: YYYY-MM-DD). Defaults to today if left blank.")
async def training_download(interaction: discord.Interaction, day: str = None):

    if day is None:
        # Use a specific timezone (e.g., 'Europe/London' or your local time) 
        # to ensure "today" matches when your runs actually happen.
        tz = pytz.timezone('Europe/Berlin') 
        day = datetime.now(tz).strftime('%Y-%m-%d')

    conn = sqlite3.connect('raids.db')
    cursor = conn.cursor()
    # Updated query to include 'comment'
    cursor.execute("SELECT gw2_acc, username, discord_ping, training_name, roles, comment FROM signups WHERE signup_date=?", (day,))
    data = cursor.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Gw2 Account", "Discord Account", "Discord Ping", "Training Name", "Roles", "Comment"])
    
    for row in data:
        row_list = list(row)
        
        # Check the boss name using the dynamic index
        if row_list[3] == "Qadim the Peerless":
            row_list[3] = "QTP"
            
        writer.writerow(row_list)
    
    conn.close()

    output.seek(0)
    file = discord.File(fp=io.BytesIO(output.getvalue().encode()), filename=f"signups.csv")
    await interaction.response.send_message(file=file)

@bot.tree.command(name="profile_view", description="View your saved GW2 account")
async def profile_view(interaction: discord.Interaction):
    from database import get_user_profile
    await interaction.response.defer(ephemeral=True)

    acc = get_user_profile(str(interaction.user.id))
    if acc:
        await interaction.followup.send(f"📋 Your saved account is: `{acc}`", ephemeral=True)
    else:
        await interaction.followup.send("❌ You don't have a saved profile.", ephemeral=True)

@bot.tree.command(name="profile_set", description="Save or update your GW2 account name")
async def profile_set(interaction: discord.Interaction, account_name: str):
    from database import save_user_profile
    await interaction.response.defer(ephemeral=True)

    save_user_profile(str(interaction.user.id), account_name)
    await interaction.followup.send(f"✅ Profile updated to: `{account_name}`", ephemeral=True)

@bot.tree.command(name="profile_remove", description="Delete your saved GW2 account from the bot")
async def profile_remove(interaction: discord.Interaction):
    from database import remove_user_profile
    await interaction.response.defer(ephemeral=True)

    remove_user_profile(str(interaction.user.id))
    await interaction.followup.send("🗑️ Your profile data has been deleted.", ephemeral=True)

@bot.tree.command(name="training_summary", description="See which bosses have the most signups for a specific day")
@discord.app_commands.describe(day="The date to check (Format: YYYY-MM-DD). Defaults to today if left blank.")
async def training_summary(interaction: discord.Interaction, day: str = None):
    await interaction.response.defer(ephemeral=True)

    if day is None:
        # Use a specific timezone (e.g., 'Europe/London' or your local time) 
        # to ensure "today" matches when your runs actually happen.
        tz = pytz.timezone('Europe/Berlin') 
        day = datetime.now(tz).strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('raids.db')
    cursor = conn.cursor()
    
    # This query groups by the boss name and counts how many rows (signups) exist for each
    query = """
        SELECT training_name, COUNT(*) as signup_count 
        FROM signups 
        WHERE signup_date = ? 
        GROUP BY training_name 
        ORDER BY signup_count DESC
    """
    cursor.execute(query, (day,))
    results = cursor.fetchall()
    conn.close()

    if not results:
        return await interaction.followup.send(f"No signups found for `{day}`.", ephemeral=True)

    # Building the response message
    embed = discord.Embed(
        title=f"📊 Training Summary: {day}",
        color=discord.Color.blue()
    )

    summary_text = ""
    for i, (boss, count) in enumerate(results):
        # Apply the QTP fix here too
        display_name = "QTP" if boss == "Qadim the Peerless" else boss
        
        if i == 0:
            summary_text += f"🔥 **Most Popular: {display_name} ({count} signups)**\n"
        else:
            summary_text += f"• {display_name}: {count} signups\n"

    embed.description = summary_text
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="sync_leaders", description="Upload and synchronize your Commander or Aide CSV file")
@discord.app_commands.describe(file="Drag and drop your roster CSV file here")
@discord.app_commands.checks.has_permissions(administrator=True) # Protect the roster from normal users
async def sync_leaders(interaction: discord.Interaction, file: discord.Attachment):
    # Ensure it's a CSV file
    if not file.filename.endswith('.csv'):
        return await interaction.response.send_message("❌ Error: Please upload a valid `.csv` file.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Read the file content directly from Discord's attachments server
        file_bytes = await file.read()
        csv_text = file_bytes.decode('utf-8-sig') # handling potential byte-order-marks gracefully
        
        import csv
        import io
        from database import save_leader_profile
        
        stream = io.StringIO(csv_text)
        reader = csv.DictReader(stream)
        
        # Smart Header detection based on your sheets
        is_aides_sheet = 'Aides' in reader.fieldnames
        detected_rank = "Aide" if is_aides_sheet else "Commander"
        
        sync_count = 0
        for row in reader:
            # Skip empty formatting or meta-description padding rows
            roles_raw = row.get('roles')
            if not roles_raw or str(roles_raw).strip().lower() in ['nan', '']:
                continue
                
            # Pick correct name column based on the specific sheet layout
            if is_aides_sheet:
                name_raw = row.get('Aides') or row.get('Official name')
            else:
                name_raw = row.get('Official name') or row.get('Unnamed: 2')
                
            if name_raw and str(name_raw).strip().lower() not in ['nan', '']:
                clean_name = str(name_raw).strip()
                clean_roles = str(roles_raw).strip().lower()
                
                # Update SQLite database instance records
                save_leader_profile(username=clean_name, rank=detected_rank, roles=clean_roles)
                sync_count += 1
                
        await interaction.followup.send(
            f"✅ **Roster Synchronization Complete!**\n"
            f"Successfully identified layout as **{detected_rank} Sheet**.\n"
            f"Parsed and updated `{sync_count}` leader profiles into `raids.db`.", 
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to parse file due to unexpected formatting error: `{e}`", ephemeral=True)

@bot.tree.command(name="build_squads", description="Visually build and orchestrate raid squads step-by-step")
@discord.app_commands.describe(day="The date to build squads for (Format: YYYY-MM-DD). Defaults to today.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def build_squads(interaction: discord.Interaction, day: str = None):
    await interaction.response.defer(ephemeral=True)
    
    if day is None:
        tz = pytz.timezone('Europe/Berlin') 
        day = datetime.now(tz).strftime('%Y-%m-%d')
        
    conn = sqlite3.connect('raids.db')
    cursor = conn.cursor()
    # Pulls unique bosses that have active signups for the chosen day
    cursor.execute("SELECT DISTINCT training_name FROM signups WHERE signup_date = ?", (day,))
    bosses = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not bosses:
        return await interaction.followup.send(f"❌ No active signups found for `{day}` to build squads.", ephemeral=True)
        
    embed = discord.Embed(
        title=f"🛠️ Squad Orchestrator Dashboard: {day}",
        description="Select a target boss pool below to initialize the step-by-step checklist.",
        color=discord.Color.blurple()
    )
    
    # This calls the new SquadOrchestratorView which loads your 3-step checklist
    from views import SquadOrchestratorView
    view = SquadOrchestratorView(day=day, active_bosses=bosses)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="backup_db", description="Download the live database file for local testing")
@discord.app_commands.checks.has_permissions(administrator=True)
async def backup_db(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Grabs the live database file and attaches it as a private download
        with open('raids.db', 'rb') as f:
            discord_file = discord.File(f, filename='raids.db')
            await interaction.followup.send("📦 Here is your live testing database snapshot:", file=discord_file, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to extract database file: `{e}`", ephemeral=True)


bot.run(TOKEN)