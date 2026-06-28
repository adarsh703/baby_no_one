import json
import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update load_data return dict to include "server_configs": {}
content = content.replace(
    '"vc_milestones_reached": {}',
    '"vc_milestones_reached": {},\n        "server_configs": {}'
)

# 2. Add global server_configs assignment after load_data()
content = content.replace(
    'invite_map = data.get("invite_map", {})  # invited_user_id (str) -> inviter_id',
    'invite_map = data.get("invite_map", {})  # invited_user_id (str) -> inviter_id\nserver_configs = data.get("server_configs", {})'
)

# 3. Update save_data dict to include "server_configs": server_configs
content = content.replace(
    '"invite_map": invite_map\n            }, f, indent=2)',
    '"invite_map": invite_map,\n                "server_configs": server_configs\n            }, f, indent=2)'
)

# 4. Insert the get_config function after the globals
get_config_func = """
DEFAULT_SERVER_CONFIG = {
    "PAYMENT_TICKET_CATEGORY_ID": 1448805721071292661,
    "AGED_ACC_ROLE_ID": 1449701649668116480,
    "HIGH_KARMA_ROLE_ID": 1449701535041716225,
    "CQS_HIGHEST_ROLE_ID": 1449032645462986822,
    "CQS_HIGH_ROLE_ID": 1449033105968201728,
    "CQS_MOD_ROLE_ID": 1449033262839238710,
    "CQS_LOW_ROLE_ID": 1449033410218692660
}

def get_config(guild_id: int, key: str):
    server_cfg = server_configs.get(str(guild_id), {})
    if key in server_cfg:
        return server_cfg[key]
    return DEFAULT_SERVER_CONFIG.get(key)
"""

content = content.replace(
    'CQS_LOW_ROLE_ID        = 1449033410218692660   # Low CQS (<50)',
    'CQS_LOW_ROLE_ID        = 1449033410218692660   # Low CQS (<50)\n' + get_config_func
)

# 5. Replace references to the constants with get_config calls in the ticket code
content = content.replace(
    'r = guild.get_role(AGED_ACC_ROLE_ID)',
    'r = guild.get_role(get_config(guild.id, "AGED_ACC_ROLE_ID"))'
)
content = content.replace(
    'r = guild.get_role(HIGH_KARMA_ROLE_ID)',
    'r = guild.get_role(get_config(guild.id, "HIGH_KARMA_ROLE_ID"))'
)

cqs_map = """    cqs_role_map = {
        "highest": get_config(guild.id, "CQS_HIGHEST_ROLE_ID"),
        "high":    get_config(guild.id, "CQS_HIGH_ROLE_ID"),
        "moderate": get_config(guild.id, "CQS_MOD_ROLE_ID"),
        "low":     get_config(guild.id, "CQS_LOW_ROLE_ID"),
    }"""
content = re.sub(r'    cqs_role_map = \{[^}]+\}', cqs_map, content)

content = content.replace(
    'if channel.category and channel.category.id == PAYMENT_TICKET_CATEGORY_ID:',
    'if channel.category and channel.category.id == get_config(channel.guild.id, "PAYMENT_TICKET_CATEGORY_ID"):'
)

content = content.replace(
    'all_ticket_categories = TICKET_CATEGORY_IDS | {PAYMENT_TICKET_CATEGORY_ID}',
    'all_ticket_categories = TICKET_CATEGORY_IDS | {get_config(i.guild.id if hasattr(i, "guild") and i.guild else None, "PAYMENT_TICKET_CATEGORY_ID")}'
)

content = content.replace(
    'all_ticket_category_ids = TICKET_CATEGORY_IDS | {PAYMENT_TICKET_CATEGORY_ID}',
    'all_ticket_category_ids = TICKET_CATEGORY_IDS | {get_config(message.guild.id if hasattr(message, "guild") and message.guild else None, "PAYMENT_TICKET_CATEGORY_ID")}'
)

# 6. Add slash command to set config
config_cmd = """
@bot.tree.command(name="setup_verify", description="Staff: Configure the roles and categories for ticket verification on this server")
@app_commands.describe(
    payment_category="Category for payment tickets",
    aged_role="Role for 1+ year old Reddit accounts",
    karma_role="Role for 1000+ Karma Reddit accounts",
    cqs_highest="Role for Highest CQS",
    cqs_high="Role for High CQS",
    cqs_mod="Role for Moderate CQS",
    cqs_low="Role for Low CQS"
)
async def setup_verify(
    i: discord.Interaction, 
    payment_category: discord.CategoryChannel = None,
    aged_role: discord.Role = None,
    karma_role: discord.Role = None,
    cqs_highest: discord.Role = None,
    cqs_high: discord.Role = None,
    cqs_mod: discord.Role = None,
    cqs_low: discord.Role = None
):
    if not is_staff(i.user):
        return await i.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
    
    guild_id = str(i.guild.id)
    if guild_id not in server_configs:
        server_configs[guild_id] = {}
        
    updated = False
    if payment_category: server_configs[guild_id]["PAYMENT_TICKET_CATEGORY_ID"] = payment_category.id; updated = True
    if aged_role: server_configs[guild_id]["AGED_ACC_ROLE_ID"] = aged_role.id; updated = True
    if karma_role: server_configs[guild_id]["HIGH_KARMA_ROLE_ID"] = karma_role.id; updated = True
    if cqs_highest: server_configs[guild_id]["CQS_HIGHEST_ROLE_ID"] = cqs_highest.id; updated = True
    if cqs_high: server_configs[guild_id]["CQS_HIGH_ROLE_ID"] = cqs_high.id; updated = True
    if cqs_mod: server_configs[guild_id]["CQS_MOD_ROLE_ID"] = cqs_mod.id; updated = True
    if cqs_low: server_configs[guild_id]["CQS_LOW_ROLE_ID"] = cqs_low.id; updated = True
    
    if updated:
        save_data()
        await i.response.send_message("✅ Verification configuration has been updated for this server.", ephemeral=True)
    else:
        await i.response.send_message("ℹ️ No configuration options were provided to update.", ephemeral=True)

"""

# Insert the command before the bot.run() or similar, or just at the end of the commands section
content = content.replace(
    '@bot.tree.command(name="verify", description="Staff: Verify ticket")',
    config_cmd + '\n@bot.tree.command(name="verify", description="Staff: Verify ticket")'
)


with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
