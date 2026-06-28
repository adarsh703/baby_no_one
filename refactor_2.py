import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add remaining IDs to DEFAULT_SERVER_CONFIG
new_defaults = """DEFAULT_SERVER_CONFIG = {
    "PAYMENT_TICKET_CATEGORY_ID": 1448805721071292661,
    "AGED_ACC_ROLE_ID": 1449701649668116480,
    "HIGH_KARMA_ROLE_ID": 1449701535041716225,
    "CQS_HIGHEST_ROLE_ID": 1449032645462986822,
    "CQS_HIGH_ROLE_ID": 1449033105968201728,
    "CQS_MOD_ROLE_ID": 1449033262839238710,
    "CQS_LOW_ROLE_ID": 1449033410218692660,
    "CHAT_CHANNEL_ID": 1518214909618290790,
    "PAYOUT_CHANNEL_ID": 1449908271937753129,
    "DAILY_ANNOUNCE_CHANNEL_ID": 1448748624375972075,
    "PUBLIC_LOG_CHANNEL_ID": 1448767223781916844,
    "AUTOKICK_WARN_CHANNEL_ID": 1453059081127592130,
    "HELP_CHANNEL_ID": 1448787031810642010,
    "CONFESSION_CHANNEL_ID": 1475013891258974349,
    "BIRTHDAY_CHANNEL_ID": 1473553195723784397,
    "BIRTHDAY_ROLE_ID": 1473554747633045615,
    "GIVE_LOG_CHANNEL_ID": 1448767355449512037,
    "ADMIN_ROLE_ID": 1448719741756768308,
    "TICKET_CATEGORY_IDS": {1448805784652746894, 1448806932575162422, 1451571863825154058, 1451800068641521846, 1457368711630426153, 1471222806200062196, 1495820309750616195, 1506713487315964054, 1506713487315964054, 1512417173652639744, 1512420242801037343, 1512420314447876096},
    "STAFF_ROLE_IDS": {1448719741756768308, 1449035039072452800, 1449035563570303017},
    "AUTO_ROLE_IDS": {1448774516904825026},
    "REMOVE_ROLE_IDS": {1448831320636784660, 1448774246447845518},
    "READ_CATEGORY_IDS": {1448753211245858826, 1448806198953644063, 1448714204964982845, 1448750517798043770, 1449052357340954674}
}"""
content = re.sub(r'DEFAULT_SERVER_CONFIG = \{.*?\}', new_defaults, content, flags=re.DOTALL)

# Add GlobalChannelProxy next to get_config
proxy_code = """
class GlobalChannelProxy:
    def __init__(self, key):
        self.key = key
    def __bool__(self):
        return True
    async def send(self, *args, **kwargs):
        success = False
        for g in bot.guilds:
            cid = get_config(g.id, self.key)
            if cid:
                ch = bot.get_channel(cid)
                if ch:
                    try:
                        await ch.send(*args, **kwargs)
                        success = True
                    except: pass
        return success
    @property
    def id(self): return 0
    @property
    def name(self): return "Global Proxy"
"""
content = content.replace("def get_config(guild_id: int, key: str):", proxy_code + "\ndef get_config(guild_id: int, key: str):")

