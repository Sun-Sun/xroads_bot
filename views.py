import discord
import sqlite3
from database import get_user_profile, save_user_profile, DB_PATH
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
        from database import save_signup, update_raid_embed
        await interaction.response.defer(ephemeral=True)

        if self.save_consent.value.upper() == "YES":
            save_user_profile(str(interaction.user.id), self.gw2_account.value)

        roles_str = ", ".join(self.selected_roles)
        safe_ping = interaction.user.mention if interaction.user.mention else f"<@{interaction.user.id}>"
        
        for boss in self.bosses:
            save_signup(
                username=interaction.user.name,
                discord_ping=safe_ping,
                gw2_acc=self.gw2_account.value,
                signup_date=self.training_date,
                training_name=boss,
                roles=roles_str
            )

        await update_raid_embed(interaction, self.training_date, message=self.message)
        await interaction.edit_original_response(content="✅ Signup Successful!", view=None)

# --- MODAL FOR RETURNING USERS (Comment Only) ---
class QuickSignupModal(discord.ui.Modal, title='Raid Training Signup'):
    comment = discord.ui.TextInput(
        label='Comments (Optional)', 
        style=discord.TextStyle.long, required=False,
        placeholder="e.g. Can do special roles"
    )

    def __init__(self, bosses, selected_roles, training_date, message, saved_acc):
        super().__init__(title=f"Raid Training Signup")
        self.bosses = bosses
        self.selected_roles = selected_roles
        self.training_date = training_date
        self.message = message
        self.saved_acc = saved_acc

    async def on_submit(self, interaction: discord.Interaction):
        from database import save_signup, update_raid_embed
        await interaction.response.defer(ephemeral=True)

        roles_str = ", ".join(self.selected_roles)
        safe_ping = interaction.user.mention if interaction.user.mention else f"<@{interaction.user.id}>"
        
        for boss in self.bosses:
            save_signup(
                username=interaction.user.name,
                discord_ping=safe_ping,
                gw2_acc=self.saved_acc,
                signup_date=self.training_date,
                training_name=boss,
                roles=roles_str
            )

        await update_raid_embed(interaction, self.training_date, message=self.message)
        await interaction.edit_original_response(content="✅ Signup Successful (Profile Used)!", view=None)


class RoleDropdown(discord.ui.Select):
    def __init__(self, selected_bosses, date, message):
        options = [
            discord.SelectOption(label="Heal Tank Quickness", value="qhealtank"),
            discord.SelectOption(label="Heal Tank Alacrity", value="ahealtank"),
            discord.SelectOption(label="Heal Quickness", value="qheal"),
            discord.SelectOption(label="Heal Alacrity", value="aheal"),
            discord.SelectOption(label="DPS Quickness", value="qdps"),
            discord.SelectOption(label="DPS Alacrity", value="adps"),
            discord.SelectOption(label="DPS", value="dps"),
        ]
        super().__init__(placeholder="Select your roles for these bosses...", min_values=1, max_values=len(options), options=options)
        self.selected_bosses = selected_bosses
        self.date = date
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        from database import get_user_profile
        saved_acc = get_user_profile(str(interaction.user.id))

        if saved_acc:
            await interaction.response.send_modal(
                QuickSignupModal(self.selected_bosses, self.values, self.date, self.message, saved_acc)
            )
        else:
            await interaction.response.send_modal(
                FullSignupModal(self.selected_bosses, self.values, self.date, self.message)
            )

