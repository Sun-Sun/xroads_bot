# ui_helpers.py
import discord
from database import wipe_date, create_embed

class DeleteConfirmationView(discord.ui.View):
    def __init__(self, training_date, original_message):
        super().__init__(timeout=60)
        self.training_date = training_date
        self.original_message = original_message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        from config import STAFF_ROLES
        if not any(role.name in STAFF_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ Access Denied: Staff only.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm Delete & Wipe", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        wipe_date(self.training_date)
        await self.original_message.delete()
        await interaction.response.edit_message(content=f"🗑️ Session for {self.training_date} has been fully removed.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Cancelled. No changes made.", view=None)


class MondayCorrectionView(discord.ui.View):
    def __init__(self, suggested_monday, original_interaction):
        super().__init__(timeout=60)
        self.suggested_monday = suggested_monday
        self.original_interaction = original_interaction

    @discord.ui.button(label="Yes, use this Monday", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        from main import run_weekly_setup
        await interaction.response.defer(ephemeral=True)
        await run_weekly_setup(interaction, self.suggested_monday)
        await interaction.edit_original_response(content=f"✅ Setup complete for week of {self.suggested_monday}.", view=None)

    @discord.ui.button(label="No, cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Setup cancelled. Please provide a valid Monday.", view=None)