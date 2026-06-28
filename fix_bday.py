import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

old_birthday_check = """@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=IST))
async def birthday_check():
    today = datetime.datetime.now(IST).date()
    today_bday_str = today.strftime("%m-%d")
    
    announce = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
    if announce: 
        await announce.send(f"{E_PARTY} **A brand new day has begun!** Time to farm some positive Aura. Claim your `/daily` now! {E_VIBE}")
        
    bday_channel = GlobalChannelProxy("BIRTHDAY_CHANNEL_ID")
    chat_channel = GlobalChannelProxy("CHAT_CHANNEL_ID")
    guild = bday_channel.guild if bday_channel else None
    
    if bday_channel and guild:
        role = guild.get_role(get_config(guild.id, "BIRTHDAY_ROLE_ID"))
        celebrants = [uid for uid, bday in birthdays.items() if bday == today_bday_str] 
        
        if celebrants:
            expiry = time.time() + 86400
            for uid in celebrants:
                active_birthday_roles[uid] = expiry
                member = guild.get_member(uid)
                if member and role:
                    try: 
                        await member.add_roles(role)
                    except: 
                        pass
                        
            save_data()
            mentions = " ".join([f"<@{uid}>" for uid in celebrants])
            
            embed_bday = discord.Embed(
                title=f"{E_PARTY} Happy Birthday!",
                description=f"Wishing a fantastic birthday to:\\n{mentions}\\n\\nThey have been granted the **Birthday Role** for the next 24 hours! 🎉🎂🎈",
                color=discord.Color.magenta()
            )
            embed_bday.set_image(url="https://media.tenor.com/E62sJ88Xj3kAAAAC/happy-birthday.gif")
            
            try:
                await bday_channel.send(content=mentions, embed=embed_bday)
            except:
                if chat_channel:
                    await chat_channel.send(content=mentions, embed=embed_bday)"""

new_birthday_check = """@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=IST))
async def birthday_check():
    today = datetime.datetime.now(IST).date()
    today_bday_str = today.strftime("%m-%d")
    
    announce = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
    if announce: 
        await announce.send(f"{E_PARTY} **A brand new day has begun!** Time to farm some positive Aura. Claim your `/daily` now! {E_VIBE}")
        
    celebrants = [uid for uid, bday in birthdays.items() if bday == today_bday_str] 
    if not celebrants:
        return
        
    expiry = time.time() + 86400
    for uid in celebrants:
        active_birthday_roles[uid] = expiry
    save_data()
    
    mentions = " ".join([f"<@{uid}>" for uid in celebrants])
    embed_bday = discord.Embed(
        title=f"{E_PARTY} Happy Birthday!",
        description=f"Wishing a fantastic birthday to:\\n{mentions}\\n\\nThey have been granted the **Birthday Role** for the next 24 hours! 🎉🎂🎈",
        color=discord.Color.magenta()
    )
    embed_bday.set_image(url="https://media.tenor.com/E62sJ88Xj3kAAAAC/happy-birthday.gif")
    
    for guild in bot.guilds:
        role_id = get_config(guild.id, "BIRTHDAY_ROLE_ID")
        role = guild.get_role(role_id) if role_id else None
        
        # Add roles in this guild if applicable
        if role:
            for uid in celebrants:
                member = guild.get_member(uid)
                if member:
                    try:
                        await member.add_roles(role)
                    except: pass
        
        # Announce in this guild
        bday_channel_id = get_config(guild.id, "BIRTHDAY_CHANNEL_ID")
        chat_channel_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        bday_channel = bot.get_channel(bday_channel_id) if bday_channel_id else None
        chat_channel = bot.get_channel(chat_channel_id) if chat_channel_id else None
        
        try:
            if bday_channel:
                await bday_channel.send(content=mentions, embed=embed_bday)
            elif chat_channel:
                await chat_channel.send(content=mentions, embed=embed_bday)
        except: pass"""

content = content.replace(old_birthday_check, new_birthday_check)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