# Helper map for contexts
# Some usages need GlobalChannelProxy because there is no guild context (or they are global loops)
replacements = [
    # CHAT_CHANNEL_ID
    ('bot.get_channel(CHAT_CHANNEL_ID)', 'bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")'),
    ('if m.channel.id in (CHAT_CHANNEL_ID, CHAT_CHANNEL_ID_2', 'if m.channel.id in (get_config(m.guild.id if m.guild else 0, "CHAT_CHANNEL_ID"), CHAT_CHANNEL_ID_2'),
    ('chat_channel = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")', 'chat_channel = GlobalChannelProxy("CHAT_CHANNEL_ID")'), # Fix double replace
    
    # PAYOUT_CHANNEL_ID
    ('bot.get_channel(PAYOUT_CHANNEL_ID)', 'bot.get_channel(get_config(interaction.guild.id if "interaction" in locals() else i.guild.id if "i" in locals() else 0, "PAYOUT_CHANNEL_ID"))'),
    
    # DAILY_ANNOUNCE_CHANNEL_ID
    ('bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)', 'GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")'),

    # PUBLIC_LOG_CHANNEL_ID
    ('interaction.guild.get_channel(PUBLIC_LOG_CHANNEL_ID)', 'interaction.guild.get_channel(get_config(interaction.guild.id, "PUBLIC_LOG_CHANNEL_ID"))'),

    # AUTOKICK_WARN_CHANNEL_ID
    ('bot.get_channel(AUTOKICK_WARN_CHANNEL_ID)', 'GlobalChannelProxy("AUTOKICK_WARN_CHANNEL_ID")'),

    # HELP_CHANNEL_ID
    ('<#{HELP_CHANNEL_ID}>', '<#{get_config(guild.id if "guild" in locals() and guild else 0, "HELP_CHANNEL_ID")}>'),

    # CONFESSION_CHANNEL_ID
    ('bot.get_channel(CONFESSION_CHANNEL_ID)', 'bot.get_channel(get_config(interaction.guild.id if "interaction" in locals() and interaction else i.guild.id if "i" in locals() and i else 0, "CONFESSION_CHANNEL_ID"))'),

    # BIRTHDAY_CHANNEL_ID
    ('bot.get_channel(BIRTHDAY_CHANNEL_ID)', 'GlobalChannelProxy("BIRTHDAY_CHANNEL_ID")'),

    # BIRTHDAY_ROLE_ID
    ('guild.get_role(BIRTHDAY_ROLE_ID)', 'guild.get_role(get_config(guild.id, "BIRTHDAY_ROLE_ID"))'),

    # GIVE_LOG_CHANNEL_ID
    ('bot.get_channel(GIVE_LOG_CHANNEL_ID)', 'bot.get_channel(get_config(interaction.guild.id if "interaction" in locals() and interaction else i.guild.id if "i" in locals() and i else 0, "GIVE_LOG_CHANNEL_ID"))'),

    # ADMIN_ROLE_ID
    ('ADMIN_ROLE_ID for', 'get_config(i.guild.id, "ADMIN_ROLE_ID") for'),

    # TICKET_CATEGORY_IDS
    ('TICKET_CATEGORY_IDS and', 'get_config(member.guild.id, "TICKET_CATEGORY_IDS") and'),
    ('in TICKET_CATEGORY_IDS', 'in get_config(c.guild.id if "c" in locals() else 0, "TICKET_CATEGORY_IDS")'),
    
    # STAFF_ROLE_IDS
    ('in STAFF_ROLE_IDS', 'in get_config(member.guild.id if "member" in locals() else m.guild.id if "m" in locals() and hasattr(m, "guild") and m.guild else 0, "STAFF_ROLE_IDS")'),
    
    # AUTO_ROLE_IDS
    ('in AUTO_ROLE_IDS', 'in get_config(member.guild.id if "member" in locals() and hasattr(member, "guild") and member.guild else 0, "AUTO_ROLE_IDS")'),
    ('for rid in AUTO_ROLE_IDS:', 'for rid in get_config(guild.id if "guild" in locals() and guild else i.guild.id if "i" in locals() and i else 0, "AUTO_ROLE_IDS"):'),
    ('if i.guild.get_role(rid)]', 'if isinstance(rid, int) and i.guild.get_role(rid)]'),

    # REMOVE_ROLE_IDS
    ('for rid in REMOVE_ROLE_IDS:', 'for rid in get_config(guild.id if "guild" in locals() and guild else i.guild.id if "i" in locals() and i else 0, "REMOVE_ROLE_IDS"):'),

    # READ_CATEGORY_IDS
    ('in READ_CATEGORY_IDS:', 'in get_config(channel.guild.id if "channel" in locals() and channel.guild else 0, "READ_CATEGORY_IDS"):')
]

for old, new in replacements:
    content = content.replace(old, new)

# Fix setup_verify slash command to setup_config and add more options
setup_config_cmd = """
@bot.tree.command(name="setup_config", description="Staff: Configure server specific channels and roles")
@app_commands.describe(
    chat_channel="Main chat channel",
    payout_channel="Channel for payouts",
    announce_channel="Channel for daily announcements",
    public_log_channel="Public logging channel",
    help_channel="Support/Help channel",
    confession_channel="Confession channel",
    birthday_channel="Birthday announcements channel",
    admin_role="Admin role for full bot access"
)
async def setup_config(
    i: discord.Interaction, 
    chat_channel: discord.TextChannel = None,
    payout_channel: discord.TextChannel = None,
    announce_channel: discord.TextChannel = None,
    public_log_channel: discord.TextChannel = None,
    help_channel: discord.TextChannel = None,
    confession_channel: discord.TextChannel = None,
    birthday_channel: discord.TextChannel = None,
    admin_role: discord.Role = None
):
    if not is_staff(i.user):
        return await i.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
    
    guild_id = str(i.guild.id)
    if guild_id not in server_configs:
        server_configs[guild_id] = {}
        
    updated = False
    if chat_channel: server_configs[guild_id]["CHAT_CHANNEL_ID"] = chat_channel.id; updated = True
    if payout_channel: server_configs[guild_id]["PAYOUT_CHANNEL_ID"] = payout_channel.id; updated = True
    if announce_channel: server_configs[guild_id]["DAILY_ANNOUNCE_CHANNEL_ID"] = announce_channel.id; updated = True
    if public_log_channel: server_configs[guild_id]["PUBLIC_LOG_CHANNEL_ID"] = public_log_channel.id; updated = True
    if help_channel: server_configs[guild_id]["HELP_CHANNEL_ID"] = help_channel.id; updated = True
    if confession_channel: server_configs[guild_id]["CONFESSION_CHANNEL_ID"] = confession_channel.id; updated = True
    if birthday_channel: server_configs[guild_id]["BIRTHDAY_CHANNEL_ID"] = birthday_channel.id; updated = True
    if admin_role: server_configs[guild_id]["ADMIN_ROLE_ID"] = admin_role.id; updated = True
    
    if updated:
        save_data()
        await i.response.send_message("✅ General configuration has been updated for this server. For ticket verification, use `/setup_verify`.", ephemeral=True)
    else:
        await i.response.send_message("ℹ️ No configuration options were provided to update.", ephemeral=True)
"""
content = content.replace('@bot.tree.command(name="setup_verify"', setup_config_cmd + '\n@bot.tree.command(name="setup_verify"')

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("done")