class BossSelect(discord.ui.Select):
    def __init__(self, bosses, placeholder, emoji, tier_name):
        options = [discord.SelectOption(label=f"✨ Select All {tier_name}", value="all")]
        for b in bosses:
            options.append(discord.SelectOption(label=b["label"], value=b["value"], emoji=emoji, description=f"Tier: {tier_name}"))
        super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class PersistentSignupView(discord.ui.View):
    # Pass exactly the 2 arguments your button in main.py provides
    def __init__(self, date, message):
        super().__init__(timeout=None)
        self.date = date
        self.message = message
        
        self.beg_list = [
            {"label": "Vale Guardian (W1)", "value": "Vale Guardian"},
            {"label": "Gorseval (W1)", "value": "Gorsevaal"},
            {"label": "Bandit Trio (W2)", "value": "Bandit Trio"},
            {"label": "Escort (W3)", "value": "Escort"},
            {"label": "Twisted Castle (W3)", "value": "Twisted Castle"},
            {"label": "Cairn (W4)", "value": "Cairn"},
            {"label": "Mursaat Overseer (W4)", "value": "Mursaat Overseer"},
            {"label": "Samarog (W4)", "value": "Samarog"},
            {"label": "River and Statues (W5)", "value": "River and Statues"},
            {"label": "Aetherblade Hideout CM, Xunlai Jade Junkyard CM, Cosmic Observatory CM", "value": "Aetherblade Hideout CM, Xunlai Jade Junkyard CM, Cosmic Observatory CM"}
        ]
        
        self.int_list = [
            {"label": "Sabetha (W1)", "value": "Sabetha"},
            {"label": "Slothasor (W2)", "value": "Slothasor"},
            {"label": "Keep Construct (W3)", "value": "Keep Construct"},
            {"label": "Xera (W3)", "value": "Xera"},
            {"label": "Conjured Amalgamate (W6)", "value": "Conjured Amalgamate"},
            {"label": "Twin Largos (W6)", "value": "Twin Largos"},
            {"label": "Adina (W7)", "value": "Adina"},
            {"label": "Sabir (W7)", "value": "Sabir"},
            {"label": "Kela (W9)", "value": "Kela"},
            {"label": "Old Lions Court CM", "value": "Old Lions Court CM"}
        ]
        
        self.adv_list = [
            {"label": "Matthias (W2)", "value": "Matthias"},
            {"label": "Deimos (W4)", "value": "Deimos"},
            {"label": "Souless Horror (W5)", "value": "Souless Horror"},
            {"label": "Dhuum (W5)", "value": "Dhuum"},
            {"label": "Qadim (W6)", "value": "Qadim"},
            {"label": "Qadim the Peerless (W7)", "value": "Qadim the Peerless"},
            {"label": "Greer (W8)", "value": "Greer"},
            {"label": "Decima (W8)", "value": "Decima"},
            {"label": "Ura (W8)", "value": "Ura"},
            {"label": "Kaineng Overlook CM", "value": "Kaineng Overlook CM"}
        ]

        # 🟢 Always add the Beginner selection layout
        self.beg_menu = BossSelect(self.beg_list, "🟢 Beginner Bosses...", "🟢", "Beginner")
        self.add_item(self.beg_menu)
        
        # Statically prepare placeholders for downstream verification checks
        self.int_menu = None
        self.adv_menu = None

    # 🌟 FIXED: Evaluates roles on interaction submission cleanly right inside the view scope!
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        user_role_names = [role.name for role in interaction.user.roles]
        ADVANCED_ROLES = ["Regular", "Adventurer", "Legend", "Commander", "Aide", "Innkeeper", "Bartender", "Squadmaker"]
        is_regular = any(role in user_role_names for role in ADVANCED_ROLES)
        
        if not is_regular and "Rookie" in user_role_names:
            is_regular = False

        # If they are a Regular or above, lazily populate the other layout blocks seamlessly
        if is_regular and self.int_menu is None:
            self.int_menu = BossSelect(self.int_list, "🟡 Intermediate Bosses...", "🟡", "Intermediate")
            self.adv_menu = BossSelect(self.adv_list, "🔴 Advanced Bosses...", "🔴", "Advanced")
            self.add_item(self.int_menu)
            self.add_item(self.adv_menu)
            await interaction.message.edit(view=self)
        return True

    @discord.ui.button(label="Next: Select Roles ➡️", style=discord.ButtonStyle.blurple, row=3)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        final_bosses = []
        
        def process_menu(menu, full_list):
            if menu and menu.values:
                if "all" in menu.values:
                    final_bosses.extend([b["value"] for b in full_list])
                else:
                    final_bosses.extend(menu.values)

        process_menu(self.beg_menu, self.beg_list)
        if self.int_menu:
            process_menu(self.int_menu, self.int_list)
        if self.adv_menu:
            process_menu(self.adv_menu, self.adv_list)

        final_bosses = list(set(final_bosses))

        if not final_bosses:
            return await interaction.response.send_message("❌ Please select at least one boss!", ephemeral=True)

        view = discord.ui.View()
        view.add_item(RoleDropdown(final_bosses, self.date, self.message))
        await interaction.response.edit_message(content="**Step 2: Select your Roles**", view=view)


