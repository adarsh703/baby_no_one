import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix the auto-kick warning
old_warn = """    if to_warn:
        mentions = " ".join([m.mention for m in to_warn])
        await warn_channel.send(content=mentions, embed=discord.Embed(title="⚠️ Time Limit Warning!", description=f"You are exactly halfway through your **{days_limit}-day** limit.\\n\\nPlease create a ticket or msg the issue in help channel <#{get_config(guild.id if \\"guild\\" in locals() and guild else 0, \\"HELP_CHANNEL_ID\\")}>, otherwise you will be automatically kicked.", color=discord.Color.orange()))"""

new_warn = """    if to_warn:
        # Removed mass mentions to prevent anti-spam filter triggers
        embed_desc = f"**{len(to_warn)} users** are exactly halfway through their **{days_limit}-day** limit.\\n\\nPlease create a ticket or msg the issue in help channel <#{get_config(guild.id if 'guild' in locals() and guild else 0, 'HELP_CHANNEL_ID')}>, otherwise you will be automatically kicked."
        await warn_channel.send(embed=discord.Embed(title="⚠️ Time Limit Warning!", description=embed_desc, color=discord.Color.orange()))"""

content = content.replace(old_warn, new_warn)

# 2. Add Cooldown to Chat Triggers
old_chat = """    _yo_triggers = {"yo", "yoo", "yooo", "hi", "hello", "wsg", "wassup", "konnichiwa", "konnichiha", "hola", "bonjour", "salut", "ciao", "hallo", "namaste", "salam", "merhaba", "oi", "ola", "hei", "hej", "привет", "안녕", "こんにちは"}
    _gm_triggers = {"gm", "good morning", "good mrng", "gmorning", "subah", "subh", "subha", "good mng"}
    _gn_triggers = {"gn", "good night", "good nite", "goodnight", "raat", "sone ja", "so ja", "sojaon"}
    if text in _gm_triggers:"""

new_chat = """    _chat_cooldowns = getattr(bot, "_chat_cooldowns", {})
    if not hasattr(bot, "_chat_cooldowns"):
        bot._chat_cooldowns = _chat_cooldowns

    _yo_triggers = {"yo", "yoo", "yooo", "hi", "hello", "wsg", "wassup", "konnichiwa", "konnichiha", "hola", "bonjour", "salut", "ciao", "hallo", "namaste", "salam", "merhaba", "oi", "ola", "hei", "hej", "привет", "안녕", "こんにちは"}
    _gm_triggers = {"gm", "good morning", "good mrng", "gmorning", "subah", "subh", "subha", "good mng"}
    _gn_triggers = {"gn", "good night", "good nite", "goodnight", "raat", "sone ja", "so ja", "sojaon"}
    
    # Check cooldown before processing AI replies to avoid rate limit bans
    if text in _gm_triggers or text in _gn_triggers or text in _yo_triggers:
        now_ts = time.time()
        if now_ts - _chat_cooldowns.get("global_chat_trigger", 0) < 10:
            return  # On cooldown, ignore the trigger
        _chat_cooldowns["global_chat_trigger"] = now_ts
        
    if text in _gm_triggers:"""

content = content.replace(old_chat, new_chat)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
