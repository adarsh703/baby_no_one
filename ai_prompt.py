import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add AI_PROMPT to DEFAULT_SERVER_CONFIG
config_old = "DEFAULT_SERVER_CONFIG = {"
config_new = "DEFAULT_SERVER_CONFIG = {\n    \"AI_PROMPT\": AI_SYSTEM,"
if '"AI_PROMPT": AI_SYSTEM' not in content:
    content = content.replace(config_old, config_new)

# 2. Modify ask_ai to use the custom prompt
ask_ai_target = """    system_with_context = AI_SYSTEM + (f"\\n\\n{server_custom_emojis}" if server_custom_emojis else "") + user_context + mem_str + channel_knowledge_str + context_str"""
ask_ai_replacement = """    guild_id = member.guild.id if member and hasattr(member, "guild") and member.guild else None
    if not guild_id and channel_id:
        ch = bot.get_channel(channel_id)
        if ch and hasattr(ch, "guild"):
            guild_id = ch.guild.id
    
    custom_system = get_config(guild_id, "AI_PROMPT") if guild_id else AI_SYSTEM
    if not custom_system:
        custom_system = AI_SYSTEM
        
    system_with_context = custom_system + (f"\\n\\n{server_custom_emojis}" if server_custom_emojis else "") + user_context + mem_str + channel_knowledge_str + context_str"""
content = content.replace(ask_ai_target, ask_ai_replacement)

# 3. Add the /ai_prompt command
cmd = """
@bot.tree.command(name="ai_prompt", description="Set a custom personality/prompt for the AI in this server.")
@app_commands.describe(prompt_text="The base instructions for how the bot should behave (Leave blank to reset to default)")
async def ai_prompt_cmd(i: discord.Interaction, prompt_text: str = None):
    if not i.user.guild_permissions.administrator and i.user.id != 992008865656868946:
        return await i.response.send_message("❌ You must be an Administrator to change the AI prompt.", ephemeral=True)
        
    if str(i.guild.id) not in server_configs:
        server_configs[str(i.guild.id)] = {}
        
    if not prompt_text:
        # Reset to default
        if "AI_PROMPT" in server_configs[str(i.guild.id)]:
            del server_configs[str(i.guild.id)]["AI_PROMPT"]
            save_data()
        return await i.response.send_message("✅ AI Prompt reset to the global default.", ephemeral=True)
        
    server_configs[str(i.guild.id)]["AI_PROMPT"] = prompt_text
    save_data()
    
    await i.response.send_message(f"✅ Custom AI Prompt set successfully! The bot will now act like this:\\n\\n`{prompt_text}`", ephemeral=True)
"""
if "@bot.tree.command(name=\"ai_prompt\"" not in content:
    content = content.replace('@bot.tree.command(name="premium"', cmd + '\n@bot.tree.command(name="premium"')

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done adding AI Prompt feature")
