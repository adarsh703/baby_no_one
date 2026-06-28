import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: autokick_check
old_autokick = """@tasks.loop(hours=24)    
async def autokick_check():
    cfg = autokick_cfg
    if not cfg.get("role_id"): 
        return
        
    warn_channel = GlobalChannelProxy("AUTOKICK_WARN_CHANNEL_ID")
    if not warn_channel: 
        return
        
    guild = warn_channel.guild
    role = guild.get_role(cfg["role_id"])
    if not role: 
        return
        
    days_limit = cfg["days"]
    half_days = cfg["days"] / 2.0
    now = time.time()
    to_warn = []
    to_kick = []
    
    for member in role.members:"""

new_autokick = """@tasks.loop(hours=24)    
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
            continue
            
        to_warn = []
        to_kick = []
        
        for member in role.members:"""

content = content.replace(old_autokick, new_autokick)

# Note: The bottom half of autokick_check uses warn_channel. I need to make sure indentation is correct for the guild loop.
# Let's replace the whole autokick_check function to be safe.

old_autokick_full = """@tasks.loop(hours=24)    
async def autokick_check():
    cfg = autokick_cfg
    if not cfg.get("role_id"): 
        return
        
    warn_channel = GlobalChannelProxy("AUTOKICK_WARN_CHANNEL_ID")
    if not warn_channel: 
        return
        
    guild = warn_channel.guild
    role = guild.get_role(cfg["role_id"])
    if not role: 
        return
        
    days_limit = cfg["days"]
    half_days = cfg["days"] / 2.0
    now = time.time()
    to_warn = []
    to_kick = []
    
    for member in role.members:
        if member.bot: 
            continue
            
        uid_str = str(member.id)
        if not user_timers.get(uid_str):
            user_timers[uid_str] = now
            save_data()
            continue
            
        elapsed_days = (now - user_timers[uid_str]) / 86400.0
        
        if elapsed_days >= days_limit: 
            to_kick.append(member)
        elif elapsed_days >= half_days and uid_str not in cfg.get("warned", []):
            to_warn.append(member)
            if "warned" not in cfg: 
                cfg["warned"] = []
            cfg["warned"].append(uid_str)
            
    if to_warn or to_kick: 
        save_data()
        
    if to_kick:
        kicked_names = []
        for m in to_kick:
            try: 
                await m.send(f"You have been kicked from **{guild.name}** as your {days_limit}-day time limit has expired.")
            except: 
                pass
                
            try: 
                await m.kick(reason=f"Time limit of {days_limit} days expired")
                kicked_names.append(f"**{m.display_name}**")
                if str(m.id) in cfg.get("warned", []): 
                    cfg["warned"].remove(str(m.id))
                if str(m.id) in user_timers: 
                    del user_timers[str(m.id)]
            except: 
                pass
                
        if kicked_names and warn_channel:
            await warn_channel.send(embed=discord.Embed(title="👢 Users Auto-Kicked", description=f"The following users failed to open a ticket in time and were removed:\\n{', '.join(kicked_names)}", color=discord.Color.red()))
        
    if to_warn and warn_channel:
        # Removed mass mentions to prevent anti-spam filter triggers
        embed_desc = f"**{len(to_warn)} users** are exactly halfway through their **{days_limit}-day** limit.\\n\\nPlease create a ticket or msg the issue in help channel <#{get_config(guild.id if 'guild' in locals() and guild else 0, 'HELP_CHANNEL_ID')}>, otherwise you will be automatically kicked."
        await warn_channel.send(embed=discord.Embed(title="⚠️ Time Limit Warning!", description=embed_desc, color=discord.Color.orange()))"""

