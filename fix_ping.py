import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """            # Split the victims into groups of 40 so Discord doesn't block the message for being too long!
            for i in range(0, len(wiped_uids), 40):
                chunk = wiped_uids[i:i + 40]
                
                # This creates the raw text string that actually triggers the ping notification
                ping_string = " ".join([f"<@{u}>" for u in chunk])
                
                embed = discord.Embed(
                    title="💀 The Grim Reaper", 
                    description=f"Swept **{len(chunk)}** inactive accounts for 7 days of silence.\\nAll their Aura has been burned to ash. Say something in chat to stay alive!", 
                    color=discord.Color.dark_theme()
                )
                
                # Send the pings outside the embed, but attach the cool embed below it
                await channel.send(content=ping_string, embed=embed)"""

new_block = """            embed = discord.Embed(
                title="💀 The Grim Reaper", 
                description=f"Swept **{len(wiped_uids)}** inactive accounts for 7 days of silence.\\nAll their Aura has been burned to ash. Say something in chat to stay alive!", 
                color=discord.Color.dark_theme()
            )
            # Just send the cool embed without mass-pinging users to avoid Discord anti-spam flags.
            await channel.send(embed=embed)"""

content = content.replace(old_block, new_block)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
