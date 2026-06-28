import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix Bug 11: close_all_tickets hardcodes payment category
old_close = "category = i.guild.get_channel(1448805721071292661)"
new_close = "category = i.guild.get_channel(get_config(i.guild.id, 'PAYMENT_TICKET_CATEGORY_ID'))"
content = content.replace(old_close, new_close)

# Fix Bug 17: multiple commands use `interaction` instead of `i`
old_int_check = "interaction.guild.id if \"interaction\" in locals() and interaction else i.guild.id if \"i\" in locals() and i else 0"
new_int_check = "i.guild.id"
content = content.replace(old_int_check, new_int_check)

# Fix Bug 24/25: gamble fairness
old_gamble = """    win_chance = 0 if amount > 150 else 20  # guaranteed loss for bets over 150
    payout_multiplier = 0.90 
    
    if random.randint(1, 100) <= win_chance:"""
new_gamble = """    win_chance = 50
    payout_multiplier = 0.95 
    
    if random.randint(1, 100) <= win_chance:"""
content = content.replace(old_gamble, new_gamble)

# Fix Bug 25: french_roulette fairness
old_roul = """    high_roller = amount > 150  # guaranteed loss flag"""
new_roul = """    high_roller = False"""
content = content.replace(old_roul, new_roul)

# Fix Bug 26: Race condition in reminder_checker
old_rem = """        if fire_dt <= now:
            fired.append(r)
            
    for r in fired:
        pending_reminders.remove(r)
        save_data()"""
new_rem = """        if fire_dt <= now:
            fired.append(r)
            
    if fired:
        global pending_reminders
        pending_reminders = [r for r in pending_reminders if r not in fired]
        save_data()"""
content = content.replace(old_rem, new_rem)

# Fix Bug 28: reshuffle_market can only be used once
old_reshuf = """    if personality_season > 0:
        return await i.response.send_message("❌ This command has already been used.", ephemeral=True)"""
new_reshuf = """    # Removed one-time limit so admins can force market shuffle anytime"""
content = content.replace(old_reshuf, new_reshuf)

# Fix Bug 40: dm_brokies_task spam vector
old_brokie = """@tasks.loop(time=datetime.time(hour=14, minute=0, tzinfo=IST))
async def dm_brokies_task():
    print("📢 Running daily Brokie DM task...")
    for guild in bot.guilds:
        # Find the brokie role
        brokie_role = discord.utils.find(lambda r: "brokie" in r.name.lower(), guild.roles)
        if not brokie_role:
            continue
        
        for member in brokie_role.members:
            if member.bot:
                continue
            try:
                embed = discord.Embed(
                    title="🚀 Ready to start earning? Tons of tasks available!",
                    description=(
                        f"Hey {member.mention}! 💸\\n\\n"
                        "We noticed you haven't been verified yet. We have **multiple tasks available right now** that you can complete to start earning!\\n\\n"
                        "**How to get started:**\\n"
                        "1️⃣ Go to our server and create a ticket\\n"
                        "2️⃣ Get verified quickly\\n"
                        "3️⃣ Start claiming tasks and securing the bag 💰\\n\\n"
                        "Don't miss out on easy earnings! Open your ticket today and let's get you paid."
                    ),
                    color=0x2b2d31
                )
                await member.send(embed=embed)
                await asyncio.sleep(2) # Prevent rate limits
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Failed to DM {member.name}: {e}")"""
new_brokie = """# dm_brokies_task was removed because mass DMing users automatically every day violates Discord's Anti-Spam policy."""
content = content.replace(old_brokie, new_brokie)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done fixing part 4")