new_autokick_full = """@tasks.loop(hours=24)    
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
            continue
            
        to_warn = []
        to_kick = []
        
        for member in role.members:
            if member.bot: 
                continue
                
            uid_str = str(member.id)
            if not user_timers.get(uid_str):
                user_timers[uid_str] = now
                save_data()
                continue
                
            elapsed_days = (now - user_timers[uid_str]) / 86400.0
            
            if elapsed_days >= days_limit: 
                to_kick.append(member)
            elif elapsed_days >= half_days and uid_str not in cfg.get("warned", []):
                to_warn.append(member)
                if "warned" not in cfg: 
                    cfg["warned"] = []
                cfg["warned"].append(uid_str)
                
        if to_warn or to_kick: 
            save_data()
            
        if to_kick:
            kicked_names = []
            for m in to_kick:
                try: 
                    await m.send(f"You have been kicked from **{guild.name}** as your {days_limit}-day time limit has expired.")
                except: 
                    pass
                    
                try: 
                    await m.kick(reason=f"Time limit of {days_limit} days expired")
                    kicked_names.append(f"**{m.display_name}**")
                    if str(m.id) in cfg.get("warned", []): 
                        cfg["warned"].remove(str(m.id))
                    if str(m.id) in user_timers: 
                        del user_timers[str(m.id)]
                except: 
                    pass
                    
            if kicked_names and warn_channel:
                await warn_channel.send(embed=discord.Embed(title="👢 Users Auto-Kicked", description=f"The following users failed to open a ticket in time and were removed:\\n{', '.join(kicked_names)}", color=discord.Color.red()))
            
        if to_warn and warn_channel:
            # Removed mass mentions to prevent anti-spam filter triggers
            embed_desc = f"**{len(to_warn)} users** are exactly halfway through their **{days_limit}-day** limit.\\n\\nPlease create a ticket or msg the issue in help channel <#{get_config(guild.id, 'HELP_CHANNEL_ID')}>, otherwise you will be automatically kicked."
            await warn_channel.send(embed=discord.Embed(title="⚠️ Time Limit Warning!", description=embed_desc, color=discord.Color.orange()))"""

content = content.replace(old_autokick_full, new_autokick_full)

# Fix 2: server_mood_tracker
old_mood = """@tasks.loop(hours=1)
async def server_mood_tracker():
    global last_mood_check
    now = datetime.datetime.now(IST)
    # Only check once per day, randomly between 6pm-9pm IST
    if not (18 <= now.hour < 21):
        return
    today = now.date().isoformat()
    if last_mood_check == today:
        return
    if random.random() > 0.3:
        return
    last_mood_check = today
    ch = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
    if not ch:
        return
    # Collect recent messages from all non-staff channels
    all_msgs = []
    for cid, log in channel_chat_log.items():
        c = bot.get_channel(cid)
        if c and (not c.category or c.category.name != "Staff Area"):
            all_msgs.extend(list(log)[-10:])
    if len(all_msgs) < 5:
        return
    sample = "\\n".join(all_msgs[-30:])
    mood = await quick_ai(
        f"Based on these recent Discord server messages, describe the server vibe/mood in one punchy sentence. Use emojis. Be fun and accurate.\\n\\nMessages:\\n{sample}",
        max_tokens=160
    )
    if mood:
        await ch.send(f"📡 **Server Mood Check:** {mood}")"""

new_mood = """@tasks.loop(hours=1)
async def server_mood_tracker():
    global last_mood_check
    now = datetime.datetime.now(IST)
    if not (18 <= now.hour < 21):
        return
    today = now.date().isoformat()
    if last_mood_check == today:
        return
    if random.random() > 0.3:
        return
    last_mood_check = today
    
    for guild in bot.guilds:
        ch_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        ch = bot.get_channel(ch_id) if ch_id else None
        if not ch:
            continue
            
        all_msgs = []
        for cid, log in channel_chat_log.items():
            c = bot.get_channel(cid)
            if c and c.guild.id == guild.id and (not c.category or c.category.name != "Staff Area"):
                all_msgs.extend(list(log)[-10:])
        if len(all_msgs) < 5:
            continue
            
        sample = "\\n".join(all_msgs[-30:])
        mood = await quick_ai(
            f"Based on these recent Discord server messages, describe the server vibe/mood in one punchy sentence. Use emojis. Be fun and accurate.\\n\\nMessages:\\n{sample}",
            max_tokens=160
        )
        if mood:
            await ch.send(f"📡 **Server Mood Check:** {mood}")"""

content = content.replace(old_mood, new_mood)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done fixing background tasks")
