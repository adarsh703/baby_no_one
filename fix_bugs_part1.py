import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Ban command delete_message_days
content = content.replace("delete_message_days=delete_history", "delete_message_seconds=delete_history * 86400")

# Fix 2: GlobalChannelProxy guild property
proxy_class_old = """    @property
    def name(self): return "Global Proxy\""""
proxy_class_new = """    @property
    def name(self): return "Global Proxy"
    @property
    def guild(self): return None"""
content = content.replace(proxy_class_old, proxy_class_new)

# Fix 3: BotDuelRPSView undefined
# I will define it.
bot_rps_view = """class BotDuelRPSView(discord.ui.View):
    def __init__(self, player, amount):
        super().__init__(timeout=60)
        self.player = player
        self.amount = amount
        self.choices = ["rock", "paper", "scissors"]

    async def finish(self, i, p_choice):
        b_choice = random.choice(self.choices)
        uid = self.player.id
        
        win_matrix = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        
        if p_choice == b_choice:
            balance[uid] += self.amount
            await i.response.edit_message(content=f"🤝 **Tie!** We both chose {p_choice}. Your {self.amount} Aura is returned.", view=None)
        elif win_matrix[p_choice] == b_choice:
            winnings = self.amount * 2
            balance[uid] += winnings
            await i.response.edit_message(content=f"🎉 **You Win!** You chose {p_choice}, I chose {b_choice}. You won {winnings} Aura!", view=None)
        else:
            await i.response.edit_message(content=f"💀 **You Lose!** You chose {p_choice}, I chose {b_choice}. I take your {self.amount} Aura.", view=None)
        save_data()

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.secondary)
    async def rock(self, i: discord.Interaction, button: discord.ui.Button):
        if i.user.id != self.player.id: return
        await self.finish(i, "rock")

    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.secondary)
    async def paper(self, i: discord.Interaction, button: discord.ui.Button):
        if i.user.id != self.player.id: return
        await self.finish(i, "paper")

    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.secondary)
    async def scissors(self, i: discord.Interaction, button: discord.ui.Button):
        if i.user.id != self.player.id: return
        await self.finish(i, "scissors")"""
        
# insert it before DuelRPSView
if "class BotDuelRPSView" not in content:
    content = content.replace("class DuelRPSView(discord.ui.View):", bot_rps_view + "\n\nclass DuelRPSView(discord.ui.View):")

# Fix 4: is_staff member instead of m
is_staff_old = """def is_staff(m: discord.Member): 
    return any(r.id in get_config(member.guild.id if "member" in locals() else m.guild.id if "m" in locals() and m else 0, "STAFF_ROLE_IDS") for r in m.roles) or m.guild_permissions.administrator"""
is_staff_new = """def is_staff(m: discord.Member): 
    return any(r.id in get_config(m.guild.id if hasattr(m, 'guild') else 0, "STAFF_ROLE_IDS") for r in m.roles) or m.guild_permissions.administrator"""
content = content.replace(is_staff_old, is_staff_new)

# Fix 5: is_ticket_channel member instead of m
is_ticket_old = """def is_ticket_channel(m: discord.Message):
    return m.channel.category and m.channel.category.id in get_config(member.guild.id if "member" in locals() else m.guild.id if "m" in locals() and m else 0, "TICKET_CATEGORY_IDS")"""
is_ticket_new = """def is_ticket_channel(m: discord.Message):
    return m.channel.category and m.channel.category.id in get_config(m.guild.id if hasattr(m, 'guild') else 0, "TICKET_CATEGORY_IDS")"""
content = content.replace(is_ticket_old, is_ticket_new)

# Fix 6: _run_auto_verify member instead of user
auto_verify_old = """    for rid in get_config(member.guild.id if "member" in locals() else i.guild.id if "i" in locals() and i else 0, "AUTO_ROLE_IDS"):"""
auto_verify_new = """    for rid in get_config(user.guild.id if hasattr(user, 'guild') else 0, "AUTO_ROLE_IDS"):"""
content = content.replace(auto_verify_old, auto_verify_new)

# Fix 7: delete_inactive_tickets message instead of i
delete_tickets_old = """        all_ticket_category_ids = TICKET_CATEGORY_IDS | {get_config(message.guild.id if hasattr(message, "guild") and message.guild else None, "PAYMENT_TICKET_CATEGORY_ID")}"""
delete_tickets_new = """        all_ticket_category_ids = get_config(i.guild.id, "TICKET_CATEGORY_IDS") | {get_config(i.guild.id, "PAYMENT_TICKET_CATEGORY_ID")}"""
content = content.replace(delete_tickets_old, delete_tickets_new)

# Fix 8: add_role_to_tickets uses global TICKET_CATEGORY_IDS
add_role_old = """    all_ticket_categories = TICKET_CATEGORY_IDS | {get_config(i.guild.id if "i" in locals() and i else None, "PAYMENT_TICKET_CATEGORY_ID")}"""
add_role_new = """    all_ticket_categories = get_config(i.guild.id, "TICKET_CATEGORY_IDS") | {get_config(i.guild.id, "PAYMENT_TICKET_CATEGORY_ID")}"""
content = content.replace(add_role_old, add_role_new)

# Fix 9: verify command member instead of i.user
verify_old1 = """        roles_to_add = [i.guild.get_role(rid) for rid in get_config(member.guild.id if "member" in locals() else i.guild.id if "i" in locals() and i else 0, "AUTO_ROLE_IDS") if i.guild.get_role(rid)]"""
verify_new1 = """        roles_to_add = [i.guild.get_role(rid) for rid in get_config(i.guild.id, "AUTO_ROLE_IDS") if i.guild.get_role(rid)]"""
content = content.replace(verify_old1, verify_new1)

verify_old2 = """        for rid in get_config(guild.id if "guild" in locals() and guild else i.guild.id if "i" in locals() and i else 0, "REMOVE_ROLE_IDS"):"""
verify_new2 = """        for rid in get_config(i.guild.id, "REMOVE_ROLE_IDS"):"""
content = content.replace(verify_old2, verify_new2)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done fixing part 1")
