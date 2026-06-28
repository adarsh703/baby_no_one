import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add MASTER_SHEET_URL to DEFAULT_SERVER_CONFIG
content = content.replace(
    '"ADMIN_ROLE_ID": 1448719741756768308,',
    '"ADMIN_ROLE_ID": 1448719741756768308,\n    "MASTER_SHEET_URL": "https://docs.google.com/spreadsheets/d/16LsJL4-1Rv8gWbmjpS7GkC9HOmD1JAvLBYcWnGRkpHM/edit",'
)

# 2. Update the local variable inside verify_sheet
content = content.replace(
    'MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/16LsJL4-1Rv8gWbmjpS7GkC9HOmD1JAvLBYcWnGRkpHM/edit"',
    'MASTER_SHEET_URL = get_config(i.guild.id, "MASTER_SHEET_URL")'
)

# 3. Add to setup_config
# Add describe
content = content.replace(
    'admin_role="Admin role for full bot access"\n)',
    'admin_role="Admin role for full bot access",\n    master_sheet_url="Link to the Master Pay Sheet"\n)'
)
# Add parameter
content = content.replace(
    'admin_role: discord.Role = None\n):',
    'admin_role: discord.Role = None,\n    master_sheet_url: str = None\n):'
)
# Add update logic
content = content.replace(
    'if admin_role: server_configs[guild_id]["ADMIN_ROLE_ID"] = admin_role.id; updated = True',
    'if admin_role: server_configs[guild_id]["ADMIN_ROLE_ID"] = admin_role.id; updated = True\n    if master_sheet_url: server_configs[guild_id]["MASTER_SHEET_URL"] = master_sheet_url; updated = True'
)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("done")
