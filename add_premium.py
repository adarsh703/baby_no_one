import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Load and Save Premium Config
load_target = 'server_configs = data.get("server_configs", {})'
load_replacement = 'server_configs = data.get("server_configs", {})\npremium_guilds = data.get("premium_guilds", [])'
if 'premium_guilds = data.get' not in content:
    content = content.replace(load_target, load_replacement)

save_target = '"server_configs": server_configs\n            }'
save_replacement = '"server_configs": server_configs,\n                "premium_guilds": premium_guilds\n            }'
if '"premium_guilds": premium_guilds' not in content:
    content = content.replace(save_target, save_replacement)

# 2. Add Premium Command
premium_cmd = """
@bot.tree.command(name="premium", description="Owner Only: Manage Premium Servers")
@app_commands.choices(action=[
    app_commands.Choice(name="Add Server", value="add"), 
    app_commands.Choice(name="Remove Server", value="remove"),
    app_commands.Choice(name="List Servers", value="list")
])
async def premium_cmd(i: discord.Interaction, action: str, guild_id: str = None):
    # Only the bot owner can use this (hardcoded owner ID)
    if i.user.id != 992008865656868946:
        return await i.response.send_message("❌ This command is restricted to the Bot Owner.", ephemeral=True)
        
    if action == "list":
        if not premium_guilds:
            return await i.response.send_message("No premium servers currently.", ephemeral=True)
        servers = []
        for gid in premium_guilds:
            g = bot.get_guild(int(gid))
            servers.append(f"{g.name if g else 'Unknown'} (`{gid}`)")
        return await i.response.send_message("💎 **Premium Servers:**\\n" + "\\n".join(servers), ephemeral=True)
        
    if not guild_id:
        return await i.response.send_message("❌ You must provide a guild_id to add or remove.", ephemeral=True)
        
    if action == "add":
        if guild_id not in premium_guilds:
            premium_guilds.append(guild_id)
            save_data()
            await i.response.send_message(f"✅ Added `{guild_id}` to Premium Servers!", ephemeral=True)
        else:
            await i.response.send_message(f"`{guild_id}` is already premium.", ephemeral=True)
            
    elif action == "remove":
        if guild_id in premium_guilds:
            premium_guilds.remove(guild_id)
            save_data()
            await i.response.send_message(f"✅ Removed `{guild_id}` from Premium Servers.", ephemeral=True)
        else:
            await i.response.send_message(f"`{guild_id}` is not premium.", ephemeral=True)
"""
if "@bot.tree.command(name=\"premium\"" not in content:
    # Insert before force_market
    content = content.replace('@bot.tree.command(name="force_market"', premium_cmd + '\n@bot.tree.command(name="force_market"')

# 3. Restrict ask_ai
ask_ai_target = """async def ask_ai(user_message: str, username: str, user_id: int, channel_id: int = None, member: discord.Member = None, avatar_url: str = None) -> str:
    if not TOKEN: 
        return None"""
ask_ai_replacement = """async def ask_ai(user_message: str, username: str, user_id: int, channel_id: int = None, member: discord.Member = None, avatar_url: str = None) -> str:
    if not TOKEN: 
        return None
        
    if member and hasattr(member, "guild") and member.guild:
        guild_id_str = str(member.guild.id)
        if guild_id_str not in premium_guilds and member.guild.owner_id != 992008865656868946:
            return "💎 **Premium Feature**\\nThis server has not unlocked AI Chat. The server owner must upgrade to Premium to use this feature!"
"""
if "guild_id_str not in premium_guilds" not in content:
    content = content.replace(ask_ai_target, ask_ai_replacement)

# 4. Restrict server_mood_tracker
mood_target = """        ch_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        ch = bot.get_channel(ch_id) if ch_id else None"""
mood_replacement = """        if str(guild.id) not in premium_guilds and guild.owner_id != 992008865656868946:
            continue
            
        ch_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        ch = bot.get_channel(ch_id) if ch_id else None"""
if "if str(guild.id) not in premium_guilds" not in content.split("async def server_mood_tracker():")[1]:
    content = content.replace(mood_target, mood_replacement, 1)

# 5. Restrict daily_hot_take
hot_take_old = """    ch = GlobalChannelProxy("CHAT_CHANNEL_ID")
    if not ch:
        return
    stock_prices = ", ".join(f"{c}: {v:.1f} Aura" for c, v in stocks.items())
    take = await quick_ai(f"You are a sarcastic stock market analyst for a Discord server economy. Current prices: {stock_prices}. Give one hot take or prediction about these server stocks. Be funny and opinionated. Max 2 sentences. ALWAYS finish your sentence.", max_tokens=300)
    if take:
        embed = discord.Embed(title="🔥 Hot Take of the Day", description=take, color=discord.Color.orange())
        await ch.send(embed=embed)"""

hot_take_new = """    stock_prices = ", ".join(f"{c}: {v:.1f} Aura" for c, v in stocks.items())
    take = await quick_ai(f"You are a sarcastic stock market analyst for a Discord server economy. Current prices: {stock_prices}. Give one hot take or prediction about these server stocks. Be funny and opinionated. Max 2 sentences. ALWAYS finish your sentence.", max_tokens=300)
    if not take:
        return
        
    embed = discord.Embed(title="🔥 Hot Take of the Day", description=take, color=discord.Color.orange())
    for guild in bot.guilds:
        if str(guild.id) not in premium_guilds and guild.owner_id != 992008865656868946:
            continue
        ch_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        ch = bot.get_channel(ch_id) if ch_id else None
        if ch:
            try:
                await ch.send(embed=embed)
            except: pass"""
content = content.replace(hot_take_old, hot_take_new)

# 6. Restrict science fact
science_old = """    channel = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
    if not channel:
        return

    fact = await quick_ai("Share one fascinating science, space, biology or physics fact. Make it mind-blowing and engaging. Start directly with the fact, no intro. 2 sentences max. ALWAYS finish the sentence completely.", max_tokens=200)
    if not fact:
        fact = random.choice(SCIENCE_FACTS)
    embed = discord.Embed(
        title="🔭 Science Fact of the Day",
        description=fact,
        color=discord.Color.teal()
    )
    embed.set_footer(text="Mind blown? Drop a 🤯 below!")
    await channel.send(embed=embed)"""

science_new = """    fact = await quick_ai("Share one fascinating science, space, biology or physics fact. Make it mind-blowing and engaging. Start directly with the fact, no intro. 2 sentences max. ALWAYS finish the sentence completely.", max_tokens=200)
    if not fact:
        fact = random.choice(SCIENCE_FACTS)
    embed = discord.Embed(
        title="🔭 Science Fact of the Day",
        description=fact,
        color=discord.Color.teal()
    )
    embed.set_footer(text="Mind blown? Drop a 🤯 below!")
    
    for guild in bot.guilds:
        if str(guild.id) not in premium_guilds and guild.owner_id != 992008865656868946:
            continue
        ch_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        ch = bot.get_channel(ch_id) if ch_id else None
        if ch:
            try:
                await ch.send(embed=embed)
            except: pass"""
content = content.replace(science_old, science_new)


with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done adding Premium System")
