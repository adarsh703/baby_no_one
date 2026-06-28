import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix Bug 7: Remove dead code in ask_ai (lines 790-932)
# The dead code starts with context_str = "" and ends right before quick_ai
dead_code_start = """    # Build channel context string from recent messages
    context_str = ""
    if channel_id and channel_id in channel_chat_log:"""

dead_code_end = """        except Exception as e:
            logging.error(f"Gemini exception: {e}")
    return None"""

if dead_code_start in content and dead_code_end in content:
    start_idx = content.find(dead_code_start)
    end_idx = content.find(dead_code_end) + len(dead_code_end)
    content = content[:start_idx] + content[end_idx:]

# Fix Bug 10 and Bug 41: on_message_delete hardcoded ID and @everyone ping
old_on_msg_delete = """@bot.event
async def on_message_delete(m: discord.Message):
    # Enforce undeletable logs in GIVE_LOG_CHANNEL_ID
    if m.channel.id == 1448767355449512037:
        deleter = m.author.mention  # Default to the author if no audit log is found
        if m.guild:
            await asyncio.sleep(1) # Give Discord a second to generate the audit log
            try:
                # Check audit logs to see if an Admin deleted it
                async for entry in m.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=3):
                    if entry.target.id == m.author.id and entry.extra.channel.id == m.channel.id:
                        deleter = entry.user.mention
                        break
            except Exception:
                pass

        # Repost ANY deleted message (even from users)
        content_prefix = f"@everyone 🚨 **[RESTORED]** {deleter} tried to delete a message from {m.author.mention}:\\n"
        await m.channel.send(content=content_prefix + m.content, embeds=m.embeds)"""

new_on_msg_delete = """@bot.event
async def on_message_delete(m: discord.Message):
    # Enforce undeletable logs in GIVE_LOG_CHANNEL_ID
    if m.guild and m.channel.id == get_config(m.guild.id, "GIVE_LOG_CHANNEL_ID"):
        deleter = m.author.mention  # Default to the author if no audit log is found
        await asyncio.sleep(1) # Give Discord a second to generate the audit log
        try:
            # Check audit logs to see if an Admin deleted it
            async for entry in m.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=3):
                if entry.target.id == m.author.id and entry.extra.channel.id == m.channel.id:
                    deleter = entry.user.mention
                    break
        except Exception:
            pass

        # Repost ANY deleted message (even from users) - removed @everyone spam
        content_prefix = f"🚨 **[RESTORED]** {deleter} tried to delete a message from {m.author.mention}:\\n"
        await m.channel.send(content=content_prefix + m.content, embeds=m.embeds)"""

content = content.replace(old_on_msg_delete, new_on_msg_delete)

# Fix Bug 15: _try_set_reminder logic error
old_try_set_rem = """        if not text:
            text = "ping"
        
        pending_reminders.append({"user_id": user_id, "channel_id": channel_id, "message": text, "time": fire_time})
        save_data()

        if minutes < 60:
            when = f"{minutes} min{'s' if minutes != 1 else ''}"
        elif minutes < 1440:
            h = minutes // 60; m2 = minutes % 60
            when = f"{h}h {m2}m" if m2 else f"{h} hour{'s' if h != 1 else ''}"
        else:
            d = minutes // 1440
            when = f"{d} day{'s' if d != 1 else ''}"

        fire_dt = datetime.datetime.fromtimestamp(fire_time, tz=IST)
        return f"✅ Got it! I'll ping you at **{fire_dt.strftime('%I:%M %p IST')}** (in {when}): *{text}*" """

new_try_set_rem = """        if not text:
            text = "ping"
            
    pending_reminders.append({"user_id": user_id, "channel_id": channel_id, "message": text, "time": fire_time})
    save_data()

    # Calculate when string
    # We need to get minutes from fire_time - now_ts
    diff_secs = fire_time - int(time.time())
    minutes = int(diff_secs / 60)
    
    if minutes < 60:
        when = f"{minutes} min{'s' if minutes != 1 else ''}"
    elif minutes < 1440:
        h = minutes // 60; m2 = minutes % 60
        when = f"{h}h {m2}m" if m2 else f"{h} hour{'s' if h != 1 else ''}"
    else:
        d = minutes // 1440
        when = f"{d} day{'s' if d != 1 else ''}"

    fire_dt = datetime.datetime.fromtimestamp(fire_time, tz=IST)
    return f"✅ Got it! I'll ping you at **{fire_dt.strftime('%I:%M %p IST')}** (in {when}): *{text}*" """

content = content.replace(old_try_set_rem, new_try_set_rem)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done fixing part 3 bugs")
