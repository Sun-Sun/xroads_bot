# config.py
import discord
from discord import app_commands

# ==========================================
# GLOBAL PERMISSION CONFIGURATIONS
# ==========================================
STAFF_ROLES = ["Innkeeper", "Squadmaker"]
LEADERSHIP_ROLES = ["Squadmaker", "Commander", "Aide", "Innkeeper", "Bartender"]

def has_leadership_role():
    """
    Reusable decorator for app commands.
    Checks if a user has any allowed leadership roles or administrator privileges.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        user_role_names = [role.name for role in interaction.user.roles]
        
        if any(role in user_role_names for role in LEADERSHIP_ROLES) or interaction.user.guild_permissions.administrator:
            return True
            
        raise app_commands.AppCommandError("🔒 Access Denied: Missing leadership permissions.")
    return app_commands.check(predicate)