# ==========================================================
# SQUAD BUILDING STEPS
# ==========================================================

class SquadOrchestratorView(discord.ui.View):
    def __init__(self, day: str, active_bosses: list):
        super().__init__(timeout=None)
        self.day = day
        self.squad_count = 0
        self.assigned_leads = set()
        self.assigned_trainees = set()
        self.master_csv_rows = []
        self.active_bosses = active_bosses
        self.completed_cohorts = set()
        
        self.add_item(BossSquadSelector(active_bosses, orchestrator_view=self))
        self.add_item(MasterExportButton())


class BossSquadSelector(discord.ui.Select):
    def __init__(self, bosses_data: list, orchestrator_view=None):
        options = []
        for b in bosses_data:
            value_string = f"{b['boss_value']}|{b['squad_suffix']}"
            if orchestrator_view and value_string in orchestrator_view.completed_cohorts:
                continue
            options.append(discord.SelectOption(
                label=b["display_label"],
                value=value_string
            ))
            
        if not options:
            options = [discord.SelectOption(label="✅ All cohorts fully compiled!", value="done")]
            disabled_state = True
        else:
            disabled_state = False
            
        super().__init__(
            placeholder="🎯 Select a target training cohort...", 
            min_values=1, max_values=1, 
            options=options[:25],
            disabled=disabled_state
        )
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "done":
            await interaction.response.defer()
            return

        selected_raw = self.values[0]
        boss_name, squad_suffix = selected_raw.split("|")
        
        orchestrator_view = self.view
        if orchestrator_view is None:
            orchestrator_view = self
            
        if len(orchestrator_view.master_csv_rows) == 0:
            current_squad_num = 1
        else:
            last_recorded_squad = orchestrator_view.master_csv_rows[-1][4]
            current_squad_num = last_recorded_squad + 1
        
        squad_setup = {
            "boss": boss_name,
            "day": orchestrator_view.day,
            "squad_number": current_squad_num,
            "squad_instance_label": f"Squad {squad_suffix}",
            "cohort_key": selected_raw,
            "commanders": [],
            "aides": []
        }
        
        orchestrator_view.clear_items()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM leaders WHERE rank = 'Commander'")
        all_comms = [row[0] for row in cursor.fetchall()]
        avail = [c for c in all_comms if c.lower() not in orchestrator_view.assigned_leads]
        conn.close()
        
        if avail:
            orchestrator_view.add_item(ChecklistStaffSelect(squad_setup, orchestrator_view, avail, current_step=1))
        else:
            orchestrator_view.add_item(discord.ui.Select(
                placeholder="❌ No unique Commanders available", disabled=True,
                options=[discord.SelectOption(label="None available", value="none")]
            ))
            
        orchestrator_view.add_item(MasterExportButton())
            
        boss_clean = "QTP" if squad_setup["boss"] == "Qadim the Peerless" else squad_setup["boss"]
        embed = discord.Embed(
            title=f"📋 Squad Builder Checklist ({squad_setup['squad_instance_label']})",
            description=f"**Target Boss Run:** {boss_clean}\n**Date:** {squad_setup['day']}\n\n"
                        f"👉 **Step 1: Select Commander(s)**\n└ *Assigned:* *None selected yet*\n\n"
                        f"⏳ **Step 2: Select Aide(s)**\n\n⏳ **Step 3: Randomly Populate Trainee Roster Lineups**",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=orchestrator_view)


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
        
        if self.step == 1:
            if chosen_name not in self.setup["commanders"]:
                self.setup["commanders"].append(chosen_name)
                self.orchestrator.assigned_leads.add(chosen_name.lower())
        else:
            if chosen_name not in self.setup["aides"]:
                self.setup["aides"].append(chosen_name)
                self.orchestrator.assigned_leads.add(chosen_name.lower())

        self.orchestrator.clear_items()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if self.step == 1:
            cursor.execute("SELECT username FROM leaders WHERE rank = 'Commander'")
            avail = [row[0] for row in cursor.fetchall() if row[0].lower() not in self.orchestrator.assigned_leads]
            if avail:
                self.orchestrator.add_item(ChecklistStaffSelect(self.setup, self.orchestrator, avail, current_step=1))
            else:
                self.orchestrator.add_item(discord.ui.Select(placeholder="❌ No unique Commanders available", disabled=True, options=[discord.SelectOption(label="None", value="n")]))
            
            if self.setup["commanders"]:
                self.orchestrator.add_item(NextStepButton(self.setup, self.orchestrator, next_step=2, label="Next: Select Aides ➔"))
        else:
            cursor.execute("SELECT username FROM leaders WHERE rank = 'Aide'")
            avail = [row[0] for row in cursor.fetchall() if row[0].lower() not in self.orchestrator.assigned_leads]
            if avail:
                self.orchestrator.add_item(ChecklistStaffSelect(self.setup, self.orchestrator, avail, current_step=2))
            else:
                self.orchestrator.add_item(discord.ui.Select(placeholder="❌ No unique Aides available", disabled=True, options=[discord.SelectOption(label="None", value="n")]))
                
            self.orchestrator.add_item(NextStepButton(self.setup, self.orchestrator, next_step=3, label="Next: Populate Trainees ➔", style=discord.ButtonStyle.success))
            
        conn.close()
        self.orchestrator.add_item(MasterExportButton())
        
        boss_clean = "QTP" if self.setup["boss"] == "Qadim the Peerless" else self.setup["boss"]
        embed = discord.Embed(
            title=f"📋 Squad Builder Checklist ({self.setup.get('squad_instance_label', 'Squad 1')})",
            description=f"**Target Boss Run:** {boss_clean}\n**Date:** {self.setup['day']}\n\n"
                        f"{'✅' if self.step > 1 else '👉'} **Step 1: Select Commander(s)**\n"
                        f"└ *Assigned:* {', '.join(self.setup['commanders']) if self.setup['commanders'] else '*None selected yet*'}\n\n"
                        f"{'👉' if self.step == 2 else '⏳'} **Step 2: Select Aide(s)**\n"
                        f"└ *Assigned:* {', '.join(self.setup['aides']) if self.setup['aides'] else '*None selected yet*'}\n\n"
                        f"⏳ **Step 3: Randomly Populate Trainee Roster Lineups**",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=self.orchestrator)


