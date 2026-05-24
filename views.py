import discord
import sqlite3
from database import get_user_profile, save_user_profile
import csv
import io

# --- MODAL FOR NEW USERS (Includes Account & Consent) ---
class FullSignupModal(discord.ui.Modal, title='Raid Training: New Profile'):
    gw2_account = discord.ui.TextInput(
        label='GW2 Account Name', 
        placeholder='Name.1234',
        min_length=3, max_length=35
    )
    save_consent = discord.ui.TextInput(
        label='Save account for future signups?',
        placeholder='Type "YES" to save to your profile',
        required=False, max_length=3
    )
    comment = discord.ui.TextInput(
        label='Comments (Optional)', 
        style=discord.TextStyle.long, required=False,
        placeholder="e.g. Can do special roles"
    )

    def __init__(self, bosses, selected_roles, training_date, message):
        super().__init__()
        self.bosses = bosses
        self.selected_roles = selected_roles
        self.training_date = training_date
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        from database import save_signup, update_raid_embed, save_user_profile
        await interaction.response.defer(ephemeral=True)

        if self.save_consent.value.upper() == "YES":
            save_user_profile(str(interaction.user.id), self.gw2_account.value)

        roles_str = ", ".join(self.selected_roles)
        for boss in self.bosses:
            save_signup(str(interaction.user.id), interaction.user.display_name, interaction.user.mention, 
                        self.gw2_account.value, boss, roles_str, self.comment.value, self.training_date)

        await update_raid_embed(interaction, self.training_date, message=self.message)
        await interaction.edit_original_response(content="✅ Signup Successful!", view=None)

# --- MODAL FOR RETURNING USERS (Comment Only) ---
class QuickSignupModal(discord.ui.Modal, title='Raid Training Signup'):
    
    textd = discord.ui.TextDisplay(
        content=""
    )
    comment = discord.ui.TextInput(
        label='Comments (Optional)', 
        style=discord.TextStyle.long, required=False,
        placeholder="e.g. Can do special roles"
    )

    def __init__(self, bosses, selected_roles, training_date, message, saved_acc):
        super().__init__(title=f"Raid Training Signup - {saved_acc}")
        self.bosses = bosses
        self.selected_roles = selected_roles
        self.training_date = training_date
        self.message = message
        self.saved_acc = saved_acc

        self.textd.content = f"Welcome back! Your saved account `{saved_acc}` will be used for this signup. You can update your profile anytime with `/profile_set`."

    async def on_submit(self, interaction: discord.Interaction):
        from database import save_signup, update_raid_embed
        await interaction.response.defer(ephemeral=True)

        roles_str = ", ".join(self.selected_roles)
        for boss in self.bosses:
            save_signup(str(interaction.user.id), interaction.user.display_name, interaction.user.mention, 
                        self.saved_acc, boss, roles_str, self.comment.value, self.training_date)

        await update_raid_embed(interaction, self.training_date, message=self.message)
        await interaction.edit_original_response(content="✅ Signup Successful (Profile Used)!", view=None)


class RoleDropdown(discord.ui.Select):
    def __init__(self, selected_bosses, date, message):
        options = [
            discord.SelectOption(label="DPS", value="dps"),
            discord.SelectOption(label="Quickness Heal", value="quickheal"),
            discord.SelectOption(label="Alacrity Heal", value="alacheal"),
            discord.SelectOption(label="Quickness DPS", value="quickdps"),
            discord.SelectOption(label="Alacrity DPS", value="alacdps"),
            discord.SelectOption(label="Quickness Heal (Tank)", value="quickhealtank"),
            discord.SelectOption(label="Alacrity Heal (Tank)", value="alachealtank"),
        ]
        super().__init__(placeholder="Select your roles for these bosses...", min_values=1, max_values=len(options), options=options)
        self.selected_bosses = selected_bosses
        self.date = date
        self.message = message

    # Inside class RoleDropdown(discord.ui.Select) in views.py

    async def callback(self, interaction: discord.Interaction):
        from database import get_user_profile
        
        # Check if user has a saved account
        saved_acc = get_user_profile(str(interaction.user.id))

        if saved_acc:
            # Show the quick version (only comments)
            await interaction.response.send_modal(
                QuickSignupModal(self.selected_bosses, self.values, self.date, self.message, saved_acc)
            )
        else:
            # Show the full version (account + consent)
            await interaction.response.send_modal(
                FullSignupModal(self.selected_bosses, self.values, self.date, self.message)
            )

