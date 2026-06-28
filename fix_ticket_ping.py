import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

old_send = """    try:
        prompt_msg = await channel.send(content=opener.mention, embed=embed, view=view)
    except Exception as e:"""

new_send = """    try:
        # Removed raw ping to prevent anti-spam trigger if many tickets are opened rapidly
        prompt_msg = await channel.send(embed=embed, view=view)
    except Exception as e:"""

content = content.replace(old_send, new_send)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("done")
