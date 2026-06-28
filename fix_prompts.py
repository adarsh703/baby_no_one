import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

ask_ai_old = """    custom_system = get_config(guild_id, "AI_PROMPT") if guild_id else AI_SYSTEM
    if not custom_system:
        custom_system = AI_SYSTEM"""

ask_ai_new = """    custom_system = get_config(guild_id, "AI_PROMPT") if guild_id else AI_SYSTEM
    if not custom_system:
        # Give the main server the OG prompt, but give other servers a generic default prompt
        from app import get_main_guild_id
        if guild_id and get_main_guild_id() and guild_id != get_main_guild_id():
            custom_system = "You are a fun, witty, and helpful Discord bot. Keep your answers conversational, natural, and concise."
        else:
            custom_system = AI_SYSTEM"""
content = content.replace(ask_ai_old, ask_ai_new)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done adjusting default prompts")