class BossSelect(discord.ui.Select):
    def __init__(self, bosses, placeholder, emoji, tier_name):
        options = [discord.SelectOption(label=f"✨ Select All {tier_name}", value="all")]
        for b in bosses:
            options.append(discord.SelectOption(label=b, value=b, emoji=emoji, description=f"Tier: {tier_name}"))
        
        super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class UnifiedBossView(discord.ui.View):
    def __init__(self, is_regular, date, message):
        super().__init__(timeout=None)
        self.date = date
        self.message = message
        
        # Boss Lists
        self.beg_list = ["Vale Guardian", "Gorsevaal", "Bandit Trio", "Escort", "Twisted Castle", "Cairn", "Mursaat Overseer", "Samarog", "River and Statues", "Aetherblade Hideout CM, Xunlai Jade Junkyard CM, Cosmic Observatory CM"]
        self.int_list = ["Sabetha", "Slothasor", "Keep Construct", "Xera", "Conjured Amalgamate", "Twin Largos", "Adina", "Sabir", "Kela", "Old Lions Court CM"]
        self.adv_list = ["Matthias", "Deimos", "Souless Horror",  "Dhuum", "Qadim", "Qadim the Peerless", "Greer", "Decima", "Ura", "Kaineng Overlook CM"]

        # 🟢 Beginner Menu
        self.beg_menu = BossSelect(self.beg_list, "🟢 Beginner Bosses...", "🟢", "Beginner")
        self.add_item(self.beg_menu)

        # 🟡 & 🔴 Menus (Role Gated)
        if is_regular:
            self.int_menu = BossSelect(self.int_list, "🟡 Intermediate Bosses...", "🟡", "Intermediate")
            self.adv_menu = BossSelect(self.adv_list, "🔴 Advanced Bosses...", "🔴", "Advanced")
            self.add_item(self.int_menu)
            self.add_item(self.adv_menu)
        else:
            self.int_menu = None
            self.adv_menu = None

    @discord.ui.button(label="Next: Select Roles ➡️", style=discord.ButtonStyle.blurple, row=3)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        final_bosses = []
        
        # Helper to collect values correctly
        def process_menu(menu, full_list):
            if menu and menu.values:
                # If "all" was selected at any point, use the full list for that tier
                if "all" in menu.values:
                    final_bosses.extend(full_list)
                else:
                    # Otherwise, just add the specific bosses they clicked
                    final_bosses.extend(menu.values)

        # Process each of your 3 menus
        process_menu(self.beg_menu, self.beg_list)
        if self.int_menu:
            process_menu(self.int_menu, self.int_list)
        if self.adv_menu:
            process_menu(self.adv_menu, self.adv_list)

        # Remove potential duplicates (if a boss is accidentally in two lists)
        final_bosses = list(set(final_bosses))

        if not final_bosses:
            return await interaction.response.send_message("❌ Please select at least one boss!", ephemeral=True)

        # Move to Role Selection
        from views import RoleDropdown
        view = discord.ui.View()
        view.add_item(RoleDropdown(final_bosses, self.date, self.message))
        
        await interaction.response.edit_message(content="**Step 2: Select your Roles**", view=view)

# ==========================================================
# SQUID BUILDING STEPS
# ==========================================================

class SquadOrchestratorView(discord.ui.View):
    def __init__(self, day: str, active_bosses: list):
        super().__init__(timeout=None)
        self.day = day
        self.squad_count = 0
        self.assigned_leads = set()      # Tracks used staff
        self.assigned_trainees = set()   # Tracks used trainees
        self.master_csv_rows = []        # 🌟 NEW: Holds all squad data rows until the end
        
        # Base Selection Dropdown
        self.add_item(BossSquadSelector(active_bosses))
        # 🌟 NEW: Finalize Button added to the bottom of the dashboard view
        self.add_item(MasterExportButton())