class NextStepButton(discord.ui.Button):
    def __init__(self, setup, orchestrator, next_step, label, style=discord.ButtonStyle.primary):
        super().__init__(label=label, style=style)
        self.setup = setup
        self.orchestrator = orchestrator
        self.next_step = next_step

    async def callback(self, interaction: discord.Interaction):
        if self.next_step == 2:
            self.orchestrator.clear_items()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM leaders WHERE rank = 'Aide'")
            all_aides = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            avail = [a for a in all_aides if a.lower() not in self.orchestrator.assigned_leads]
            if avail:
                self.orchestrator.add_item(ChecklistStaffSelect(self.setup, self.orchestrator, avail, current_step=2))
            else:
                self.orchestrator.add_item(discord.ui.Select(
                    placeholder="❌ No unique Aides available", disabled=True,
                    options=[discord.SelectOption(label="None available", value="none")]
                ))
                
            self.orchestrator.add_item(NextStepButton(self.setup, self.orchestrator, next_step=3, label="Next: Populate Trainees ➔", style=discord.ButtonStyle.success))
            self.orchestrator.add_item(MasterExportButton())
            
            boss_clean = "QTP" if self.setup["boss"] == "Qadim the Peerless" else self.setup["boss"]
            embed = discord.Embed(
                title=f"📋 Squad Builder Checklist ({self.setup.get('squad_instance_label', 'Squad 1')})",
                description=f"**Target Boss Run:** {boss_clean}\n**Date:** {self.setup['day']}\n\n"
                            f"✅ **Step 1: Select Commander(s)**\n"
                            f"└ *Assigned:* {', '.join(self.setup['commanders'])}\n\n"
                            f"👉 **Step 2: Select Aide(s)**\n"
                            f"└ *Assigned:* *None selected yet*\n\n"
                            f"⏳ **Step 3: Randomly Populate Trainee Roster Lineups**",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=self.orchestrator)
            
        elif self.next_step == 3:
            await interaction.response.defer(ephemeral=True)
            await generate_final_checklist_squad(interaction, self.setup, self.orchestrator)


class MasterExportButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔴 Finish & Export Master CSV", style=discord.ButtonStyle.danger, row=4)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.view.master_csv_rows:
            await interaction.followup.send("⚠️ Master output cache is completely empty! Build at least one squad target first.", ephemeral=True)
            return

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Rank / Role Type", "Character Name", "Discord Tag / Ping", "Date", "Squad Number", "Boss", "Assigned Role", "Group Tier", "Eligible Bosses", "Roles Selection Profile"])
        writer.writerows(self.view.master_csv_rows)
        output.seek(0)
        
        discord_file = discord.File(fp=io.BytesIO(output.getvalue().encode('utf-8')), filename=f"master_squads_{self.view.day}.csv")
        await interaction.followup.send(content=f"🚀 **All Squads Compiled Successfully!** Attached is your master sheet format file:", file=discord_file, ephemeral=True)


# --- MATRICES COMBINATORIAL ALGORITHM ---
async def generate_final_checklist_squad(interaction: discord.Interaction, setup: dict, orchestrator):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    boss_name = setup["boss"]
    
    cursor.execute("SELECT username, discord_ping, gw2_acc, roles FROM signups WHERE signup_date = ? AND training_name = ?", (setup["day"], boss_name))
    trainees_raw = cursor.fetchall()
    
    lower_leads = set(x.lower() for x in setup["commanders"] + setup["aides"])
    leader_pool = []
    for name in setup["commanders"]:
        cursor.execute("SELECT roles FROM leaders WHERE username = ?", (name,))
        res = cursor.fetchone()
        roles = [r.strip().lower() for r in res[0].split(',') if r.strip()] if res else ["dps"]
        leader_pool.append({"name": name, "roles": roles, "type": "Commander", "assigned_role": "DPS"})
    for name in setup["aides"]:
        cursor.execute("SELECT roles FROM leaders WHERE username = ?", (name,))
        res = cursor.fetchone()
        roles = [r.strip().lower() for r in res[0].split(',') if r.strip()] if res else ["dps"]
        leader_pool.append({"name": name, "roles": roles, "type": "Aide", "assigned_role": "DPS"})
        
    trainee_pool = []
    for t_name, t_ping, t_acc, t_roles in trainees_raw:
        if t_name.lower() not in lower_leads and t_name.lower() not in orchestrator.assigned_trainees:
            unique_boss_names = list(set(b["boss_value"] for b in orchestrator.active_bosses))
            if not unique_boss_names:
                unique_boss_names = [boss_name]
                
            placeholders = ", ".join(["?"] * len(unique_boss_names))
            query = f"SELECT COUNT(*) FROM signups WHERE signup_date = ? AND username = ? AND training_name IN ({placeholders})"
            query_params = [setup["day"], t_name] + unique_boss_names
            
            cursor.execute(query, query_params)
            session_boss_count = cursor.fetchone()[0]
            
            parsed_roles = [r.strip().lower() for r in t_roles.split(',') if r.strip()]
            if any(role in parsed_roles for role in ["qheal", "aheal", "quickheal", "alacheal", "qhealtank", "ahealtank"]):
                role_weight = 0
            elif any(role in parsed_roles for role in ["qdps", "adps", "quickdps", "alacdps"]):
                role_weight = 1
            else:
                role_weight = 2
                
            trainee_pool.append({
                "name": t_name, "ping": t_ping, "acc": t_acc, "roles": parsed_roles,
                "roles_raw_str": t_roles, "boss_count": session_boss_count, "role_weight": role_weight
            })
            
    trainee_pool.sort(key=lambda x: (x["boss_count"], x["role_weight"]))
    
    needed_trainees = 10 - len(leader_pool)
    active_trainees = trainee_pool[:min(len(trainee_pool), needed_trainees)]
    
    subgroup_boons = []
    assigned_names = set()
    
    boon_targets = [
        {"type": "qheal", "roles": ["qheal", "quickheal", "qhealtank", "quickhealtank"]},
        {"type": "aheal", "roles": ["aheal", "alacheal", "ahealtank", "alachealtank"]},
        {"type": "qdps", "roles": ["qdps", "quickdps"]},
        {"type": "adps", "roles": ["adps", "alacdps"]}
    ]
    
    import random
    random.shuffle(boon_targets)
    
    for target in boon_targets:
        found = False
        for trainee in active_trainees:
            if trainee["name"] not in assigned_names and any(r in trainee["roles"] for r in target["roles"]):
                if "tank" in "".join(trainee["roles"]):
                    trainee["assigned_role"] = "Heal Tank Quickness" if target["type"] == "qheal" else "Heal Tank Alacrity"
                else:
                    trainee["assigned_role"] = "Heal Quickness" if target["type"] == "qheal" else "Heal Alacrity" if target["type"] == "aheal" else "DPS Quickness" if target["type"] == "qdps" else "DPS Alacrity"
                subgroup_boons.append(target["type"])
                assigned_names.add(trainee["name"])
                found = True
                break
        if not found:
            for leader in leader_pool:
                if leader["name"] not in assigned_names and any(r in leader["roles"] for r in target["roles"]):
                    leader["assigned_role"] = "Heal Quickness" if target["type"] == "qheal" else "Heal Alacrity" if target["type"] == "aheal" else "DPS Quickness" if target["type"] == "qdps" else "DPS Alacrity"
                    subgroup_boons.append(target["type"])
                    assigned_names.add(leader["name"])
                    break
                    
    for trainee in active_trainees:
        if trainee["name"] not in assigned_names:
            trainee["assigned_role"] = "DPS"
        orchestrator.assigned_trainees.add(trainee["name"].lower())
        
    for leader in leader_pool:
        if leader["name"] not in assigned_names:
            leader["assigned_role"] = "DPS"
            
    cursor.execute("SELECT COUNT(DISTINCT username) FROM signups WHERE signup_date = ?", (setup["day"],))
    res_count = cursor.fetchone()
    total_unique_trainees = res_count[0] if res_count else 0
    remaining_trainees_count = max(0, total_unique_trainees - len(orchestrator.assigned_trainees))
    
    conn.close()
    
    if "cohort_key" in setup:
        orchestrator.completed_cohorts.add(setup["cohort_key"])

    orchestrator.clear_items()
    orchestrator.add_item(BossSquadSelector(orchestrator.active_bosses, orchestrator_view=orchestrator))
    orchestrator.add_item(MasterExportButton())
    
    base_label = "QTP" if setup["boss"] == "Qadim the Peerless" else setup["boss"]
    boss_label = f"{base_label} {setup.get('squad_instance_label', 'Squad 1')}"
    
    from datetime import datetime
    try:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                clean_date = datetime.strptime(setup["day"].strip(), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        else:
            clean_date = setup["day"]
    except Exception:
        clean_date = setup["day"]

    for leader in leader_pool:
        final_role = leader.get("assigned_role", "DPS")
        orchestrator.master_csv_rows.append([
            leader["type"], leader["name"], f"@{leader['name']}", 
            clean_date, setup["squad_number"], boss_label, final_role, "-", "all", "all"
        ])
        
    for trainee in active_trainees:
        final_role = trainee.get("assigned_role", "DPS")
        orchestrator.master_csv_rows.append([
            trainee["acc"] if trainee["acc"] else trainee["name"], trainee["name"], trainee["ping"], 
            clean_date, setup["squad_number"], boss_label, final_role, "3", boss_label, trainee["roles_raw_str"]
        ])
        
    warning_text = ""
    total_squad_count = len(leader_pool) + len(active_trainees)
    if total_squad_count < 10:
        warning_text = f"\n⚠️ *Note: This squad was parsed as a partial run due to roster limits ({total_squad_count}/10 slots filled).* "

    return_embed = discord.Embed(
        title="📊 Raid Night Master Dashboard",
        description=f"✅ **{boss_label} compiled and cached successfully!**{warning_text}\n\n"
                    f"**Date Context:** `{setup['day']}`\n"
                    f"**Remaining Unassigned Trainees:** `{remaining_trainees_count}`\n"
                    f"**Current master file lines:** {len(orchestrator.master_csv_rows)} tracking rows cached.\n\n"
                    "Select your next target training cohort block below to continue building, or click the red export button to finish.",
        color=discord.Color.dark_purple()
    )
    return_embed.set_footer(text="Xroads Raid Orchestration Engine")
    
    await interaction.edit_original_response(embed=return_embed, view=orchestrator)