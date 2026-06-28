import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace get_config definition
old_get_config = """def get_config(guild_id: int, key: str):
    server_cfg = server_configs.get(str(guild_id), {})
    if key in server_cfg:
        return server_cfg[key]
    return DEFAULT_SERVER_CONFIG.get(key)"""

new_get_config = """MAIN_GUILD_ID = None

def get_main_guild_id():
    global MAIN_GUILD_ID
    if MAIN_GUILD_ID is not None:
        return MAIN_GUILD_ID
    # Try to find the guild that owns the default CHAT_CHANNEL_ID
    ch = bot.get_channel(1518214909618290790)
    if ch and hasattr(ch, "guild"):
        MAIN_GUILD_ID = ch.guild.id
        return MAIN_GUILD_ID
    return None

def get_config(guild_id: int, key: str):
    server_cfg = server_configs.get(str(guild_id), {})
    if key in server_cfg:
        return server_cfg[key]
    
    # Only fall back to defaults if this is the main server
    main_id = get_main_guild_id()
    if not main_id or guild_id == main_id:
        return DEFAULT_SERVER_CONFIG.get(key)
        
    # Return None (or empty collections) for other servers that haven't set a config
    default_val = DEFAULT_SERVER_CONFIG.get(key)
    if isinstance(default_val, set):
        return set()
    if isinstance(default_val, list):
        return []
    if isinstance(default_val, dict):
        return {}
    return None"""

content = content.replace(old_get_config, new_get_config)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("done")