class BossSquadSelector(discord.ui.Select):
    def __init__(self, bosses):
        options = [discord.SelectOption(label="QTP" if b == "Qadim the Peerless" else b, value=b) for b in bosses]
        super().__init__(placeholder="🎯 Select a target boss pool...", min_values=1, max_values=1, options=options)
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_boss = self.values[0]
        
        self.view.squad_count += 1
        squad_setup = {
            "boss": selected_boss,
            "day": self.view.day,
            "squad_number": self.view.squad_count,
            "commanders": [],
            "aides": []
        }
        
        await send_checklist_step(interaction, squad_setup, self.view, step=1)


async def send_checklist_step(interaction: discord.Interaction, squad_setup: dict, orchestrator, step: int):
    boss_clean = "QTP" if squad_setup["boss"] == "Qadim the Peerless" else squad_setup["boss"]
    
    embed = discord.Embed(
        title=f"📋 Squad Builder Checklist (Group #{squad_setup['squad_number']})",
        description=f"**Target Boss Run:** {boss_clean}\n**Date:** {squad_setup['day']}\n\n"
                    f"{'✅' if step > 1 else '👉'} **Step 1: Select Commander(s)**\n"
                    f"└ *Assigned:* {', '.join(squad_setup['commanders']) if squad_setup['commanders'] else '*None selected yet*'}\n\n"
                    f"{'✅' if step > 2 else ('👉' if step == 2 else '⏳')} **Step 2: Select Aide(s)**\n"
                    f"└ *Assigned:* {', '.join(squad_setup['aides']) if squad_setup['aides'] else '*None selected yet*'}\n\n"
                    f"{'⏳' if step < 3 else '🚀'} **Step 3: Randomly Populate Trainee Roster Lineups**",
        color=discord.Color.blue()
    )
    
    view = discord.ui.View()
    conn = sqlite3.connect('raids.db')
    cursor = conn.cursor()
    
    if step == 1:
        cursor.execute("SELECT username FROM leaders WHERE rank = 'Commander'")
        all_comms = [row[0] for row in cursor.fetchall()]
        avail = [c for c in all_comms if c.lower() not in orchestrator.assigned_leads]
        view.add_item(ChecklistStaffSelect(squad_setup, orchestrator, avail if avail else all_comms[:25], current_step=1))
        if squad_setup["commanders"]:
            view.add_item(NextStepButton(squad_setup, orchestrator, next_step=2, label="Next: Select Aides ➔"))
            
    elif step == 2:
        cursor.execute("SELECT username FROM leaders WHERE rank = 'Aide'")
        all_aides = [row[0] for row in cursor.fetchall()]
        avail = [a for a in all_aides if a.lower() not in orchestrator.assigned_leads]
        view.add_item(ChecklistStaffSelect(squad_setup, orchestrator, avail if avail else all_aides[:25], current_step=2))
        view.add_item(NextStepButton(squad_setup, orchestrator, next_step=3, label="Next: Populate Trainees ➔", style=discord.ButtonStyle.success))
        
    conn.close()
    
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class ChecklistStaffSelect(discord.ui.Select):
    def __init__(self, setup, orchestrator, staff_list, current_step):
        self.setup = setup
        self.orchestrator = orchestrator
        self.step = current_step
        placeholder = "👑 Choose Commander(s)..." if current_step == 1 else "🛡️ Choose Aide(s)..."
        options = [discord.SelectOption(label=name, value=name) for name in staff_list[:25]]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen_name = self.values[0]
        self.orchestrator.assigned_leads.add(chosen_name.lower())
        
        if self.step == 1:
            self.setup["commanders"].append(chosen_name)
        else:
            self.setup["aides"].append(chosen_name)
            
        await send_checklist_step(interaction, self.setup, self.orchestrator, step=self.step)


class NextStepButton(discord.ui.Button):
    def __init__(self, setup, orchestrator, next_step, label, style=discord.ButtonStyle.secondary):
        self.setup = setup
        self.orchestrator = orchestrator
        self.next_step = next_step
        super().__init__(label=label, style=style)

    async def callback(self, interaction: discord.Interaction):
        if self.next_step == 3:
            await generate_final_checklist_squad(interaction, self.setup, self.orchestrator)
        else:
            await send_checklist_step(interaction, self.setup, self.orchestrator, step=self.next_step)


