import discord

from database import get_user_profile, save_user_profile

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
            discord.SelectOption(label="Quickness Heal (Tank)", value="quickheal tank"),
            discord.SelectOption(label="Alacrity Heal (Tank)", value="alacheal tank"),
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
            self.int_menu = self.adv_menu = None

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