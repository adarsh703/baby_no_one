import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

old_autokick_setup = """@bot.tree.command(name="autokick_setup", description="Staff: Setup strict time-limit kick for a role")
async def autokick_setup(i: discord.Interaction, role: discord.Role, days: int):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if days < 2: 
        return await i.response.send_message("Days must be at least 2.", ephemeral=True)
        
    autokick_cfg["role_id"] = role.id
    autokick_cfg["days"] = days
    save_data()
    
    await i.response.send_message(f"✅ **Auto-Kick Enabled!**\\nAnyone with the {role.mention} role will be kicked after {days} days if they don't open a ticket.", ephemeral=True)"""

new_autokick_setup = """@bot.tree.command(name="autokick_setup", description="Staff: Setup strict time-limit kick for a role")
async def autokick_setup(i: discord.Interaction, role: discord.Role, days: int):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if days < 2: 
        return await i.response.send_message("Days must be at least 2.", ephemeral=True)
        
    # Make autokick_cfg multi-server compatible
    guild_id = str(i.guild.id)
    if guild_id not in autokick_cfg:
        autokick_cfg[guild_id] = {}
        
    autokick_cfg[guild_id]["role_id"] = role.id
    autokick_cfg[guild_id]["days"] = days
    save_data()
    
    await i.response.send_message(f"✅ **Auto-Kick Enabled!**\\nAnyone with the {role.mention} role will be kicked after {days} days if they don't open a ticket.", ephemeral=True)"""

content = content.replace(old_autokick_setup, new_autokick_setup)

old_autokick_check2 = """@tasks.loop(hours=24)    
async def autokick_check():
    cfg = autokick_cfg
    if not cfg.get("role_id"): 
        return
        
    days_limit = cfg["days"]
    half_days = cfg["days"] / 2.0
    now = time.time()
    
    for guild in bot.guilds:
        warn_channel_id = get_config(guild.id, "AUTOKICK_WARN_CHANNEL_ID")
        warn_channel = bot.get_channel(warn_channel_id) if warn_channel_id else None
        
        role = guild.get_role(cfg["role_id"])
        if not role: 
            continue"""

new_autokick_check2 = """@tasks.loop(hours=24)    
async def autokick_check():
    now = time.time()
    
    for guild in bot.guilds:
        guild_id_str = str(guild.id)
        # Fallback to global cfg for backwards compatibility if guild config not found
        cfg = autokick_cfg.get(guild_id_str) or (autokick_cfg if "role_id" in autokick_cfg else None)
        if not cfg or not cfg.get("role_id"):
            continue
            
        days_limit = cfg["days"]
        half_days = cfg["days"] / 2.0
            
        warn_channel_id = get_config(guild.id, "AUTOKICK_WARN_CHANNEL_ID")
        warn_channel = bot.get_channel(warn_channel_id) if warn_channel_id else None
        
        role = guild.get_role(cfg["role_id"])
        if not role: 
            continue"""

content = content.replace(old_autokick_check2, new_autokick_check2)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done fixing autokick config")