class MasterExportButton(discord.ui.Button):
    """🌟 NEW: The button that compiles all cached squads into one file."""
    def __init__(self):
        super().__init__(label="🔴 Finish & Export Master CSV", style=discord.ButtonStyle.danger, row=1)

    async def callback(self, interaction: discord.Interaction):
        if not self.view.master_csv_rows:
            return await interaction.response.send_message("❌ You haven't generated any squads to export yet!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write Header row once at the very top of the single file
        writer.writerow(["Player name", "Discord name", "Discord Ping", "Day", "Squad", "Squad Type", "Assigned Role", "Tier", "Signups", "Roles"])
        # Dump all compiled squad records down the list
        writer.writerows(self.view.master_csv_rows)
        
        output.seek(0)
        file_data = discord.File(fp=io.BytesIO(output.getvalue().encode()), filename=f"master_squads_{self.view.day}.csv")
        
        await interaction.followup.send(content=f"🚀 **All Squads Compiled Successfully!** Attached is your master sheet format file:", file=file_data, ephemeral=True)


async def generate_final_checklist_squad(interaction: discord.Interaction, setup: dict, orchestrator):
    """Processes Step 3, handles priority algorithms, and bundles the data rows into the Master Cache."""
    await interaction.response.defer(ephemeral=True)
    
    conn = sqlite3.connect('raids.db')
    cursor = conn.cursor()
    
    leader_pool = []
    all_leads = setup["commanders"] + setup["aides"]
    
    for name in setup["commanders"]:
        cursor.execute("SELECT roles FROM leaders WHERE username = ?", (name,))
        res = cursor.fetchone()
        roles = [r.strip().lower() for r in res[0].split(',') if r.strip()] if res else ["dps"]
        leader_pool.append({"name": name, "roles": roles, "type": "Commander", "assigned_role": "Flex Support Lead"})
        
    for name in setup["aides"]:
        cursor.execute("SELECT roles FROM leaders WHERE username = ?", (name,))
        res = cursor.fetchone()
        roles = [r.strip().lower() for r in res[0].split(',') if r.strip()] if res else ["dps"]
        leader_pool.append({"name": name, "roles": roles, "type": "Aide", "assigned_role": "Flex Support Lead"})

    cursor.execute("SELECT username, discord_ping, gw2_acc, roles FROM signups WHERE signup_date = ? AND training_name = ?", 
                   (setup["day"], setup["boss"]))
    trainees_raw = cursor.fetchall()
    
    trainee_pool = []
    lower_leads = [n.lower() for n in all_leads]
    placeholders = ', '.join('?' for _ in orchestrator.active_bosses)
    
    for t_name, t_ping, t_acc, t_roles in trainees_raw:
        if t_name.lower() not in lower_leads and t_name.lower() not in orchestrator.assigned_trainees:
            query = f"SELECT COUNT(*) FROM signups WHERE signup_date = ? AND username = ? AND training_name IN ({placeholders})"
            query_params = [setup["day"], t_name] + list(orchestrator.active_bosses)
            cursor.execute(query, query_params)
            session_boss_count = cursor.fetchone()[0]
            
            parsed_roles = [r.strip().lower() for r in t_roles.split(',') if r.strip()]
            
            if any(role in parsed_roles for role in ["qheal", "aheal", "quickheal", "alacheal"]):
                role_weight = 0
            elif any(role in parsed_roles for role in ["qdps", "adps", "quickdps", "alacdps"]):
                role_weight = 1
            else:
                role_weight = 2
            
            trainee_pool.append({
                "name": t_name, "ping": t_ping, "acc": t_acc, "roles": parsed_roles,
                "roles_raw_str": t_roles, "boss_count": session_boss_count, "role_weight": role_weight
            })
            
    conn.close()

    import random
    random.shuffle(trainee_pool)
    trainee_pool.sort(key=lambda x: (x["boss_count"], x["role_weight"]))
    
    max_trainee_slots = max(0, 10 - len(leader_pool))
    active_trainees = trainee_pool[:max_trainee_slots]
    
    for trainee in active_trainees:
        orchestrator.assigned_trainees.add(trainee["name"].lower())
        
    squad_processing_pool = leader_pool + active_trainees
    q_heals = [p for p in squad_processing_pool if any(r in p["roles"] for r in ["qheal", "quickheal"])]
    a_heals = [p for p in squad_processing_pool if any(r in p["roles"] for r in ["aheal", "alacheal"])]
    q_dps   = [p for p in squad_processing_pool if any(r in p["roles"] for r in ["qdps", "quickdps"])]
    a_dps   = [p for p in squad_processing_pool if any(r in p["roles"] for r in ["adps", "alacdps"])]
    
    boon_match = False
    b1, b2 = None, None
    
    for qh in q_heals:
        for ad in a_dps:
            if qh["name"] != ad["name"]:
                b1, b2 = (qh, "Heal Quickness"), (ad, "DPS Alacrity")
                boon_match = True
                break
        if boon_match: break
        
    if not boon_match:
        for ah in a_heals:
            for qd in q_dps:
                if ah["name"] != qd["name"]:
                    b1, b2 = (ah, "Heal Alacrity"), (qd, "DPS Quickness")
                    boon_match = True
                    break
            if boon_match: break

    assigned_names = set()
    if boon_match:
        b1[0]["assigned_role"] = b1[1]
        b2[0]["assigned_role"] = b2[1]
        assigned_names.update([b1[0]["name"], b2[0]["name"]])

    # 🌟 DATA REDIRECTION: Instead of writing a file right now, cache the clean row arrays
    boss_label = "QTP" if setup["boss"] == "Qadim the Peerless" else setup["boss"]
    
    # Cache Staff Rows
    for leader in leader_pool:
        final_role = leader.get("assigned_role") if leader["name"] in assigned_names else "DPS"
        orchestrator.master_csv_rows.append([
            leader["name"], leader["name"], f"@{leader['name']}", 
            setup["day"], setup["squad_number"], boss_label, final_role, "-", "all", "all"
        ])
        
    # Cache Trainee Rows
    for trainee in active_trainees:
        final_role = trainee.get("assigned_role") if trainee["name"] in assigned_names else "DPS"
        orchestrator.master_csv_rows.append([
            trainee["acc"] if trainee["acc"] else trainee["name"], trainee["name"], trainee["ping"], 
            setup["day"], setup["squad_number"], boss_label, final_role, "3", boss_label, trainee["roles_raw_str"]
        ])

    # Let the squadmaker know this sub-squad step cleared cleanly
    await interaction.edit_original_response(
        content=f"✅ **Squad #{setup['squad_number']} ({boss_label}) compiled and cached!**\n"
                f"Select another target boss from the dashboard menu above to keep building, or click the red export button below to grab your master file.",
        embed=None, view=None
    )

# pools = {
#             "Beginner": [
#                 {"label": "Vale Guardian (W1)", "value": "VG"},
#                 {"label": "Gorseval (W1)", "value": "Gorse"},
#                 {"label": "Bandit Trio (W2)", "value": "Trio"},
#                 {"label": "Escort (W3)", "value": "Escort"},
#                 {"label": "Twisted Castle (W3)", "value": "TC"},
#                 {"label": "Cairn (W4)", "value": "Cairn"},
#                 {"label": "Mursaat Overseer (W4)", "value": "MO"},
#                 {"label": "Samarog (W4)", "value": "Sama"},
#                 {"label": "River & Statues (W5)", "value": "R&S"},
#             ],
#             "Intermediate": [
#                 {"label": "Slothasor (W2)", "value": "Sloth"},
#                 {"label": "Matthias (W2)", "value": "Matt"},
#                 {"label": "Keep Construct (W3)", "value": "KC"},
#                 {"label": "Xera (W3)", "value": "Xera"},
#                 {"label": "Sabetha (W1)", "value": "Sab"},
#                 {"label": "Conjured Amalgamate (W6)", "value": "CA"},
#                 {"label": "Largos (W6)", "value": "Largos"},
#                 {"label": "Adina (W7)", "value": "Adina"},
#                 {"label": "Sabir (W7)", "value": "Sabir"},
#                 {"label": "Greer (W8)", "value": "Greer"},
#                 {"label": "Decima (W8)", "value": "Decima"},
#                 {"label": "Ura (W8)", "value": "Ura"},
#                 {"label": "Kela (W9)", "value": "Kela"},
#             ],
#             "Advanced": [
#                 {"label": "Deimos (W4)", "value": "Deimos"},
#                 {"label": "Souless Horror (W5)", "value": "SH"},
#                 {"label": "Dhuum (W5)", "value": "Dhuum"},
#                 {"label": "Qadim (W6)", "value": "Qadim"},
#                 {"label": "Qadim the Peerless (W7)", "value": "QTP"},
#             ]