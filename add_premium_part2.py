import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Restrict gm/gn/yo
triggers_old = """    # Check cooldown before processing AI replies to avoid rate limit bans
    if text in _gm_triggers or text in _gn_triggers or text in _yo_triggers:
        now_ts = time.time()
        if now_ts - _chat_cooldowns.get("global_chat_trigger", 0) < 10:
            return  # On cooldown, ignore the trigger
        _chat_cooldowns["global_chat_trigger"] = now_ts
        
    if text in _gm_triggers:
        reply = await quick_ai(f"{m.author.display_name} said good morning in the server. Reply with a chill personalized good morning. Match language. 1 sentence.", max_tokens=150)
        await m.channel.send(reply if reply else f"Good morning {m.author.mention} 👋")
        return
    elif text in _gn_triggers:
        reply = await quick_ai(f"{m.author.display_name} said good night in the server. Reply with a chill good night message. Match language. 1 sentence.", max_tokens=150)
        await m.channel.send(reply if reply else f"Good night {m.author.mention} 🌙")
        return
    elif text in _yo_triggers:
        yo_reply = await quick_ai(f"{m.author.display_name} just said '{m.content}' in the server chat. Give a short, fun greeting back. Match their language. Max 1 sentence.", max_tokens=160)
        await m.channel.send(yo_reply if yo_reply else yo_bag.get_next())
        return"""

triggers_new = """    # Check cooldown before processing AI replies to avoid rate limit bans
    if text in _gm_triggers or text in _gn_triggers or text in _yo_triggers:
        # Check Premium status
        if not m.guild or (str(m.guild.id) not in premium_guilds and m.guild.owner_id != 992008865656868946):
            return  # Don't trigger auto-replies in free servers
            
        now_ts = time.time()
        if now_ts - _chat_cooldowns.get("global_chat_trigger", 0) < 10:
            return  # On cooldown, ignore the trigger
        _chat_cooldowns["global_chat_trigger"] = now_ts
        
        if text in _gm_triggers:
            reply = await quick_ai(f"{m.author.display_name} said good morning in the server. Reply with a chill personalized good morning. Match language. 1 sentence.", max_tokens=150)
            await m.channel.send(reply if reply else f"Good morning {m.author.mention} 👋")
            return
        elif text in _gn_triggers:
            reply = await quick_ai(f"{m.author.display_name} said good night in the server. Reply with a chill good night message. Match language. 1 sentence.", max_tokens=150)
            await m.channel.send(reply if reply else f"Good night {m.author.mention} 🌙")
            return
        elif text in _yo_triggers:
            yo_reply = await quick_ai(f"{m.author.display_name} just said '{m.content}' in the server chat. Give a short, fun greeting back. Match their language. Max 1 sentence.", max_tokens=160)
            await m.channel.send(yo_reply if yo_reply else yo_bag.get_next())
            return"""
content = content.replace(triggers_old, triggers_new)

# 2. Restrict Sentient Lurker Mode
lurker_old = """        # --- SENTIENT LURKER MODE ---
        if not m.content.startswith('/') and len(text) > 15 and bot.user not in m.mentions:
            import random
            if random.random() < 0.01: # 1% chance
                interject_prompt = f"You are the sarcastic bot of this Discord server. You are lurking. The user {m.author.display_name} just said: '{m.content}'. Jump in uninvited with a witty, funny, or sarcastic 1-sentence comment. Act like you were eavesdropping."
                reply = await quick_ai(interject_prompt, max_tokens=150)
                if reply:
                    await m.channel.send(reply)"""

lurker_new = """        # --- SENTIENT LURKER MODE ---
        if not m.content.startswith('/') and len(text) > 15 and bot.user not in m.mentions:
            # Check Premium status
            if m.guild and (str(m.guild.id) in premium_guilds or m.guild.owner_id == 992008865656868946):
                import random
                if random.random() < 0.01: # 1% chance
                    interject_prompt = f"You are the sarcastic bot of this Discord server. You are lurking. The user {m.author.display_name} just said: '{m.content}'. Jump in uninvited with a witty, funny, or sarcastic 1-sentence comment. Act like you were eavesdropping."
                    reply = await quick_ai(interject_prompt, max_tokens=150)
                    if reply:
                        await m.channel.send(reply)"""
content = content.replace(lurker_old, lurker_new)


with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done adding Premium System Part 2")
