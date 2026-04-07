import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import logging
import asynci
import aiohttp
import random
import time
import datetime
from dotenv import load_dotenv
from collections import defaultdict, deque
from typing import Optional
from google import genai
from google.genai import types
load_dotenv()
vertex_client = genai.Client(
    vertexai=True, 
    project="discord-bot-490910", 
    location="us-central1"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CRICKET_API_KEY = os.getenv("CRICKET_API", "")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_SYSTEM = """You are baby_no_one, the bot of this Discord server. Smart, bully, chill, a bit witty. You feel like a real member, not a robot.

RESPONSE RULES:
- NEVER start your reply with "baby_no_one:" — just reply directly.
- SHORT replies always. Max 1-2 sentences for most things. Only go longer if someone asks for a detailed explanation.
- Don't over-explain. Get to the point fast.
- Do the math if asked (show brief working).
- Use display names (e.g. "Ahmed") NOT Discord pings when referring to people in chat.
- Match language: Hindi/Hinglish in → Hindi/Hinglish out. English in → English out.
- CRITICAL EMOJI RULE: The ONLY valid emoji formats are: actual Unicode characters (😊 🔥 💀) OR <:name:id> for server custom emojis. NEVER EVER type :anything: with colons — it shows as plain text. If you want to use a server emoji, copy the EXACT format from the list provided.
- Prefer server custom emojis from the list provided. Never use 😉.
- NEVER mention or comment on anyone's profile picture unless they specifically ask.
- GROUP CHAT: messages are labeled "Name: message". Know who said what. Address only the person who @mentioned you in your reply, unless the question involves others.
- NEVER reply to two different people in one message — pick the one who @mentioned you and answer them.
- You are a bot. You have no WhatsApp, Instagram, phone number, DMs or any social media. Never say "my DMs are open".

SERVER INFO:
- Currency: Aura. Earn by: /daily, chatting, puzzles (50 Aura, 2/day), casino games, stocks
- Games: /bj (blackjack), /french_roulette, /gamble, /dice_duel
- Stocks: $No_ONe $MUFFIN $Jerry $wessi $notpain $DJ_hunks $adel — /invest (max 30 shares, max 400 Aura/tx), /sell, update every 5 mins
- /bal = balance | /portfolio = holdings | /leaderboard = rankings | /help = all commands
- /withdraw when staff opens it (min 1000 Aura). Only staff can /give Aura.
- Net sell = shares × price × 0.95 (5% broker fee)"""

BALANCE_MILESTONES = [1000, 5000, 10000, 25000, 50000, 100000]

async def check_balance_milestone(uid: int, guild):
    for milestone in BALANCE_MILESTONES:
        key = f"{uid}_{milestone}"
        if balance[uid] >= milestone and key not in balance_milestones_announced:
            balance_milestones_announced.add(key)
            save_data()
            ch = guild.get_channel(CHAT_CHANNEL_ID) if guild else bot.get_channel(CHAT_CHANNEL_ID)
            if not ch:
                return
            member = guild.get_member(uid) if guild else None
            name = member.display_name if member else f"<@{uid}>"
            mention = member.mention if member else f"<@{uid}>"
            hype = await quick_ai(
                f"{name} just hit {milestone:,} Aura in a Discord server economy! Write a short hype announcement. Be excited and funny. 1-2 sentences.",
                max_tokens=80
            )
            msg = hype if hype else f"🎉 {mention} just hit **{milestone:,} Aura**! Let's gooo!"
            embed = discord.Embed(description=f"{mention} {msg}", color=discord.Color.gold())
            embed.set_footer(text=f"💰 Balance milestone: {milestone:,} Aura")
            await ch.send(embed=embed)
            break


async def _shock_comment(coin: str, shock: float):
    direction = "pumped" if shock > 0 else "dumped"
    pct = abs(int(shock * 100))
    ch = bot.get_channel(CHAT_CHANNEL_ID)
    if not ch:
        return
    comment = await quick_ai(f"The crypto coin {coin} just {direction} {pct}% in a Discord server economy. Make a short funny/sarcastic comment about it like a stock market commentator. 1 sentence max.", max_tokens=150)
    if comment:
        await ch.send(f"📊 {comment}")


BALANCE_MILESTONES = [1000, 5000, 10000, 25000, 50000, 100000]

async def check_balance_milestone(uid: int, old_bal: int, new_bal: int):
    for milestone in BALANCE_MILESTONES:
        if old_bal < milestone <= new_bal:
            ch = bot.get_channel(CHAT_CHANNEL_ID)
            if not ch:
                return
            member = None
            for g in bot.guilds:
                member = g.get_member(uid)
                if member:
                    break
            name = member.display_name if member else f"<@{uid}>"
            mention = member.mention if member else f"<@{uid}>"
            hype = await quick_ai(
                f"A Discord server member named {name} just hit {milestone:,} Aura balance milestone! "
                f"Write a short hype announcement for the server. Be exciting and fun. 1-2 sentences max.",
                max_tokens=80
            )
            msg = hype if hype else f"🎉 {mention} just hit **{milestone:,} Aura**! Let's go!"
            embed = discord.Embed(
                title=f"💰 {milestone:,} Aura Milestone!",
                description=f"{mention} {msg}",
                color=discord.Color.gold()
            )
            await ch.send(embed=embed)
            break


async def _try_set_reminder(user_id: int, channel_id: int, message: str) -> str:
    """Bulletproof reminder parsing — super fast, catches slang and words like 'a min'."""
    import re as _re
    lower = message.lower()
    
    reminder_keywords = ["remind", "reminder", "याद", "alarm", "ping", "bata", "notify", "wake", "alert", "tag",]
    if not any(k in lower for k in reminder_keywords):
        return None

    now_ts = time.time()
    fire_time = None
    minutes = 0

    rel = _re.search(r'(?:in|after|baad)\s+(a|an|one|\d+)\s*(sec|second|seconds|min|minute|minutes|hour|hours|hr|hrs|day|days|ghante|ghanta)', lower)
    if rel:
        num_str = rel.group(1)
        num = 1 if num_str in ['a', 'an', 'one'] else int(num_str)
        unit = rel.group(2)
        
        if any(u in unit for u in ['hour','hr','ghante','ghanta']):
            minutes = num * 60
        elif 'day' in unit:
            minutes = num * 1440
        elif any(u in unit for u in ['sec','second']):
            fire_time = now_ts + num
            minutes = max(1, num // 60)
        else:
            minutes = num
            
        if fire_time is None:
            fire_time = now_ts + (minutes * 60)

    if not fire_time:
        now_dt = datetime.datetime.now(IST)
        tm = _re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', lower)
        if tm:
            h = int(tm.group(1))
            m = int(tm.group(2)) if tm.group(2) else 0
            ampm = tm.group(3)
            
            if ampm == 'pm' and h != 12: h += 12
            elif ampm == 'am' and h == 12: h = 0
            
            target = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now_dt:
                target += datetime.timedelta(days=1)
                
            fire_time = target.astimezone(datetime.timezone.utc).timestamp()
            minutes = int((fire_time - now_ts) / 60)

    if not fire_time:
        return None

    text = _re.sub(r'<@!?\d+>', '', message) # Strip bot ping
    text = _re.sub(r'\b(?:remind|reminder|ping|alarm|wake|notify)\s*(?:me\s*)?', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'((?:in|after|baad)\s+(?:a|an|one|\d+)\s*(?:min\w*|hour\w*|hr\w*|day\w*|sec\w*|ghante?)|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\b(?:to|about|that|ke baad|baad mein|bata dena|bata de)\b', '', text, flags=_re.IGNORECASE).strip(" ,-:")
    
    if not text:
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
    return f"✅ Got it! I'll ping you at **{fire_dt.strftime('%I:%M %p IST')}** (in {when}): *{text}*"
    
async def _extract_memory(user_id: int, username: str, user_msg: str, bot_reply: str):
    """Uses a tiny AI call to extract core facts from a conversation."""
    prompt = f"From this conversation, extract ONE key fact about {username}. If none, reply NONE.\nUser: {user_msg}\nBot: {bot_reply}"
    try:
        response = await vertex_client.aio.models.generate_content(
           model="gemini-2.5-flash",
           contents=prompt,
           config=types.GenerateContentConfig(max_output_tokens=50, temperature=0.1)
        )
        fact = response.text.strip() if response.text else ""
        if fact and fact.upper() != "NONE":
            if str(user_id) not in user_persistent_memory: 
                user_persistent_memory[str(user_id)] = []
            if fact not in user_persistent_memory[str(user_id)]:
                user_persistent_memory[str(user_id)].append(fact)
                save_data()
    except Exception as e:
        logging.error(f"Memory extraction error: {e}")
    
async def ask_ai(user_message: str, username: str, user_id: int, channel_id: int = None, member: discord.Member = None, avatar_url: str = None) -> str:
    if not TOKEN: 
        return None

    context_str = ""
    if channel_id and channel_id in channel_chat_log:
        recent = list(channel_chat_log[channel_id])[-10:]
        if recent:
            context_str = "\n\nRecent messages in this channel:\n" + "\n".join(recent)

    if channel_id not in ai_conversation_history:
        ai_conversation_history[channel_id] = []
    
    history = ai_conversation_history[channel_id]
    history.append({"role": "user", "content": f"{username}: {user_message}"})
    if len(history) > 60: history = history[-60:]

    user_bal = balance.get(user_id, 0)
    user_streak = daily_streak.get(user_id, 0)
    stock_prices = ", ".join(f"{c}: {v:.1f}" for c, v in stocks.items())
    
    user_context = f"\n\n[User info for {username}]\nAura balance: {user_bal:,}\nDaily streak: {user_streak} days\nCurrent stock prices: {stock_prices}"

    channel_knowledge_str = ""
    if server_channel_knowledge:
        sections = [f"[#{ch_name}]\n{content}" for ch_name, content in server_channel_knowledge.items()]
        channel_knowledge_str = "\n\n[Server Knowledge]\n" + "\n\n".join(sections)

    mem_str = ""
    if user_id in user_persistent_memory and user_persistent_memory[user_id]:
        mem_str = "\n\n[Memory]\n" + "\n".join(f"- {f}" for f in user_persistent_memory[user_id][-20:])

    system_with_context = AI_SYSTEM + (f"\n\n{server_custom_emojis}" if server_custom_emojis else "") + user_context + mem_str + channel_knowledge_str + context_str

    request_contents = [f"{username}: {user_message}"]

    if avatar_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        mime_type = resp.headers.get("Content-Type", "image/png").split(";")[0]
                        request_contents.insert(0, types.Part.from_bytes(data=img_data, mime_type=mime_type))
        except Exception as e:
            logging.error(f"Failed to fetch avatar: {e}")

    try:
        response = await vertex_client.aio.models.generate_content(
            model="gemini-2.5-flash", # Or gemini-2.5-flash
            contents=request_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_with_context,
                max_output_tokens=2000,
                temperature=0.9
            )
        )
        
        reply = response.text.strip()
        if channel_id and reply:
            ai_conversation_history[channel_id].append({"role": "model", "content": reply})
        return reply

    except Exception as e:
        logging.error(f"Vertex AI Error: {e}")
        return None

    context_str = ""
    if channel_id and channel_id in channel_chat_log:
        recent = list(channel_chat_log[channel_id])[-10:]
        if recent:
            context_str = "\n\nRecent messages in this channel (background context only — focus on what the user just asked you):\n" + "\n".join(recent)

    if channel_id not in ai_conversation_history:
        ai_conversation_history[channel_id] = []

    history = ai_conversation_history[channel_id]
    history.append({"role": "user", "content": f"{username}: {user_message}"})

    if len(history) > 60:
        history = history[-60:]
        ai_conversation_history[channel_id] = history

    user_bal = balance.get(user_id, 0)
    user_streak = daily_streak.get(user_id, 0)
    user_portfolio = portfolios.get(user_id, {})
    portfolio_str = ""
    if user_portfolio:
        holdings = []
        for coin, d in user_portfolio.items():
            if isinstance(d, dict) and d.get("shares", 0) > 0:
                holdings.append(f"{coin}: {d['shares']} shares @ {stocks.get(coin, 0):.1f} Aura each")
        if holdings:
            portfolio_str = f"\nTheir portfolio: {', '.join(holdings)}"

    member_info = ""
    if member:
        roles = [r.name for r in member.roles if r.name != "@everyone"]
        is_staff = any(r.id in STAFF_ROLE_IDS for r in member.roles)
        joined = member.joined_at.strftime("%b %Y") if member.joined_at else "unknown"
        bio = member.bio if hasattr(member, "bio") and member.bio else "no bio"
        member_info = (
            f"\nRoles: {', '.join(roles) if roles else 'none'}"
            f"\nIs staff: {'yes' if is_staff else 'no'}"
            f"\nJoined server: {joined}"
            f"\nAccount created: {member.created_at.strftime('%b %Y')}"
            f"\nBio: {bio}"
        )

    stock_prices = ", ".join(f"{c}: {v:.1f}" for c, v in stocks.items())
    now_ist = datetime.datetime.now(IST)
    current_time = now_ist.strftime("%I:%M %p IST, %A %d %B %Y")

    member_keywords = ["who", "their", "his", "her", "staff", "role", "balance of", "streak of", "richest", "leaderboard", "member", "joined", "kiska", "unka", "kaun", "kitna"]
    needs_member_list = any(kw in user_message.lower() for kw in member_keywords)
    guild = None
    for g in bot.guilds:
        guild = g
        break
    server_members_info = ""
    if guild and needs_member_list:
        member_lines = []
        for m in guild.members:
            if m.bot:
                continue
            m_roles = [r.name for r in m.roles if r.name != "@everyone"]
            m_staff = any(r.id in STAFF_ROLE_IDS for r in m.roles)
            m_bal = balance.get(m.id, 0)
            m_streak = daily_streak.get(m.id, 0)
            line = f"{m.display_name}: roles=[{', '.join(m_roles) if m_roles else 'none'}] staff={'yes' if m_staff else 'no'} balance={m_bal} streak={m_streak}"
            member_lines.append(line)
        server_members_info = "\n\n[Server members]\n" + "\n".join(member_lines)

    user_context = (
        f"\n\n[Current time: {current_time}]"
        f"\n\n[User info for {username}]"
        f"\nAura balance: {user_bal:,}"
        f"\nDaily streak: {user_streak} days"
        f"{portfolio_str}"
        f"{member_info}"
        f"\nCurrent stock prices: {stock_prices}"
        f"{server_members_info}"
    )
    channel_knowledge_str = ""
    if server_channel_knowledge:
        sections = []
        for ch_name, content in server_channel_knowledge.items():
            sections.append(f"[#{ch_name}]\n{content}")
        channel_knowledge_str = "\n\n[Server Channel Content — use this to answer questions about rules, info, tasks etc]\n" + "\n\n".join(sections)

    mem_str = ""
    if user_id in user_persistent_memory and user_persistent_memory[user_id]:
        mem_str = "\n\n[What I remember about " + username + "]\n" + "\n".join(f"- {f}" for f in user_persistent_memory[user_id][-20:])

    system_with_context = AI_SYSTEM + (f"\n\n{server_custom_emojis}" if server_custom_emojis else "") + user_context + mem_str + channel_knowledge_str + context_str

    if GEMINI_API_KEY:
        try:
            gemini_messages = []
            for msg in ([{"role": "system", "content": system_with_context}] + history):
                role = "user" if msg["role"] in ("user", "system") else "model"
                gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})
            if avatar_url and gemini_messages:
                try:
                    async with aiohttp.ClientSession() as _img_sess:
                        async with _img_sess.get(str(avatar_url)) as _img_resp:
                            if _img_resp.status == 200:
                                import base64 as _b64
                                img_data = await _img_resp.read()
                                img_b64 = _b64.b64encode(img_data).decode()
                                content_type = _img_resp.headers.get("Content-Type", "image/png").split(";")[0]
                                gemini_messages[-1]["parts"].append({
                                    "inline_data": {"mime_type": content_type, "data": img_b64}
                                })
                except Exception:
                    pass
            payload = {"contents": gemini_messages, "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.9}}
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    if "candidates" in data:
                        candidate = data["candidates"][0]
                        parts = candidate.get("content", {}).get("parts", [])
                        text_parts = [p["text"] for p in parts if "text" in p]
                        if text_parts:
                            reply = " ".join(text_parts).strip()
                            if channel_id and channel_id in ai_conversation_history:
                                ai_conversation_history[channel_id].append({"role": "model", "content": reply})
                            return reply
                    elif "error" in data:
                        logging.error(f"Gemini error: {data['error']}")
        except Exception as e:
            logging.error(f"Gemini exception: {e}")
    return None

async def quick_ai(prompt: str, max_tokens: int = 200) -> str:
    try:
        response = await vertex_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=AI_SYSTEM + "\n\n" + prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.95
            )
        )
        text = response.text.strip()
        
        return text
    except Exception as e:
        logging.error(f"Vertex quick_ai error: {e}")
        return ""


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN missing in .env")

logging.basicConfig(level=logging.INFO)

CHAT_CHANNEL_ID = 1448727099727941836
CHAT_CHANNEL_ID_2 = 1478785863126089759
PAYOUT_CHANNEL_ID = 1449908271937753129
DAILY_ANNOUNCE_CHANNEL_ID = 1448748624375972075
PUBLIC_LOG_CHANNEL_ID = 1448767223781916844 
AUTOKICK_WARN_CHANNEL_ID = 1453059081127592130
HELP_CHANNEL_ID = 1448787031810642010
CONFESSION_CHANNEL_ID = 1475013891258974349 

BIRTHDAY_CHANNEL_ID = 1473553195723784397
BIRTHDAY_ROLE_ID = 1473554747633045615
BIRTHDAY_GIFT_AMOUNT = 700
AURA_TO_USD = 1000
MAX_SHARES_PER_COIN = 30  # Max shares per person per coin
MAX_DAILY_SELL_EARNINGS = 2000  # Max Aura per person per day from selling stocks ($2)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

E_LOAD = "<a:waiting:1456284110556237925>"
E_COIN = "<:wallet_Binance:1488205979362525325>"
E_PARTY = "<a:DGmoni:1448978255213363202>"
E_SUCCESS = "<a:Check:1456283190942498818>"
E_WARN = "<a:Gojo_sad_hu:1456285739728900211>"
E_CHART = "<:reddit_upvote:1448747700920127498>"
E_VIBE = "<a:DGcatVibe:1456283377228316673>"
E_ROAST = "🔥"

GIVEAWAY_BANNER_URL = "https://cdn.discordapp.com/attachments/1451675344305131592/1456295677603876949/20260101_200831.png"

YO_RESPONSES = [
    "Yoo! Ready to stack some Aura today? 💰",
    "The legend has logged in. Wsg!",
    "Ayy! Time to print some money. 📈",
    "Look who decided to show up! Let's get this bread.",
    "Wassup boss. Markets are open, let's grind.",
    "Yo! Don't gamble all your Aura away today.",
    "Welcome back to the trenches. Wsg?",
    "A wild Chad appears. Yo! 🗿",
    "Yooo! Hope your bags are pumping today.",
    "Sup! Did you claim your daily yet or are you lacking?",
    "Wsg! I was just talking about you... good things, mostly.",
    "Yo yo! Let's get these tasks done and bags secured.",
    "Top of the morning! Let's make some moves today.",
    "Yooooo! The server's collective IQ just went up by 1.",
    "Greetings! Ready to hit the casino?",
    "Wsg gang! 🚨 Let's get to work.",
    "Ayo! The chat just got 10x more interesting.",
    "Finally! I was getting bored in here.",
    "Oh you actually showed up. Respect. 🫡",
    "Yo! Check the market before you do anything else.",
    "Wassup! Bags heavy or we still grinding?",
    "The goat has arrived. 🐐",
    "Yo! Don't sleep on the stocks today.",
    "Aye aye captain! Ready to earn some Aura?",
    "Wsg fam! Let's see those task numbers go up.",
    "Bro actually showed up today. Rare. 👀",
    "Wsg! You just made this server 100% more dangerous.",
    "Oh look who it is. The market has been waiting. 📊",
    "Ayo! Someone's ready to cause problems today.",
    "You're here! Now things are about to get interesting.",
    "Wsg! Hope you brought your A-game today.",
    "Leggo! The grind don't stop.",
    "Yo, the server energy just went up. Facts. ⚡",
    "Another day, another bag to secure. Let's go!",
    "Wsg! Don't forget to claim your daily Aura.",
    "Aye! You back. The casino missed you fr.",
    "Yo! Stocks are moving, you might wanna check.",
    "The main character has entered the chat. 🎬",
    "Wassup! Ready to climb that leaderboard?",
    "Bro said let me go make this Aura real quick. Respect.",
    "Yo! Today might be your lucky day. Or not. Spin and see.",
    "Finally someone with taste shows up. Wsg!",
    "Wsg! Don't let the market eat you alive today.",
    "The vibe just changed. You know what it is. 🔥",
    "Ayo big man! What's the plan today?",
    "Wsg! You look like someone who claims their daily on time.",
    "Oh it's you. The one who's definitely not going broke today.",
    "Yo! Still breathing? Good. Now go earn some Aura.",
    "Wsg legend. Try not to gamble everything away this time.",
    "You have arrived. The server is complete. 🫡",
]

ROASTS = [
    "I'd call you a tool, but even tools are actually useful for something.",
    "You're the reason the gene pool desperately needs a lifeguard.",
    "I've seen wet paper towels with more spine than you.",
    "You bring everyone in this server so much joy... the exact second you log off.",
    "I would roast you, but life already did a massive number on you.",
    "If ignorance is truly bliss, you must be the happiest person on the planet.",
    "You have the perfect face for radio and the perfect voice for a silent movie.",
    "I'm not insulting you, I'm just describing you accurately. It just happens to sound like an insult.",
    "You are the human equivalent of a typo.",
    "I'd give you a nasty look, but I see you've already got one permanently stuck on your face.",
    "I'd explain this to you, but I don't have any crayons on me right now.",
    "It's a real shame you can't photoshop a personality.",
    "You're living proof that God has a sense of humor, just a really twisted one.",
    "If I had a single dollar for every smart thing you've ever said, I'd be homeless.",
    "You are basically a participation trophy that breathes.",
    "I would agree with you, but then we'd both be dead wrong and look incredibly stupid.",
    "Your family tree must be a cactus because everyone on it is a prick.",
    "You're not the dumbest person in the world, but you better hope he doesn't die and leave you the title.",
    "I genuinely envy the people who have never had the misfortune of meeting you.",
    "You're like a software update. Whenever I see you, I just think 'Not right now'.",
    "You have the energy of a participation trophy nobody wanted.",
    "Somewhere out there, a tree is working very hard to produce oxygen for you. I think you owe that tree an apology.",
    "You're not stupid, you just have terrible luck thinking.",
    "I've met garden gnomes with more charisma than you.",
    "You're the type of person who gets outsmarted by a revolving door.",
    "If you were a spice, you'd be flour.",
    "You have the social skills of a error 404 page.",
    "Calling you average would be a massive compliment I'm not willing to give.",
    "You're like a cloud. When you disappear, it's a beautiful day.",
    "I'd roast you harder but my mom told me not to burn trash.",
    "Your secret admirer stopped admiring once they found out who you actually are.",
    "You're the human equivalent of a low battery notification.",
    "Even your shadow tries to walk two steps ahead of you.",
    "You're not the sharpest tool in the shed — you're not even in the shed.",
    "I've seen better comebacks in a boomerang tutorial.",
    "You radiate the energy of a phone charger that only works at a specific angle.",
    "You're like WiFi in a basement — weak signal, zero bars.",
    "The only thing sharp about you is your Wi-Fi password.",
    "You're the type to bring a fork to a soup restaurant.",
    "I'd say get well soon but I don't think this is a medical issue.",
    "You peaked in a fever dream nobody had.",
]

class SmartRandomizer:
    def __init__(self, items, save_key: str = None):
        self.items = items
        self.save_key = save_key
        self.bag = []

    def get_next(self):
        if not self.bag:
            self.bag = list(self.items)
            random.shuffle(self.bag)
            if self.save_key:
                _save_bag(self.save_key, self.bag)
        item = self.bag.pop()
        if self.save_key:
            _save_bag(self.save_key, self.bag)
        return item

    def load(self, saved_bag):
        if saved_bag:
            self.bag = saved_bag

def _save_bag(key, bag):
    pass  # bags are saved as part of save_data() to avoid file conflicts

yo_bag = SmartRandomizer(YO_RESPONSES, save_key="yo_bag")
roast_bag = SmartRandomizer(ROASTS, save_key="roast_bag")

DATA_FILE = "data.json"
DEFAULT_STOCKS = {
    "$No_ONe": 100.0,
    "$MUFFIN": 50.0,
    "$Jerry": 10.0,
    "$wessi": 25.0,
    "$notpain": 75.0,
    "$DJ hunks": 200.0,
    "$adel": 150.0
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load JSON: {e}")
            pass
    
    return {
        "messages": {}, 
        "balance": {}, 
        "giveaways": {}, 
        "last_daily": {}, "daily_streak": {}, 
        "last_giveaway": None, 
        "birthdays": {}, 
        "active_birthday_roles": {},
        "claimed_easter_eggs": [], 
        "polls": {},
        "hard_eggs": ["i love you", "who invited him", "the bot knows", "god loves me", "i was first", "i am rich", "i am poor", "i am new here", "one piece is real"],
        "easy_eggs": ["discord", "reddit", "sigma", "aura", "chad", "goat", "based", "bruh"],
        "bot_bank": {"date": datetime.datetime.now(IST).date().isoformat(), "balance": 100},
        "msg_threshold": 10, 
        "msg_reward": 3, 
        "user_timers": {}, 
        "autokick_cfg": {"role_id": None, "days": 14, "warned": []},
        "stocks": DEFAULT_STOCKS, 
        "stock_history": {k: [v]*144 for k, v in DEFAULT_STOCKS.items()},
        "portfolios": {},
        "used_puzzles": [],
        "pending_payouts": {},
        "puzzles_sent_today": 0,
        "puzzle_date": "",
        "daily_sell_earnings": {},
        "sell_earnings_date": "",
        "personality_season": 0
    }

data = load_data()

message_count = defaultdict(int, {int(k): v for k, v in data.get("messages", {}).items()})
balance = defaultdict(int, {int(k): v for k, v in data.get("balance", {}).items()})
last_daily = defaultdict(str, {int(k): str(v) for k, v in data.get("last_daily", {}).items()})
daily_streak = defaultdict(int, {int(k): int(v) for k, v in data.get("daily_streak", {}).items()})
birthdays = defaultdict(str, {int(k): v for k, v in data.get("birthdays", {}).items()})
active_birthday_roles = defaultdict(float, {int(k): v for k, v in data.get("active_birthday_roles", {}).items()})

giveaways = data.get("giveaways", {})
last_giveaway = data.get("last_giveaway")
claimed_easter_eggs = data.get("claimed_easter_eggs", [])
polls = data.get("polls", {}) 
hard_eggs = data.get("hard_eggs", ["i love you", "who invited him", "the bot knows", "god loves me", "i was first", "i am rich", "i am poor", "i am new here", "one piece is real"])
easy_eggs = data.get("easy_eggs", ["discord", "reddit", "sigma", "aura", "chad", "goat", "based", "bruh"])
bot_bank = data.get("bot_bank", {"date": datetime.datetime.now(IST).date().isoformat(), "balance": 100})
msg_threshold = data.get("msg_threshold", 10) 
msg_reward = data.get("msg_reward", 3)
user_timers = data.get("user_timers", {})
autokick_cfg = data.get("autokick_cfg", {"role_id": None, "days": 14, "warned": []})
stocks = data.get("stocks", DEFAULT_STOCKS)
stock_history = data.get("stock_history", {k: [v]*144 for k, v in DEFAULT_STOCKS.items()})
force_market_targets = {}
withdrawal_open_until = None  # datetime or None
pending_aura_requests = {}  # message_id -> {requester, channel_id}
ai_conversation_history = {}  # user_id -> list of {role, content}
balance_milestones_announced = set(data.get("balance_milestones_announced", []))
casino_losses = defaultdict(int, {int(k): v for k, v in data.get("casino_losses", {}).items()})
casino_wins = defaultdict(int, {int(k): v for k, v in data.get("casino_wins", {}).items()})
weekly_stock_start = data.get("weekly_stock_start", {})
last_mood_check = None
weekly_aura_earned = defaultdict(int)   # uid -> aura earned this week
weekly_casino_lost = defaultdict(int)   # uid -> aura lost in casino this week
weekly_start_balance = {}               # uid -> balance at week start
channel_chat_log = {}  # channel_id -> deque of recent messages
server_channel_knowledge = {}  # channel_name -> content
server_custom_emojis = ""
user_persistent_memory = {}  # user_id -> list of key facts  # formatted emoji list for AI prompt
delisted_coins = data.get("delisted_coins", {})
user_persistent_memory = {int(k): v for k, v in data.get("user_persistent_memory", {}).items()}
pending_reminders = data.get("pending_reminders", [])  # list of {user_id, channel_id, message, time}
invite_event_active = data.get("invite_event_active", False)
invite_counts = defaultdict(int, {int(k): v for k, v in data.get("invite_counts", {}).items()})  # inviter_id -> valid invite count
invite_map = data.get("invite_map", {})  # invited_user_id (str) -> inviter_id
cached_invites = {}  # guild_id -> {invite_code -> uses}  # coin -> relist_timestamp

portfolios = defaultdict(lambda: defaultdict(lambda: {"shares": 0, "invested": 0.0}))
for uid_str, holding in data.get("portfolios", {}).items():
    if isinstance(holding, dict):
        for coin, val in holding.items():
            if isinstance(val, (int, float)):
                portfolios[int(uid_str)][coin] = {"shares": int(val), "invested": float(val * stocks.get(coin, 10.0))}
            elif isinstance(val, dict):
                portfolios[int(uid_str)][coin] = {"shares": val.get("shares", 0), "invested": float(val.get("invested", 0.0))}

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "messages": dict(message_count), 
                "balance": dict(balance), 
                "giveaways": giveaways, 
            
                "last_daily": dict(last_daily), "daily_streak": dict(daily_streak), 
                "last_giveaway": last_giveaway, 
                "birthdays": dict(birthdays),
                "active_birthday_roles": dict(active_birthday_roles), 
                "claimed_easter_eggs": claimed_easter_eggs,
                "polls": polls, 
                "hard_eggs": hard_eggs, 
                "easy_eggs": easy_eggs, 
                "bot_bank": bot_bank,
                "msg_threshold": msg_threshold, 
                "msg_reward": msg_reward, 
                "user_timers": user_timers,
                "autokick_cfg": autokick_cfg, 
                "stocks": stocks, 
                "stock_history": stock_history,
                "portfolios": {str(k): dict(v) for k, v in portfolios.items()},
                "used_puzzles": used_puzzles,
                "pending_payouts": pending_payouts,
                "puzzles_sent_today": puzzles_sent_today,
                "puzzle_date": puzzle_date,
                "daily_sell_earnings": dict(daily_sell_earnings),
                "sell_earnings_date": sell_earnings_date,
                "personality_season": personality_season,
                "yo_bag": yo_bag.bag,
                "roast_bag": roast_bag.bag,
                "delisted_coins": delisted_coins,
                "user_persistent_memory": {str(k): v for k, v in user_persistent_memory.items()},
                "pending_reminders": pending_reminders,
                "balance_milestones_announced": list(balance_milestones_announced),
                "casino_losses": dict(casino_losses),
                "casino_wins": dict(casino_wins),
                "weekly_stock_start": weekly_stock_start,
                "invite_event_active": invite_event_active,
                "invite_counts": dict(invite_counts),
                "invite_map": invite_map
            }, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving data: {e}")

TICKET_CATEGORY_IDS = {1448805784652746894, 1448806932575162422, 1451571863825154058, 1451800068641521846, 1457368711630426153, 1471222806200062196}
STAFF_ROLE_IDS = {1448719741756768308, 1449035039072452800, 1449035563570303017}
AUTO_ROLE_IDS = {1448774516904825026}
REMOVE_ROLE_IDS = {1448831320636784660, 1448774246447845518}
BAD_WORDS = {"nigga"}

def is_staff(m: discord.Member): 
    return any(r.id in STAFF_ROLE_IDS for r in m.roles) or m.guild_permissions.administrator

def is_ticket_channel(c: discord.TextChannel): 
    return c.category and c.category.id in TICKET_CATEGORY_IDS

def simple_embed(t, d, c=discord.Color.blue()): 
    return discord.Embed(title=t, description=d, color=c)

def parse_duration(d_str: str) -> Optional[int]:
    d_str = d_str.lower().strip()
    mults = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    if d_str[-1] in mults and d_str[:-1].isdigit(): 
        return int(d_str[:-1]) * mults[d_str[-1]]
    return None

def evaluate_message(text: str) -> int:
    bonus = 0
    words = text.split()
    if "?" in text and len(text) > 15: bonus += 7 
    if any(word in words for word in ['lol', 'lmao', 'haha', '😭', '😂', 'w', 'fr', 'based', 'goat', 'fire', 'wsg', 'money']): bonus += 5 
    if any(word in words for word in ['stfu', 'shut', 'cringe', 'trash', 'dumb', 'idiot', 'loser', 'hate', 'bozo', 'mid']): bonus -= 1 
    if len(text.replace(" ", "")) > 8 and len(set(text.replace(" ", ""))) <= 3: bonus -= 1 
    return bonus

CHART_W = 14   # columns shown in charts (mobile-safe)
CHART_H = 7    # rows shown in charts
SPARK_N = 16   # points shown in sparkline

def _sample(hist, n):
    """Evenly downsample or pad history to exactly n points."""
    if not hist:
        return []
    if len(hist) <= n:
        return list(hist)
    step = (len(hist) - 1) / (n - 1)
    return [hist[round(i * step)] for i in range(n)]

def generate_sparkline(history):
    pts = _sample(history, SPARK_N)
    if not pts:
        return "▅" * SPARK_N
    mn, mx = min(pts), max(pts)
    if mn == mx:
        return "▅" * len(pts)
    chars = " ▂▃▄▅▆▇█"
    extent = mx - mn
    return "".join(chars[min(7, int((x - mn) / extent * 7))] for x in pts)

def generate_line_chart(history, width=CHART_W, height=CHART_H):
    pts = _sample(history, width)
    if not pts:
        return "No data yet."
    mn, mx = min(pts), max(pts)
    if mn == mx:
        mid = height // 2
        lines = []
        for r in range(height - 1, -1, -1):
            row = ("⠤" * width) if r == mid else (" " * width)
            lines.append(f"{int(mn):>5} | {row}")
        return "\n".join(lines)

    pw, ph = width * 2, height * 4
    canvas = [[False] * pw for _ in range(ph)]

    scaled = [round((v - mn) / (mx - mn) * (ph - 1)) for v in pts]
    for i in range(len(scaled) - 1):
        x0 = round(i / (len(pts) - 1) * (pw - 1))
        x1 = round((i + 1) / (len(pts) - 1) * (pw - 1))
        y0, y1 = scaled[i], scaled[i + 1]
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        cx, cy = x0, y0
        while True:
            if 0 <= cx < pw and 0 <= cy < ph:
                canvas[cy][cx] = True
            if cx == x1 and cy == y1:
                break
            e2 = err * 2
            if e2 > -dy:
                err -= dy
                cx += sx
            if e2 < dx:
                err += dx
                cy += sy

    braille_base = 0x2800
    dot_map = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]
    lines = []
    for r in range(height - 1, -1, -1):
        row = ""
        for c in range(width):
            v = 0
            for dr in range(4):
                for dc in range(2):
                    px, py = c * 2 + dc, r * 4 + dr
                    if 0 <= px < pw and 0 <= py < ph and canvas[py][px]:
                        v |= dot_map[dr][dc]
            row += chr(braille_base + v)
        label = mn + (mx - mn) * (r / max(1, height - 1))
        lines.append(f"{int(label):>5} | {row}")
    return "\n".join(lines)

def generate_area_chart(history, height=CHART_H):
    N = 12
    pts = _sample(history, N)
    if not pts:
        return "No data yet."
    mn, mx = min(pts), max(pts)
    spread = max(mx - mn, 1e-6)
    tops = " ▁▂▃▄▅▆▇█"
    lines = []
    for r in range(height - 1, -1, -1):
        row = ""
        for v in pts:
            y = (v - mn) / spread * height  # 0..height float
            if y >= r + 1:
                row += "█"
            elif y > r:
                frac = y - r  # 0..1
                row += tops[max(1, min(8, int(frac * 8)))]
            else:
                row += " "
        label = mn + spread * (r / max(1, height - 1))
        lines.append(f"{int(label):>5} |{row}")
    lines.append("      +" + "─" * N)
    return "\n".join(lines)

def generate_candlestick_chart(history, height=CHART_H):
    pts = _sample(history, 14)
    if len(pts) < 2:
        return "Gathering data for candles..."

    ohlc = []
    for i in range(1, len(pts)):
        o = pts[i-1]
        c = pts[i]
        diff = abs(c - o)
        h = max(o, c) + diff * 0.2
        l = min(o, c) - diff * 0.2
        ohlc.append((o, h, l, c))

    min_val = min(x[2] for x in ohlc)
    max_val = max(x[1] for x in ohlc)
    spread = max(max_val - min_val, 1e-6)

    lines = []
    for r in range(height - 1, -1, -1):
        row_str = ""
        for o, h, l, c in ohlc:
            y_o = (o - min_val) / spread * (height - 1)
            y_c = (c - min_val) / spread * (height - 1)
            y_h = (h - min_val) / spread * (height - 1)
            y_l = (l - min_val) / spread * (height - 1)
            body_top = max(y_o, y_c)
            body_bot = min(y_o, y_c)
            if body_bot - 0.3 <= r <= body_top + 0.3:
                row_str += "█ " if c >= o else "▒ "
            elif y_l - 0.5 <= r <= y_h + 0.5:
                row_str += "| "
            else:
                row_str += "  "
        label_val = min_val + spread * (r / max(1, height - 1))
        lines.append(f"{int(label_val):>4} | {row_str}")
    lines.append("     +" + "-" * (len(ohlc) * 2))
    return "\n".join(lines)


confession_authors = {}

class ConfessionReplyModal(discord.ui.Modal, title="Reply to Confession"):
    reply_text = discord.ui.TextInput(
        label="Your Reply",
        style=discord.TextStyle.paragraph,
        placeholder="Type your reply here... (anonymous unless you are the OP)",
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        msg = interaction.message

        original_msg_id = str(msg.id)
        is_op = confession_authors.get(original_msg_id) == interaction.user.id
        author_label = "🕵️ OP (Original Confessor)" if is_op else "Anonymous Reply"
        author_icon = interaction.user.display_avatar.url if is_op else "https://cdn.discordapp.com/embed/avatars/0.png"

        thread = msg.thread
        if not thread:
            try:
                thread = await msg.create_thread(name="Confession Replies", auto_archive_duration=1440)
            except Exception:
                return await interaction.followup.send("Failed to create thread for replies.", ephemeral=True)

        embed = discord.Embed(description=self.reply_text.value, color=discord.Color.blurple() if is_op else discord.Color.light_embed())
        embed.set_author(name=author_label, icon_url=author_icon)

        reply_msg = await thread.send(embed=embed, view=ThreadReplyView(original_msg_id))
        confession_authors[str(reply_msg.id)] = interaction.user.id

        await interaction.followup.send("✅ Your reply was posted!" + (" (shown as OP)" if is_op else " (anonymous)"), ephemeral=True)


class ThreadReplyModal(discord.ui.Modal, title="Reply in Thread"):
    reply_text = discord.ui.TextInput(
        label="Your Reply",
        style=discord.TextStyle.paragraph,
        placeholder="Type your reply... (anonymous unless you are the OP)",
        max_length=1000
    )

    def __init__(self, original_msg_id: str):
        super().__init__()
        self.original_msg_id = original_msg_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        is_op = confession_authors.get(self.original_msg_id) == interaction.user.id
        author_label = "🕵️ OP (Original Confessor)" if is_op else "Anonymous Reply"
        author_icon = interaction.user.display_avatar.url if is_op else "https://cdn.discordapp.com/embed/avatars/0.png"

        thread = interaction.channel
        embed = discord.Embed(description=self.reply_text.value, color=discord.Color.blurple() if is_op else discord.Color.light_embed())
        embed.set_author(name=author_label, icon_url=author_icon)

        reply_msg = await thread.send(embed=embed, view=ThreadReplyView(self.original_msg_id))
        confession_authors[str(reply_msg.id)] = interaction.user.id

        await interaction.followup.send("✅ Your reply was posted!" + (" (shown as OP)" if is_op else " (anonymous)"), ephemeral=True)


class ThreadReplyView(discord.ui.View):
    def __init__(self, original_msg_id: str):
        super().__init__(timeout=None)
        self.original_msg_id = original_msg_id
        btn = discord.ui.Button(label="Reply", emoji="💬", style=discord.ButtonStyle.secondary, custom_id=f"thread_reply_{original_msg_id[:8]}")
        btn.callback = self.reply_btn
        self.add_item(btn)

    async def reply_btn(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ThreadReplyModal(self.original_msg_id))


class ConfessionSubmitModal(discord.ui.Modal, title="🕵️ Submit a Confession"):
    confession_text = discord.ui.TextInput(
        label="Your Confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type your confession here... (100% anonymous)",
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(CONFESSION_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("Confession channel not found!", ephemeral=True)

        embed = discord.Embed(title="🕵️ Anonymous Confession", description=f'"{self.confession_text.value}"', color=discord.Color.dark_theme())
        embed.set_footer(text="Click below to reply or submit your own confession")

        msg = await channel.send(embed=embed, view=ConfessionView())
        confession_authors[str(msg.id)] = interaction.user.id
        await interaction.response.send_message("✅ Your confession has been submitted anonymously!", ephemeral=True)


class ConfessionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reply to Confession", style=discord.ButtonStyle.secondary, emoji="💬", custom_id="confess_reply_btn")
    async def reply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionReplyModal())

    @discord.ui.button(label="Submit Confession", style=discord.ButtonStyle.primary, emoji="🕵️", custom_id="confess_submit_btn")
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionSubmitModal())

class BirthdayModal(discord.ui.Modal, title="🎂 Set Your Birthday"):
    day = discord.ui.TextInput(label="Day (e.g. 18)", placeholder="18", min_length=1, max_length=2)
    month = discord.ui.TextInput(label="Month (e.g. 02)", placeholder="02", min_length=1, max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = int(self.day.value)
            m = int(self.month.value)
            datetime.date(2024, m, d)
            date_str = f"{d:02d}-{m:02d}"
            
            if interaction.user.id in birthdays:
                return await interaction.response.send_message("❌ You have already set your birthday! Ask staff if you need to reset it.", ephemeral=True)

            birthdays[interaction.user.id] = date_str
            save_data()
            await interaction.response.send_message(f"✅ Birthday set to **{date_str}**! You will receive rewards on this day.", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid date! Please check the Day and Month.", ephemeral=True)

class BirthdayPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎂 Set Birthday", style=discord.ButtonStyle.primary, custom_id="set_bday_btn")
    async def set_bday_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in birthdays:
            return await interaction.response.send_message("You already set your birthday! 🎉", ephemeral=True)
            
        await interaction.response.send_modal(BirthdayModal())

class BlackjackView(discord.ui.View):
    def __init__(self, player: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.player = player
        self.bet = bet
        self.deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 16 
        random.shuffle(self.deck)
        self.p_hand = [self.draw(), self.draw()]
        self.d_hand = [self.dealer_draw(), self.dealer_draw()]

    def draw(self): 
        return self.deck.pop()
        
    def dealer_draw(self):
        if random.random() < 0.05: 
            return random.choice([9, 10, 10, 10, 10, 11])
        return self.deck.pop()
        
    def get_score(self, hand):
        score = sum(hand)
        aces = hand.count(11)
        while score > 21 and aces: 
            score -= 10
            aces -= 1
        return score
        
    def format_hand(self, hand, hide_second=False):
        cards = []
        for idx, val in enumerate(hand):
            if hide_second and idx == 1: 
                cards.append("[ ? ]")
            else: 
                cards.append(f"[ {'A' if val == 11 else str(val)} ]")
        return "  ".join(cards)

    def build_embed(self, game_over=False, msg=""):
        p_score = self.get_score(self.p_hand)
        d_score = self.get_score(self.d_hand)
        
        e = discord.Embed(title="🃏 Casino Blackjack", description=msg, color=discord.Color.from_rgb(43, 45, 49))
        e.add_field(name=f"👤 Your Hand: {p_score}", value=f"```ini\n{self.format_hand(self.p_hand)}\n```", inline=False)
        
        if game_over: 
            e.add_field(name=f"🏦 Dealer's Hand: {d_score}", value=f"```ini\n{self.format_hand(self.d_hand)}\n```", inline=False)
        else: 
            e.add_field(name=f"🏦 Dealer's Hand: ?", value=f"```ini\n{self.format_hand(self.d_hand, hide_second=True)}\n```", inline=False)
            
        return e

    async def end_game(self, i: discord.Interaction, res: str):
        for c in self.children: 
            c.disabled = True
            
        if res == "win":
            profit = int(self.bet * 0.90) 
            balance[self.player.id] += (self.bet + profit)
            msg = f"🎉 You win **{profit}** Aura! *(10% House Tax)*"
            col = discord.Color.green()
        elif res == "lose":
            weekly_casino_lost[self.player.id] += self.bet
            msg = f"💀 You busted and lost **{self.bet}** Aura."
            col = discord.Color.red()
        else: 
            balance[self.player.id] += self.bet
            msg = f"👔 Push! Your bet of **{self.bet}** Aura has been refunded."
            col = discord.Color.orange()
            
        save_data()
        
        final_embed = self.build_embed(True, msg).copy()
        final_embed.set_author(name="Game Over")
        final_embed.color = col
        
        await i.response.edit_message(embed=final_embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.player.id: 
            return await i.response.send_message("Not your game!", ephemeral=True)
            
        self.p_hand.append(self.draw())
        
        if self.get_score(self.p_hand) > 21: 
            await self.end_game(i, "lose")
        else: 
            await i.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.player.id: 
            return await i.response.send_message("Not your game!", ephemeral=True)
            
        d_score = self.get_score(self.d_hand)
        
        while d_score < 17:
            self.d_hand.append(self.dealer_draw())
            d_score = self.get_score(self.d_hand)
            
        p_score = self.get_score(self.p_hand)
        
        if d_score > 21 or p_score > d_score: 
            await self.end_game(i, "win")
        elif d_score > p_score: 
            await self.end_game(i, "lose")
        else: 
            await self.end_game(i, "tie")


class BotDiceDuelView(discord.ui.View):
    def __init__(self, p1: discord.Member, amt: int):
        super().__init__(timeout=120)
        self.p1 = p1
        self.amt = amt

    @discord.ui.button(label="Roll Dice 🎲", style=discord.ButtonStyle.primary)
    async def roll(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.p1.id: 
            return await i.response.send_message("Not your game!", ephemeral=True)
            
        for c in self.children: 
            c.disabled = True
            
        u_roll = random.randint(1, 100)
        b_roll = random.randint(1, 100)
        
        if u_roll > b_roll:
            balance[self.p1.id] += self.amt * 2
            bot_bank["balance"] -= self.amt
            msg = f"**{self.p1.display_name}**: {u_roll}\n**Bot**: {b_roll}\n\n🏆 You win **{self.amt:,} Aura**!\n*(My bank is down to {bot_bank['balance']:,} Aura)*"
            col = discord.Color.green()
        elif b_roll > u_roll:
            bot_bank["balance"] += self.amt
            msg = f"**{self.p1.display_name}**: {u_roll}\n**Bot**: {b_roll}\n\n💀 Bot wins! You lost **{self.amt:,} Aura**.\n*(My bank is now {bot_bank['balance']:,} Aura)*"
            col = discord.Color.red()
        else:
            balance[self.p1.id] += self.amt
            msg = f"Both rolled **{u_roll}**! It's a Tie! Bet refunded."
            col = discord.Color.orange()
            
        save_data()
        await i.response.edit_message(content=None, embed=discord.Embed(title="🎲 Bot Dice Duel Results", description=msg, color=col), view=self)

class BotRouletteView(discord.ui.View):
    def __init__(self, p1: discord.Member, amt: int):
        super().__init__(timeout=300)
        self.p1 = p1
        self.amt = amt
        
        self.btn = discord.ui.Button(label="Pull Trigger 🔫", style=discord.ButtonStyle.danger)
        self.btn.callback = self.pull
        self.add_item(self.btn)

    async def pull(self, i: discord.Interaction):
        if i.user.id != self.p1.id: 
            return await i.response.send_message("Not your game!", ephemeral=True)
            
        if random.randint(1, 6) == 1:
            self.btn.disabled = True
            bot_bank["balance"] += self.amt
            save_data()
            e = discord.Embed(title="💥 BANG!", description=f"You pulled the trigger and the gun fired!\n\n💀 You died and lost **{self.amt:,} Aura**.\n*(My bank is now {bot_bank['balance']:,} Aura)*", color=discord.Color.red())
            return await i.response.edit_message(embed=e, view=self)
            
        self.btn.disabled = True
        e = discord.Embed(title="🔫 Russian Roulette", description="*Click.* You survived.\n\n🤖 Bot is taking its turn...", color=discord.Color.orange())
        await i.response.edit_message(embed=e, view=self)
        
        await asyncio.sleep(1.5)
        
        if random.randint(1, 6) == 1:
            balance[self.p1.id] += self.amt * 2
            bot_bank["balance"] -= self.amt
            save_data()
            e2 = discord.Embed(title="💥 BANG!", description=f"The Bot pulled the trigger and the gun fired!\n\n🏆 You survive and win **{self.amt:,} Aura**!\n*(My bank is down to {bot_bank['balance']:,} Aura)*", color=discord.Color.green())
            msg = await i.original_response()
            return await msg.edit(embed=e2, view=self)
            
        self.btn.disabled = False
        e3 = discord.Embed(title="🔫 Russian Roulette", description="*Click.* The Bot survived.\n\nIt is your turn again. Pull the trigger.", color=discord.Color.blue())
        msg = await i.original_response()
        await msg.edit(embed=e3, view=self)

class BotDrawView(discord.ui.View):
    def __init__(self, p1: discord.Member, amt: int):
        super().__init__(timeout=300)
        self.p1 = p1
        self.amt = amt
        self.active = False
        self.bot_won = False
        
        self.btn = discord.ui.Button(label="DRAW! 🔫", style=discord.ButtonStyle.danger, disabled=True, custom_id="bot_draw_btn")
        self.btn.callback = self.draw_clicked
        self.add_item(self.btn)

    async def bot_shoot(self, message: discord.Message):
        bot_reaction = random.uniform(0.3, 1.0)
        await asyncio.sleep(bot_reaction)
        
        if not self.active: 
            return
            
        self.active = False
        self.bot_won = True
        self.btn.disabled = True
        bot_bank["balance"] += self.amt
        save_data()
        
        e = discord.Embed(title="⚡ Quick Draw Results", description=f"💥 The Bot shot first! (Reaction: {bot_reaction:.2f}s)\n\n💀 You lost **{self.amt:,} Aura**.\n*(My bank is now {bot_bank['balance']:,} Aura)*", color=discord.Color.red())
        try: 
            await message.edit(embed=e, view=self)
        except: 
            pass

    async def draw_clicked(self, i: discord.Interaction):
        if i.user.id != self.p1.id: 
            return await i.response.send_message("Not your game!", ephemeral=True)
            
        if not self.active:
            if self.bot_won:
                return await i.response.send_message("You were too slow!", ephemeral=True)
            return await i.response.send_message("You pulled too early! Wait for the DRAW signal.", ephemeral=True)
            
        self.active = False
        self.btn.disabled = True
        balance[self.p1.id] += self.amt * 2
        bot_bank["balance"] -= self.amt
        save_data()
        
        e = discord.Embed(title="⚡ Quick Draw Results", description=f"💥 {i.user.mention} shot first and killed the Bot!\n\n🏆 You won **{self.amt:,} Aura**!\n*(My bank is down to {bot_bank['balance']:,} Aura)*", color=discord.Color.green())
        await i.response.edit_message(content=None, embed=e, view=self)

    async def start_draw(self, message: discord.Message):
        await asyncio.sleep(random.uniform(3.0, 8.0))
        
        self.btn.disabled = False
        self.active = True
        
        embed = discord.Embed(title="🚨 DRAW! 🚨", description="CLICK THE BUTTON FIRST!", color=discord.Color.green())
        try: 
            await message.edit(embed=embed, view=self)
            asyncio.create_task(self.bot_shoot(message))
        except: 
            pass

class DuelRPSView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, amt: int):
        super().__init__(timeout=120)
        self.p1 = p1
        self.p2 = p2
        self.amt = amt
        self.choices = {}

    async def resolve(self, i: discord.Interaction):
        c1 = self.choices[self.p1.id]
        c2 = self.choices[self.p2.id]
        
        for c in self.children: 
            c.disabled = True
        
        if c1 == c2:
            balance[self.p1.id] += self.amt
            balance[self.p2.id] += self.amt
            msg = f"Both chose **{c1}**! It's a Tie! Bets refunded."
            color = discord.Color.orange()
        else:
            win_map = {"🪨 Rock": "✂️ Scissors", "📄 Paper": "🪨 Rock", "✂️ Scissors": "📄 Paper"}
            
            if win_map[c1] == c2:
                winner = self.p1
                loser = self.p2
            else:
                winner = self.p2
                loser = self.p1
                
            balance[winner.id] += self.amt * 2
            msg = f"**{self.p1.display_name}**: {c1}\n**{self.p2.display_name}**: {c2}\n\n🏆 {winner.mention} wins **{self.amt*2:,} Aura**!"
            color = discord.Color.green()
        
        save_data()
        await i.message.edit(content=None, embed=discord.Embed(title="⚔️ Duel Results!", description=msg, color=color), view=self)

    async def handle_choice(self, i: discord.Interaction, choice: str):
        if i.user.id not in [self.p1.id, self.p2.id]: 
            return await i.response.send_message("Not your duel!", ephemeral=True)
        
        self.choices[i.user.id] = choice
        
        if len(self.choices) == 2: 
            await self.resolve(i)
        else:
            await i.response.send_message(f"Choice locked to **{choice}**. You can change it before your opponent plays!", ephemeral=True)

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.primary)
    async def rock(self, i: discord.Interaction, b: discord.ui.Button): 
        await self.handle_choice(i, "🪨 Rock")
        
    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.primary)
    async def paper(self, i: discord.Interaction, b: discord.ui.Button): 
        await self.handle_choice(i, "📄 Paper")
        
    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.primary)
    async def scissors(self, i: discord.Interaction, b: discord.ui.Button): 
        await self.handle_choice(i, "✂️ Scissors")

class EscrowView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, amt: int, cond: str):
        super().__init__(timeout=None)
        self.p1 = p1
        self.p2 = p2
        self.amt = amt
        self.cond = cond

    @discord.ui.button(label="Accept Bet", style=discord.ButtonStyle.success)
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.p2.id: 
            return await i.response.send_message("Not your bet.", ephemeral=True)
            
        if balance[self.p1.id] < self.amt or balance[self.p2.id] < self.amt: 
            return await i.response.send_message("Insufficient funds!", ephemeral=True)
            
        balance[self.p1.id] -= self.amt
        balance[self.p2.id] -= self.amt
        save_data()
        
        self.clear_items()
        
        b1 = discord.ui.Button(label=f"Concede: {self.p1.display_name} Won", style=discord.ButtonStyle.primary)
        b2 = discord.ui.Button(label=f"Concede: {self.p2.display_name} Won", style=discord.ButtonStyle.primary)

        async def p1_won_callback(i2: discord.Interaction):
            if i2.user.id != self.p2.id: 
                return await i2.response.send_message("Only the LOSER can click this to concede.", ephemeral=True)
                
            balance[self.p1.id] += self.amt * 2
            save_data()
            
            for child in self.children: 
                child.disabled = True
                
            await i2.response.edit_message(content=f"✅ {self.p1.mention} wins the **{self.amt*2:,} Aura** pot!", embed=None, view=self)

        async def p2_won_callback(i2: discord.Interaction):
            if i2.user.id != self.p1.id: 
                return await i2.response.send_message("Only the LOSER can click this to concede.", ephemeral=True)
                
            balance[self.p2.id] += self.amt * 2
            save_data()
            
            for child in self.children: 
                child.disabled = True
                
            await i2.response.edit_message(content=f"✅ {self.p2.mention} wins the **{self.amt*2:,} Aura** pot!", embed=None, view=self)

        b1.callback = p1_won_callback
        b2.callback = p2_won_callback
        
        self.add_item(b1)
        self.add_item(b2)
        
        await i.response.edit_message(embed=discord.Embed(title="🤝 Escrow Locked!", description=f"**Pot:** {self.amt*2:,} Aura\n**Condition:** {self.cond}\n\n*When the bet is over, the loser must click their button to concede the money to the winner.*", color=discord.Color.blue()), view=self)

class DiceDuelView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, amt: int):
        super().__init__(timeout=120)
        self.p1 = p1
        self.p2 = p2
        self.amt = amt
        self.rolls = {}

    @discord.ui.button(label="Roll Dice 🎲", style=discord.ButtonStyle.primary)
    async def roll(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id not in [self.p1.id, self.p2.id]:
            return await i.response.send_message("Not your duel!", ephemeral=True)
        if i.user.id in self.rolls:
            return await i.response.send_message("You already rolled!", ephemeral=True)

        self.rolls[i.user.id] = random.randint(1, 100)
        await i.response.send_message(f"🎲 You rolled **{self.rolls[i.user.id]}**! Waiting for opponent...", ephemeral=True)

        if len(self.rolls) == 2:
            r1 = self.rolls[self.p1.id]
            r2 = self.rolls[self.p2.id]
            for c in self.children:
                c.disabled = True

            if r1 > r2:
                winner, loser, wr, lr = self.p1, self.p2, r1, r2
            elif r2 > r1:
                winner, loser, wr, lr = self.p2, self.p1, r2, r1
            else:
                balance[self.p1.id] += self.amt
                balance[self.p2.id] += self.amt
                save_data()
                await i.message.edit(embed=discord.Embed(title="🎲 Dice Duel — Tie!", description=f"Both rolled **{r1}**! Bets refunded.", color=discord.Color.orange()), view=self)
                return

            balance[winner.id] += self.amt * 2
            save_data()
            msg = f"**{self.p1.display_name}**: {r1}\n**{self.p2.display_name}**: {r2}\n\n🏆 {winner.mention} wins **{self.amt*2:,} Aura**!"
            await i.message.edit(embed=discord.Embed(title="🎲 Dice Duel Results", description=msg, color=discord.Color.green()), view=self)


class RouletteView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, amt: int):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.amt = amt
        self.current_turn = p2  # p2 goes first as per accept message

        self.btn = discord.ui.Button(label="Pull Trigger 🔫", style=discord.ButtonStyle.danger)
        self.btn.callback = self.pull
        self.add_item(self.btn)

    async def pull(self, i: discord.Interaction):
        if i.user.id != self.current_turn.id:
            return await i.response.send_message("It's not your turn!", ephemeral=True)

        if random.randint(1, 6) == 1:
            winner = self.p2 if self.current_turn == self.p1 else self.p1
            self.btn.disabled = True
            balance[winner.id] += self.amt * 2
            save_data()
            e = discord.Embed(title="💥 BANG!", description=f"{self.current_turn.mention} pulled the trigger and it fired!\n\n🏆 {winner.mention} wins **{self.amt*2:,} Aura**!", color=discord.Color.red())
            return await i.response.edit_message(embed=e, view=self)

        self.current_turn = self.p2 if self.current_turn == self.p1 else self.p1
        self.btn.disabled = False
        e = discord.Embed(title="🔫 Russian Roulette", description=f"*Click.* They survived!\n\n{self.current_turn.mention}, it's your turn. Pull the trigger.", color=discord.Color.orange())
        await i.response.edit_message(embed=e, view=self)


class DrawView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, amt: int):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.amt = amt
        self.active = False
        self.winner_decided = False

        self.btn = discord.ui.Button(label="DRAW! 🔫", style=discord.ButtonStyle.danger, disabled=True, custom_id="pvp_draw_btn")
        self.btn.callback = self.draw_clicked
        self.add_item(self.btn)

    async def draw_clicked(self, i: discord.Interaction):
        if i.user.id not in [self.p1.id, self.p2.id]:
            return await i.response.send_message("Not your duel!", ephemeral=True)
        if not self.active:
            return await i.response.send_message("Too early! Wait for the DRAW signal.", ephemeral=True)
        if self.winner_decided:
            return

        self.active = False
        self.winner_decided = True
        self.btn.disabled = True
        winner = i.user
        loser = self.p2 if winner.id == self.p1.id else self.p1
        balance[winner.id] += self.amt * 2
        save_data()
        e = discord.Embed(title="⚡ Quick Draw Results", description=f"💥 {winner.mention} drew first!\n\n🏆 {winner.mention} wins **{self.amt*2:,} Aura**!", color=discord.Color.green())
        await i.response.edit_message(content=None, embed=e, view=self)

    async def start_draw(self, message: discord.Message):
        await asyncio.sleep(random.uniform(3.0, 8.0))
        if self.winner_decided:
            return
        self.btn.disabled = False
        self.active = True
        embed = discord.Embed(title="🚨 DRAW! 🚨", description="CLICK THE BUTTON FIRST!", color=discord.Color.green())
        try:
            await message.edit(embed=embed, view=self)
        except:
            pass


class AcceptDuelView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, amt: int, game_type: str):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.amt = amt
        self.game_type = game_type

    @discord.ui.button(label="Accept Duel", style=discord.ButtonStyle.success)
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.p2.id: 
            return await i.response.send_message("Not your duel!", ephemeral=True)
            
        if balance[self.p1.id] < self.amt or balance[self.p2.id] < self.amt: 
            return await i.response.send_message("Insufficient funds!", ephemeral=True)
        
        balance[self.p1.id] -= self.amt
        balance[self.p2.id] -= self.amt
        save_data()
            
        if self.game_type == "rps":
            view = DuelRPSView(self.p1, self.p2, self.amt)
            embed = discord.Embed(title="⚔️ RPS Duel Accepted!", description=f"**{self.p1.display_name} vs {self.p2.display_name}**\n*Both players must click a button below to attack!*", color=discord.Color.red())
            await i.response.edit_message(content=None, embed=embed, view=view)
            
        elif self.game_type == "dice":
            view = DiceDuelView(self.p1, self.p2, self.amt)
            embed = discord.Embed(title="🎲 Dice Duel Accepted!", description=f"**{self.p1.display_name} vs {self.p2.display_name}**\n*Click the button to roll your 1-100 die!*", color=discord.Color.red())
            await i.response.edit_message(content=None, embed=embed, view=view)
            
        elif self.game_type == "roulette":
            view = RouletteView(self.p1, self.p2, self.amt)
            embed = discord.Embed(title="🔫 Russian Roulette Accepted!", description=f"**{self.p1.display_name} vs {self.p2.display_name}**\n*There is 1 bullet in the 6-chamber cylinder.*\n\n{self.p2.mention}, you go first. Pull the trigger.", color=discord.Color.dark_red())
            await i.response.edit_message(content=None, embed=embed, view=view)
            
        elif self.game_type == "draw":
            view = DrawView(self.p1, self.p2, self.amt)
            embed = discord.Embed(title="⚡ Quick Draw Accepted!", description=f"**{self.p1.display_name} vs {self.p2.display_name}**\n*Stand back to back... wait for the red DRAW signal to click the button!*", color=discord.Color.gold())
            await i.response.edit_message(content=None, embed=embed, view=view)
            msg = await i.original_response() 
            asyncio.create_task(view.start_draw(msg))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id not in [self.p1.id, self.p2.id]: 
            return await i.response.send_message("Not your duel!", ephemeral=True)
            
        for c in self.children: 
            c.disabled = True
            
        await i.response.edit_message(content=f"Duel cancelled by {i.user.mention}.", embed=None, view=self)


class PayoutView(discord.ui.View):
    def __init__(self, uid: int, amt: int, method: str, details: str, msg_id: str = "0"):
        super().__init__(timeout=None)
        self.uid = uid
        self.amt = amt
        self.method = method
        self.details = details
        self.msg_id = msg_id

    @discord.ui.button(label="Mark Paid", style=discord.ButtonStyle.success, custom_id="payout_approve")
    async def approve(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not is_staff(interaction.user): 
            return await interaction.response.send_message("Staff only.", ephemeral=True)

        msg_id = str(interaction.message.id)
        pdata = pending_payouts.get(msg_id, {})
        uid = pdata.get("uid", self.uid)
        amt = pdata.get("amt", self.amt)
        method = pdata.get("method", self.method)
        details = pdata.get("details", self.details)

        for c in self.children: 
            c.disabled = True

        user = bot.get_user(uid)
        if user:
            item = f"${(amt/AURA_TO_USD):.2f} via {method.upper()}" if method != "reddit" else "Reddit Account"
            try: 
                await user.send(embed=simple_embed("✅ Payout Processed!", f"Your withdrawal for **{item}** was completed!\nDetails: `{details}`", discord.Color.green()))
            except: 
                pass

        public_channel = interaction.guild.get_channel(PUBLIC_LOG_CHANNEL_ID)
        if public_channel:
            item_public = f"${(amt/AURA_TO_USD):.2f}" if method != "reddit" else "Reddit Account"
            await public_channel.send(embed=simple_embed(f"{E_SUCCESS} Withdrawal Successful!", f"<@{uid}> just withdrew **{item_public}** ({amt:,} Aura)!\nKeep chatting to earn more. {E_VIBE}", discord.Color.green()))

        pending_payouts.pop(msg_id, None)
        save_data()

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ PAYOUT COMPLETED"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Reject & Refund", style=discord.ButtonStyle.danger, custom_id="payout_reject")
    async def reject(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not is_staff(interaction.user): 
            return await interaction.response.send_message("Staff only.", ephemeral=True)

        msg_id = str(interaction.message.id)
        pdata = pending_payouts.get(msg_id, {})
        uid = pdata.get("uid", self.uid)
        amt = pdata.get("amt", self.amt)

        balance[uid] += amt

        for c in self.children: 
            c.disabled = True

        user = bot.get_user(uid)
        if user:
            try: 
                await user.send(embed=simple_embed("🛑 Payout Rejected", f"Your withdrawal of **{amt} Aura** was rejected and refunded.", discord.Color.red()))
            except: 
                pass

        public_channel = interaction.guild.get_channel(PUBLIC_LOG_CHANNEL_ID)
        if public_channel:
            await public_channel.send(embed=simple_embed(f"❌ Withdrawal Rejected", f"<@{uid}>'s withdrawal for **{amt:,} Aura** was rejected and refunded.", discord.Color.red()))

        pending_payouts.pop(msg_id, None)
        save_data()

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ REJECTED & REFUNDED"
        await interaction.response.edit_message(embed=embed, view=self)

class PollView(discord.ui.View):
    def __init__(self, poll_id: str):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.pdata = polls.get(poll_id, {})
        self.q = self.pdata.get("q", "Unknown Poll")
        self.opts = self.pdata.get("opts", [])
        self.votes = self.pdata.get("votes", {})
        
        for idx, opt in enumerate(self.opts):
            btn = discord.ui.Button(label=opt[:80], style=discord.ButtonStyle.primary, custom_id=f"poll_{poll_id}_{idx}")
            btn.callback = self.make_callback(idx)
            self.add_item(btn)
            
        v_btn = discord.ui.Button(label="View Votes", style=discord.ButtonStyle.secondary, emoji="👀", custom_id=f"poll_view_{poll_id}")
        v_btn.callback = self.view_votes
        self.add_item(v_btn)

    def make_callback(self, idx):
        async def cb(i: discord.Interaction):
            uid_str = str(i.user.id)
            if self.votes.get(uid_str) == idx: 
                del self.votes[uid_str] 
            else: 
                self.votes[uid_str] = idx 
                
            save_data()
            await i.response.edit_message(embed=self.build_embed(), view=self)
            
        return cb

    async def view_votes(self, i: discord.Interaction):
        if not self.votes: 
            return await i.response.send_message("No votes yet!", ephemeral=True)
            
        desc = ""
        for idx, opt in enumerate(self.opts):
            voters = [f"<@{uid}>" for uid, opt_idx in self.votes.items() if opt_idx == idx]
            desc += f"**{opt}**\n" + (", ".join(voters) if voters else "None") + "\n\n"
            
        await i.response.send_message(embed=discord.Embed(title="🗳️ Poll Voters", description=desc[:4000], color=discord.Color.teal()), ephemeral=True)

    def build_embed(self) -> discord.Embed:
        tot = len(self.votes)
        e = discord.Embed(title=f"📊 {self.q}", color=discord.Color.teal())
        
        author_name = self.pdata.get("author_name", "Unknown")
        author_icon = self.pdata.get("author_icon")
        
        if author_icon:
            e.set_author(name=f"Poll by {author_name}", icon_url=author_icon)
        else:
            e.set_author(name=f"Poll by {author_name}")
            
        desc = ""
        for idx, opt in enumerate(self.opts):
            cnt = sum(1 for v in self.votes.values() if v == idx)
            pct = (cnt / tot * 100) if tot > 0 else 0
            filled = int((pct / 100) * 15)
            bar = "█" * filled + "░" * (15 - filled)
            desc += f"**{opt}**\n`{bar}` **{pct:.1f}%** ({cnt} votes)\n\n"
            
        e.description = desc
        e.set_footer(text=f"Total Votes: {tot}")
        return e

def build_giveaway_embed(g: dict, guild: discord.Guild) -> discord.Embed:
    e = discord.Embed(title=f"{E_PARTY} **ACTIVE GIVEAWAY**", description=f"### Prize is {g['prize']}\nClick below to enter!", color=discord.Color.gold())
    e.add_field(name="⏱️ Ends", value=f"<t:{int(g['end_time'])}:R>", inline=True)
    e.add_field(name="Host", value=f"<@{g['host_id']}>", inline=True)
    e.add_field(name="👥 Entries", value=f"**{len(g['participants'])}** Users", inline=True)
    
    reqs = []
    if g.get("role_id"): 
        reqs.append(f"• Role: <@&{g['role_id']}>")
    if g.get("min_msgs"): 
        reqs.append(f"• Msgs: **{g['min_msgs']}**+")
    if g.get("min_balance"): 
        reqs.append(f"• Aura: **{g['min_balance']}**+")
        
    if reqs: 
        e.add_field(name="🔒 Requirements", value="\n".join(reqs), inline=False)
        
    e.set_image(url=GIVEAWAY_BANNER_URL)
    e.set_footer(text=f"🏆 {g['winners']} Winner(s)")
    return e

class GiveawayView(discord.ui.View):
    def __init__(self, gid: str):
        super().__init__(timeout=None)
        self.gid = gid
        
        join_btn = discord.ui.Button(label="Enter Giveaway", style=discord.ButtonStyle.success, emoji="🎉", custom_id=f"join_gw_{gid}")
        join_btn.callback = self.join
        self.add_item(join_btn)
        
        view_btn = discord.ui.Button(label="View Entries", style=discord.ButtonStyle.secondary, emoji="👀", custom_id=f"view_gw_{gid}")
        view_btn.callback = self.view_entries
        self.add_item(view_btn)

    async def join(self, i: discord.Interaction):
        g = giveaways.get(self.gid)
        
        if not g or g.get("ended"): 
            return await i.response.send_message("Giveaway ended.", ephemeral=True)
            
        u = i.user
        if g.get("role_id") and not any(r.id == g["role_id"] for r in u.roles): 
            return await i.response.send_message("Missing role requirement.", ephemeral=True)
            
        if g.get("min_msgs") and message_count[u.id] < g["min_msgs"]: 
            return await i.response.send_message(f"Need {g['min_msgs']} msgs.", ephemeral=True)
            
        if g.get("min_balance") and balance[u.id] < g["min_balance"]: 
            return await i.response.send_message(f"Need {g['min_balance']} Aura.", ephemeral=True)
            
        if u.id in g["participants"]: 
            return await i.response.send_message("Already entered!", ephemeral=True)
        
        g["participants"].append(u.id)
        save_data()
        
        await i.message.edit(embed=build_giveaway_embed(g, i.guild))
        await i.response.send_message(f"{E_SUCCESS} Entry confirmed!", ephemeral=True)

    async def view_entries(self, i: discord.Interaction):
        p = giveaways.get(self.gid, {}).get("participants", [])
        if not p:
            return await i.response.send_message("No entries yet!", ephemeral=True)

        mentions = [f"<@{uid}>" for uid in p]
        chunk_size = 40
        chunks = [mentions[x:x+chunk_size] for x in range(0, len(mentions), chunk_size)]

        embeds = []
        for idx, chunk in enumerate(chunks):
            title = f"👥 All Entries ({len(p)} total)" if idx == 0 else f"👥 Entries (cont. {idx+1})"
            embeds.append(discord.Embed(title=title, description="\n".join(chunk), color=discord.Color.blue()))

        await i.response.send_message(embeds=embeds[:10], ephemeral=True)


class MyBot(commands.Bot):
    def __init__(self): 
        super().__init__(command_prefix="!", intents=discord.Intents.all(), help_command=None)
        
    async def setup_hook(self):
        for gid, g in giveaways.items():
            if not g.get("ended"): 
                self.add_view(GiveawayView(gid))
                
        for pid in polls.keys(): 
            self.add_view(PollView(pid))
            
        self.add_view(BirthdayPanelView())
        self.add_view(ConfessionView())
        
        for mid, pdata in pending_payouts.items():
            self.add_view(PayoutView(pdata["uid"], pdata["amt"], pdata["method"], pdata["details"], mid))
            
    
        
        await self.tree.sync()

        midnight_birthday_check.start()
        check_birthday_roles.start()
        autokick_check.start()
        market_fluctuation.start()      
        daily_puzzle_scheduler.start()
        science_fact_dropper.start()
        reminder_checker.start()
        daily_hot_take.start()
        server_mood_tracker.start()
        weekly_recap.start()
        weekly_recap_task.start()

bot = MyBot()
last_chatter_id = None
last_user_message = {}
PUZZLES = [
    {"type": "riddle", "q": "I speak without a mouth and hear without ears. I have no body, but I come alive with the wind. What am I?", "a": "echo"},
    {"type": "riddle", "q": "The more you take, the more you leave behind. What am I?", "a": "footsteps"},
    {"type": "riddle", "q": "I have cities but no houses, mountains but no trees, water but no fish. What am I?", "a": "map"},
    {"type": "riddle", "q": "What has hands but can't clap?", "a": "clock"},
    {"type": "riddle", "q": "What gets wetter the more it dries?", "a": "towel"},
    {"type": "riddle", "q": "I have keys but no locks, space but no room. You can enter but can't go inside. What am I?", "a": "keyboard"},
    {"type": "riddle", "q": "What can run but never walks, has a mouth but never talks, has a bed but never sleeps?", "a": "river"},
    {"type": "riddle", "q": "The more you have of it, the less you see. What is it?", "a": "darkness"},
    {"type": "riddle", "q": "What has one eye but can't see?", "a": "needle"},
    {"type": "riddle", "q": "Light as a feather, but even the strongest can't hold it for more than a few minutes. What am I?", "a": "breath"},
    {"type": "riddle", "q": "I have no life but I can die. What am I?", "a": "battery"},
    {"type": "riddle", "q": "The more you remove from me, the bigger I get. What am I?", "a": "hole"},
    {"type": "riddle", "q": "I go up but never come down. What am I?", "a": "age"},
    {"type": "riddle", "q": "What has 13 hearts but no other organs?", "a": "deck of cards"},
    {"type": "riddle", "q": "Always in front of you but can never be seen. What am I?", "a": "future"},
    {"type": "riddle", "q": "What can you catch but not throw?", "a": "cold"},
    {"type": "riddle", "q": "I have a tail and a head but no body. What am I?", "a": "coin"},
    {"type": "riddle", "q": "What invention lets you look right through a wall?", "a": "window"},
    {"type": "riddle", "q": "Maker doesn't need it, buyer doesn't use it, user doesn't know it. What is it?", "a": "coffin"},
    {"type": "riddle", "q": "What has many teeth but can't bite?", "a": "comb"},
    {"type": "riddle", "q": "I have branches but no fruit, trunk, or leaves. What am I?", "a": "bank"},
    {"type": "riddle", "q": "Full of holes but still holds water. What am I?", "a": "sponge"},
    {"type": "riddle", "q": "What 5-letter word becomes shorter when you add 2 letters to it?", "a": "short"},
    {"type": "riddle", "q": "I shrink every time you use me. What am I?", "a": "soap"},
    {"type": "riddle", "q": "What has words but never speaks?", "a": "book"},
    {"type": "riddle", "q": "I can fly without wings, cry without eyes. Wherever I go darkness follows. What am I?", "a": "cloud"},
    {"type": "riddle", "q": "What runs around the whole yard without moving?", "a": "fence"},
    {"type": "riddle", "q": "I am not alive but I grow. I have no lungs but I need air. What am I?", "a": "fire"},
    {"type": "riddle", "q": "What begins with T, ends with T, and has T in it?", "a": "teapot"},
    {"type": "riddle", "q": "I have a head, a tail, but no body. I'm not alive but I help things run. What am I?", "a": "coin"},
    {"type": "riddle", "q": "The more you feed me the bigger I grow, but water kills me. What am I?", "a": "fire"},
    {"type": "riddle", "q": "I have cities, but no houses live there. What am I?", "a": "map"},
    {"type": "riddle", "q": "What can fill a room but takes up no space?", "a": "light"},
    {"type": "riddle", "q": "I am always hungry and must always be fed. The finger I touch will soon turn red. What am I?", "a": "fire"},
    {"type": "riddle", "q": "What has a bottom at the top?", "a": "legs"},

    {"type": "scramble", "q": "OSDIC", "a": "disco"},
    {"type": "scramble", "q": "AKNB", "a": "bank"},
    {"type": "scramble", "q": "ROFEST", "a": "forest"},
    {"type": "scramble", "q": "TNPALE", "a": "planet"},
    {"type": "scramble", "q": "ATREW", "a": "water"},
    {"type": "scramble", "q": "RTEIG", "a": "tiger"},
    {"type": "scramble", "q": "CAKBLROD", "a": "blockard"},
    {"type": "scramble", "q": "SUMIN", "a": "minus"},
    {"type": "scramble", "q": "ELPPAS", "a": "apples"},
    {"type": "scramble", "q": "NBTUTO", "a": "button"},
    {"type": "scramble", "q": "MREBO", "a": "brome"},
    {"type": "scramble", "q": "LTADIE", "a": "detail"},
    {"type": "scramble", "q": "SNKAE", "a": "snake"},
    {"type": "scramble", "q": "ARCAME", "a": "camera"},
    {"type": "scramble", "q": "GLEJUG", "a": "juggle"},
    {"type": "scramble", "q": "OECLHCOTA", "a": "chocolate"},
    {"type": "scramble", "q": "IUTRF", "a": "fruit"},
    {"type": "scramble", "q": "ESTNP", "a": "spent"},
    {"type": "scramble", "q": "LAPITCA", "a": "capital"},
    {"type": "scramble", "q": "RNBAI", "a": "brain"},
    {"type": "scramble", "q": "HDAMON", "a": "mohand"},
    {"type": "scramble", "q": "PLSEE", "a": "sleep"},
    {"type": "scramble", "q": "IEPSR", "a": "spire"},
    {"type": "scramble", "q": "TTBURE", "a": "butter"},
    {"type": "scramble", "q": "LPCNIE", "a": "pencil"},
    {"type": "scramble", "q": "SOHRE", "a": "horse"},
    {"type": "scramble", "q": "NOOMS", "a": "moons"},
    {"type": "scramble", "q": "DOLCU", "a": "cloud"},
    {"type": "scramble", "q": "SHBRU", "a": "brush"},
    {"type": "scramble", "q": "AOCEN", "a": "ocean"},

    {"type": "math", "q": "What is 17 × 6?", "a": "102"},
    {"type": "math", "q": "What is 144 ÷ 12?", "a": "12"},
    {"type": "math", "q": "What is 25² (25 squared)?", "a": "625"},
    {"type": "math", "q": "What is 15% of 200?", "a": "30"},
    {"type": "math", "q": "What is 8! (8 factorial)?", "a": "40320"},
    {"type": "math", "q": "What is √196?", "a": "14"},
    {"type": "math", "q": "A train travels 60km/h. How far does it go in 2.5 hours?", "a": "150"},
    {"type": "math", "q": "What is 2 to the power of 10?", "a": "1024"},
    {"type": "math", "q": "What is 33% of 300?", "a": "99"},
    {"type": "math", "q": "If you have 5 dozen eggs, how many eggs do you have?", "a": "60"},
    {"type": "math", "q": "What is 999 + 111?", "a": "1110"},
    {"type": "math", "q": "What is 1000 − 337?", "a": "663"},
    {"type": "math", "q": "What is 13 × 13?", "a": "169"},
    {"type": "math", "q": "What is √81?", "a": "9"},
    {"type": "math", "q": "What is 7 × 8 × 2?", "a": "112"},
    {"type": "math", "q": "What is 20% of 450?", "a": "90"},
    {"type": "math", "q": "What is 56 ÷ 7 + 18?", "a": "26"},
    {"type": "math", "q": "What is 3³ (3 cubed)?", "a": "27"},
    {"type": "math", "q": "If a pizza has 8 slices and you eat 3, what percentage did you eat? (round to nearest whole)", "a": "38"},
    {"type": "math", "q": "What is 500 × 0.25?", "a": "125"},

    {"type": "emoji", "q": "🦇🧛 = ? (movie)", "a": "batman"},
    {"type": "emoji", "q": "🧊🍦 = ?", "a": "ice cream"},
    {"type": "emoji", "q": "🏠🕷️ = ? (movie)", "a": "home alone"},
    {"type": "emoji", "q": "🐠🔍 = ? (movie)", "a": "finding nemo"},
    {"type": "emoji", "q": "🤖🚗 = ? (movie)", "a": "transformers"},
    {"type": "emoji", "q": "🧊❄️👸 = ? (movie)", "a": "frozen"},
    {"type": "emoji", "q": "🌪️🏠🐕 = ? (movie)", "a": "wizard of oz"},
    {"type": "emoji", "q": "💣⏱️🚌 = ? (movie)", "a": "speed"},
    {"type": "emoji", "q": "🧙📚⚡ = ? (character)", "a": "harry potter"},
    {"type": "emoji", "q": "🦸🏿⚡🌩️ = ? (superhero)", "a": "black adam"},
    {"type": "emoji", "q": "🐝🎬 = ? (movie)", "a": "bee movie"},
    {"type": "emoji", "q": "🚂⏰ = ? (movie)", "a": "polar express"},
    {"type": "emoji", "q": "🧟🧠 = ?", "a": "zombie"},
    {"type": "emoji", "q": "🌙🐺 = ?", "a": "werewolf"},
    {"type": "emoji", "q": "👻🏠 = ?", "a": "haunted house"},
    {"type": "emoji", "q": "🎸🔥 = ? (song)", "a": "fire"},
    {"type": "emoji", "q": "💃🌹 = ? (dance)", "a": "tango"},
    {"type": "emoji", "q": "🎤🎶🌧️ = ? (song)", "a": "singing in the rain"},
    {"type": "emoji", "q": "🌞😎 = ?", "a": "sunshine"},
    {"type": "emoji", "q": "🐸☕ = ? (meme)", "a": "but thats none of my business"},
    {"type": "emoji", "q": "🦊🌾 = ? (app)", "a": "firefox"},
    {"type": "emoji", "q": "🍎⌚ = ? (product)", "a": "apple watch"},
    {"type": "emoji", "q": "🐦🔵 = ? (app)", "a": "twitter"},
    {"type": "emoji", "q": "📸👻 = ? (app)", "a": "snapchat"},
    {"type": "emoji", "q": "🎵🔗 = ? (app)", "a": "soundcloud"},

    {"type": "emoji", "q": "🌊🏄 = ?", "a": "surfing"},
    {"type": "emoji", "q": "🍎📱 = ? (brand)", "a": "apple"},
    {"type": "emoji", "q": "🦁👑 = ? (movie)", "a": "lion king"},
    {"type": "emoji", "q": "🕷️👨 = ? (superhero)", "a": "spiderman"},
    {"type": "emoji", "q": "🧊❄️🏔️ = ? (one word)", "a": "frozen"},
    {"type": "emoji", "q": "🌹🌹🌹 = ? (song by 21 Savage)", "a": "roses"},
    {"type": "emoji", "q": "🔫🌹 = ? (band)", "a": "guns n roses"},
    {"type": "emoji", "q": "🐍🎵 = ? (artist)", "a": "taylor swift"},
    {"type": "emoji", "q": "👁️🍬👁️ = ?", "a": "eye candy"},
    {"type": "emoji", "q": "🧠🌩️ = ?", "a": "brainstorm"},
    {"type": "emoji", "q": "🌙🚶 = ? (Michael Jackson move)", "a": "moonwalk"},
    {"type": "emoji", "q": "🐜🏃 = ?", "a": "antman"},
    {"type": "emoji", "q": "🔑🏠 = ?", "a": "lockdown"},
    {"type": "emoji", "q": "🐝🏠 = ?", "a": "beehive"},
    {"type": "emoji", "q": "🌊📏 = ?", "a": "sea level"},
    {"type": "emoji", "q": "🚗🎥 = ?", "a": "drive in"},
    {"type": "emoji", "q": "🍋🎤 = ? (Beyonce album)", "a": "lemonade"},
    {"type": "emoji", "q": "🌴🏝️🍹 = ?", "a": "tropical"},
    {"type": "emoji", "q": "🎭😂 = ?", "a": "comedy"},
    {"type": "emoji", "q": "💀🏴‍☠️⚓ = ?", "a": "pirate"},

    {"type": "fillblank", "q": "The early bird catches the ___.", "a": "worm"},
    {"type": "fillblank", "q": "Actions speak louder than ___.", "a": "words"},
    {"type": "fillblank", "q": "Every cloud has a silver ___.", "a": "lining"},
    {"type": "fillblank", "q": "Don't judge a book by its ___.", "a": "cover"},
    {"type": "fillblank", "q": "The pen is mightier than the ___.", "a": "sword"},
    {"type": "fillblank", "q": "All that glitters is not ___.", "a": "gold"},
    {"type": "fillblank", "q": "Better late than ___.", "a": "never"},
    {"type": "fillblank", "q": "A penny saved is a penny ___.", "a": "earned"},
    {"type": "fillblank", "q": "Two wrongs don't make a ___.", "a": "right"},
    {"type": "fillblank", "q": "When in Rome, do as the ___ do.", "a": "romans"},
    {"type": "fillblank", "q": "The grass is always greener on the other ___.", "a": "side"},
    {"type": "fillblank", "q": "You can't make an omelette without breaking ___.", "a": "eggs"},
    {"type": "fillblank", "q": "Time ___ all wounds.", "a": "heals"},
    {"type": "fillblank", "q": "A stitch in time saves ___.", "a": "nine"},
    {"type": "fillblank", "q": "Curiosity killed the ___.", "a": "cat"},
    {"type": "fillblank", "q": "Birds of a feather flock ___.", "a": "together"},
    {"type": "fillblank", "q": "The ___ is always right. (customer service saying)", "a": "customer"},
    {"type": "fillblank", "q": "Rome wasn't built in a ___.", "a": "day"},
    {"type": "fillblank", "q": "Let sleeping dogs ___.", "a": "lie"},
    {"type": "fillblank", "q": "Barking up the wrong ___.", "a": "tree"},
]

active_puzzle = {"question": None, "answer": None, "solved": False}
puzzles_sent_today = data.get("puzzles_sent_today", 0)
puzzle_date = data.get("puzzle_date", "")
last_puzzle_time = 0
puzzle_slots = {"midnight": False, "afternoon": False, "random": False}
puzzle_slots_date = ""
midday_flip_done = False
midday_flip_date = ""
insider_uses_today = defaultdict(int)
insider_uses_date = ""
used_puzzles = data.get("used_puzzles", [])
pending_payouts = data.get("pending_payouts", {})
midday_flip_done = False
midday_flip_date = ""
insider_uses_today = defaultdict(int)
insider_uses_date = ""
daily_sell_earnings = defaultdict(int, {int(k): v for k, v in data.get("daily_sell_earnings", {}).items()})
sell_earnings_date = data.get("sell_earnings_date", "")
personality_season = data.get("personality_season", 0)



@bot.event
async def on_ready():
    logging.info(f"Bot online: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="/help | Collecting Aura"))
    yo_bag.load(data.get("yo_bag", []))
    roast_bag.load(data.get("roast_bag", []))

    trimmed = 0
    for uid in portfolios:
        for coin in portfolios[uid]:
            held = portfolios[uid][coin].get("shares", 0)
            if held > MAX_SHARES_PER_COIN:
                invested = portfolios[uid][coin].get("invested", 0.0)
                ratio = MAX_SHARES_PER_COIN / held
                kept_invested = max(0.0, invested * ratio)
                refund = int(invested - kept_invested)
                portfolios[uid][coin]["shares"] = MAX_SHARES_PER_COIN
                portfolios[uid][coin]["invested"] = kept_invested
                balance[uid] += refund
                trimmed += 1
    if trimmed:
        save_data()
        logging.info(f"Trimmed {trimmed} portfolio entries to MAX_SHARES_PER_COIN={MAX_SHARES_PER_COIN} on startup, refunds issued")

    for guild in bot.guilds:
        try:
            cached_invites[guild.id] = {inv.code: inv.uses for inv in await guild.invites()}
        except Exception:
            pass

    READ_CATEGORIES = {"important", "start here", "lounge", "reddit tasks", "extras"}
    global server_channel_knowledge, server_custom_emojis
    server_channel_knowledge = {}
    for guild in bot.guilds:
        emoji_list = [f"<{'a' if e.animated else ''}:{e.name}:{e.id}>" for e in guild.emojis]
        if emoji_list:
            server_custom_emojis = "Available server emojis: " + " ".join(emoji_list[:30])
        break
    READ_CATEGORY_IDS = {1448753211245858826, 1448806198953644063, 1448714204964982845, 1448750517798043770, 1449052357340954674}
    for guild in bot.guilds:
        for channel in guild.text_channels:
            cat_id = channel.category.id if channel.category else None
            if cat_id in READ_CATEGORY_IDS:
                try:
                    messages = []
                    async for msg in channel.history(limit=50, oldest_first=True):
                        if msg.content:
                            messages.append(msg.content[:500])
                        for embed in msg.embeds:
                            parts = []
                            if embed.title: parts.append(embed.title)
                            if embed.description: parts.append(embed.description[:500])
                            for field in embed.fields:
                                parts.append(f"{field.name}: {field.value}")
                            if parts:
                                messages.append(" | ".join(parts))
                    if messages:
                        server_channel_knowledge[channel.name] = "\n".join(messages)
                        logging.info(f"Read #{channel.name} ({len(messages)} entries)")
                except Exception as e:
                    logging.warning(f"Skipped #{channel.name}: {e}")
    
    for gid, g in list(giveaways.items()):
        if not g.get("ended"): 
            bot.loop.create_task(schedule_end(gid, max(0, g["end_time"] - time.time())))


@bot.event
async def on_member_join(member: discord.Member):
    global invite_event_active
    if not invite_event_active:
        return
    guild = member.guild
    try:
        new_invites = {inv.code: inv for inv in await guild.invites()}
        old_invites = cached_invites.get(guild.id, {})
        logging.info(f"Member join: {member.display_name} | Old cache size: {len(old_invites)} | New invites size: {len(new_invites)}")
        inviter_id = None
        for code, inv_obj in new_invites.items():
            old_uses = old_invites.get(code, 0)
            if isinstance(old_uses, int):
                old_use_count = old_uses
            else:
                old_use_count = old_uses.uses if hasattr(old_uses, 'uses') else 0
            if inv_obj.uses > old_use_count:
                if inv_obj.inviter:
                    inviter_id = inv_obj.inviter.id
                break
        cached_invites[guild.id] = {code: inv.uses for code, inv in new_invites.items()}
        if inviter_id and inviter_id != member.id:
            invite_counts[inviter_id] += 1
            invite_map[str(member.id)] = inviter_id
            save_data()
            logging.info(f"Invite tracked: {member.display_name} invited by {inviter_id}, total: {invite_counts[inviter_id]}")
        else:
            logging.info(f"Invite NOT tracked for {member.display_name} — inviter not found")
    except Exception as e:
        logging.error(f"on_member_join invite tracking error: {e}")

@bot.event
async def on_member_remove(member: discord.Member):
    global invite_event_active
    if not invite_event_active:
        return
    guild = member.guild
    try:
        cached_invites[guild.id] = {inv.code: inv.uses for inv in await guild.invites()}
    except Exception:
        pass
    inviter_id = invite_map.pop(str(member.id), None)
    if inviter_id:
        invite_counts[inviter_id] = max(0, invite_counts[inviter_id] - 1)
        save_data()


PAYMENT_TICKET_CATEGORY_ID = 1448805721071292661

@bot.event
async def on_guild_channel_create(channel):
    if not isinstance(channel, discord.TextChannel):
        return
    if not channel.category or channel.category.id != PAYMENT_TICKET_CATEGORY_ID:
        return
    await asyncio.sleep(1)
    opener = None
    for target, overwrite in channel.overwrites.items():
        if isinstance(target, discord.Member) and not target.bot:
            if overwrite.read_messages:
                opener = target
                break
    if opener:
        new_name = f"payment-{opener.display_name[:80].lower().replace(' ', '-')}"
        try:
            await channel.edit(name=new_name)
            logging.info(f"Renamed payment ticket to {new_name}")
        except Exception as e:
            logging.error(f"Could not rename ticket: {e}")

@bot.event
async def on_message(m: discord.Message):
    if m.author.bot: 
        return

    OWNER_ID = 992008865656868946
    text_raw = m.content.strip()

    if m.author.id == OWNER_ID and m.reference and m.reference.message_id in pending_aura_requests:
        req = pending_aura_requests[m.reference.message_id]
        if text_raw.lower() == "yes":
            pending_aura_requests[m.reference.message_id]["approved"] = True
            await m.channel.send(f"<@{OWNER_ID}> How much Aura do you want to give {req['requester'].mention}?")
        elif text_raw.lower() == "no":
            del pending_aura_requests[m.reference.message_id]
            await m.channel.send(f"{req['requester'].mention} Request denied! 😔")
        return

    if m.author.id == OWNER_ID and text_raw.isdigit():
        active = [(mid, req) for mid, req in pending_aura_requests.items() if req.get("approved") and req["channel_id"] == m.channel.id]
        if active:
            mid, req = active[0]
            amount = int(text_raw)
            uid = req["requester"].id
            balance[uid] += amount
            save_data()
            del pending_aura_requests[mid]
            await m.channel.send(f"✅ {req['requester'].mention} has been given **{amount:,} Aura**! New balance: **{balance[uid]:,} Aura**")
            return


        
    if not m.author.bot and m.content and not m.content.startswith('/'):
        if not (hasattr(m.channel, 'category') and m.channel.category and m.channel.category.name == "Staff Area"):
            if m.channel.id not in channel_chat_log:
                channel_chat_log[m.channel.id] = deque(maxlen=100)
            channel_chat_log[m.channel.id].append(f"{m.author.display_name}: {m.content[:200]}")

    global last_chatter_id
    text = m.content.lower().strip()
    
    _yo_triggers = {"yo", "yoo", "yooo", "hi", "hello", "wsg", "wassup", "konnichiwa", "konnichiha", "hola", "bonjour", "salut", "ciao", "hallo", "namaste", "salam", "merhaba", "oi", "ola", "hei", "hej", "привет", "안녕", "こんにちは"}
    _gm_triggers = {"gm", "good morning", "good mrng", "gmorning", "subah", "subh", "subha", "good mng"}
    _gn_triggers = {"gn", "good night", "good nite", "goodnight", "raat", "sone ja", "so ja", "sojaon"}
    if text in _gm_triggers:
        reply = await quick_ai(f"{m.author.display_name} said good morning in the server. Reply with a chill personalized good morning. Match language. 1 sentence.", max_tokens=150)
        await m.channel.send(reply if reply else f"Good morning {m.author.mention} 👋")
    elif text in _gn_triggers:
        reply = await quick_ai(f"{m.author.display_name} said good night in the server. Reply with a chill good night message. Match language. 1 sentence.", max_tokens=150)
        await m.channel.send(reply if reply else f"Good night {m.author.mention} 🌙")
    elif text in _yo_triggers:
        yo_reply = await quick_ai(f"{m.author.display_name} just said '{m.content}' in the server chat. Give a short, fun greeting back. Match their language. Max 1 sentence.", max_tokens=160)
        await m.channel.send(yo_reply if yo_reply else yo_bag.get_next())

    if bot.user in m.mentions:
        question = m.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        import re
        text_only = re.sub(r'<a?:[\w]+:[\d]+>', '', question).strip()
        text_only = re.sub('[\U0001F000-\U0001FFFF\U00002000-\U00003300]', '', text_only).strip()
        if not text_only:
            return

        if m.reference:
            try:
                ref_msg = m.reference.cached_message or await m.channel.fetch_message(m.reference.message_id)
                if ref_msg.author.id == bot.user.id and (ref_msg.embeds or ref_msg.components):
                    return  # Never reply to slash command responses
            except Exception:
                pass

        if not question:
            question = "kuch toh bol"

        OWNER_ID = 992008865656868946
        intent_prompt = f"""The user said: "{question}"
Is the user directly asking YOU (the bot) to give them Aura/money/currency as a request? 
Reply with only "YES" if they are genuinely requesting Aura from you, or "NO" if they are just talking about Aura, asking a question about it, or anything else.
Only reply YES if it's a clear direct request like "give me aura", "can I have some aura", "mujhe aura chahiye" etc."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    GROQ_URL,
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": intent_prompt}],
                        "max_tokens": 5,
                        "temperature": 0
                    },
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY or GROQ_API_KEY}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    intent = data["choices"][0]["message"]["content"].strip().upper()
                    is_aura_request = intent.startswith("YES")
        except Exception:
            is_aura_request = False

        if is_aura_request:
            ask_msg = await m.channel.send(f"<@{OWNER_ID}> {m.author.mention} is asking for Aura — \"{question}\"\nYes or no?")
            pending_aura_requests[ask_msg.id] = {"requester": m.author, "channel_id": m.channel.id}
            return

        reminder_set = await _try_set_reminder(m.author.id, m.channel.id, question)
        if reminder_set:
            await m.reply(reminder_set)
            return

        async with m.channel.typing():
            avatar = str(m.author.display_avatar.url) if m.author.display_avatar else None
            reply = await ask_ai(question, m.author.display_name, m.author.id, m.channel.id, member=m.author, avatar_url=avatar)
        if reply:
            import re as _re
            reply = _re.sub(r'(?<![<a]):[a-zA-Z0-9_]+:', '', reply)
            reply = _re.sub(r'<[A-Z]:[a-zA-Z0-9_]+:\d+>', '', reply)
            reply = reply.strip()
            if reply:
                await m.reply(reply)
                asyncio.create_task(_extract_memory(m.author.id, m.author.display_name, question, reply))
        return
    if any(w in text for w in BAD_WORDS):
        try: 
            await m.delete()
        except: 
            pass
        return await m.channel.send(f"{m.author.mention}, watch your language. {E_WARN}", delete_after=5)

    if m.channel.id in (CHAT_CHANNEL_ID, CHAT_CHANNEL_ID_2):
        uid = m.author.id
        if active_puzzle["question"] and not active_puzzle["solved"]:
            user_ans = text.strip().lower()
            correct_ans = active_puzzle["answer"].lower()
            if user_ans == correct_ans or user_ans.replace(" ", "") == correct_ans.replace(" ", ""):
                active_puzzle["solved"] = True
                old_b = balance[uid]
                balance[uid] += 50
                weekly_aura_earned[uid] += 50
                asyncio.create_task(check_balance_milestone(uid, old_b, balance[uid]))
                save_data()
                ptype = active_puzzle.get("type", "riddle")
                type_labels = {"riddle": "🧩 Riddle", "scramble": "🔀 Word Scramble", "math": "🔢 Math", "trivia": "🎯 Trivia", "emoji": "🎭 Emoji", "fillblank": "✏️ Fill in the Blank"}
                label = type_labels.get(ptype, "🧩 Puzzle")
                hype = await quick_ai(f"Someone named {m.author.display_name} just solved a {ptype} puzzle in a Discord server and won 50 Aura! Write a short hype message congratulating them. Be fun, 1 sentence max.", max_tokens=160)
                hype_msg = hype if hype else f"**{label} SOLVED!** 🎉"
                await m.channel.send(f"{hype_msg} {m.author.mention} wins **50 Aura**!\n> ✅ Answer: **{active_puzzle['answer'].title()}**")

        found_hard = next((egg for egg in hard_eggs if egg in text), None)
        found_easy = next((egg for egg in easy_eggs if egg in text), None)
        
        if found_hard and found_hard not in claimed_easter_eggs:
            claimed_easter_eggs.append(found_hard)
            hard_eggs.remove(found_hard)
            balance[uid] += 500
            save_data()
            await m.channel.send(f"🏴‍☠️ **TREASURE FOUND!** {m.author.mention} found a hidden easter egg (`{found_hard}`) and claimed **500 Aura**! 💰")
            
        elif found_easy and found_easy not in claimed_easter_eggs:
            claimed_easter_eggs.append(found_easy)
            easy_eggs.remove(found_easy)
            balance[uid] += 100
            save_data()
            await m.channel.send(f"🐣 **MINI EGG FOUND!** {m.author.mention} found an easy easter egg (`{found_easy}`) and claimed **100 Aura**! 🪙")

        if len(text) >= 2 and last_chatter_id != uid and last_user_message.get(uid) != text:
            last_chatter_id = uid
            last_user_message[uid] = text
            message_count[uid] += 1
            
            if message_count[uid] % msg_threshold == 0:
                old_b = balance[uid]
                balance[uid] += msg_reward
                asyncio.create_task(check_balance_milestone(uid, old_b, balance[uid]))
            bonus = evaluate_message(text)
            if bonus != 0:
                balance[uid] += bonus

            if message_count[uid] % 10 == 0:
                save_data()
            
    await bot.process_commands(m)



@tasks.loop(hours=1)
async def server_mood_tracker():
    global last_mood_check
    now = datetime.datetime.now(IST)
    if not (18 <= now.hour < 21):
        return
    today = now.date().isoformat()
    if last_mood_check == today:
        return
    if random.random() > 0.3:
        return
    last_mood_check = today
    ch = bot.get_channel(CHAT_CHANNEL_ID)
    if not ch:
        return
    all_msgs = []
    for cid, log in channel_chat_log.items():
        c = bot.get_channel(cid)
        if c and (not c.category or c.category.name != "Staff Area"):
            all_msgs.extend(list(log)[-10:])
    if len(all_msgs) < 5:
        return
    sample = "\n".join(all_msgs[-30:])
    mood = await quick_ai(
        f"Based on these recent Discord server messages, describe the server vibe/mood in one punchy sentence. Use emojis. Be fun and accurate.\n\nMessages:\n{sample}",
        max_tokens=160
    )
    if mood:
        await ch.send(f"📡 **Server Mood Check:** {mood}")

@tasks.loop(hours=1)
async def weekly_recap():
    now = datetime.datetime.now(IST)
    if now.weekday() != 6 or now.hour != 21:
        return
    ch = bot.get_channel(CHAT_CHANNEL_ID)
    if not ch:
        return

    top_uid = max(balance, key=lambda u: balance[u]) if balance else None
    top_name = "unknown"
    if top_uid:
        m = ch.guild.get_member(top_uid) if ch.guild else None
        top_name = m.display_name if m else f"<@{top_uid}>"

    best_coin = max(stocks, key=lambda c: stocks[c]) if stocks else "unknown"
    worst_coin = min(stocks, key=lambda c: stocks[c]) if stocks else "unknown"

    top_loser_uid = max(casino_losses, key=lambda u: casino_losses[u]) if casino_losses else None
    loser_name = "nobody"
    if top_loser_uid:
        m = ch.guild.get_member(top_loser_uid) if ch.guild else None
        loser_name = m.display_name if m else f"<@{top_loser_uid}>"
        loser_amt = casino_losses[top_loser_uid]
    else:
        loser_amt = 0

    recap = await quick_ai(
        f"Write a fun weekly server recap for a Discord economy server. "
        f"Top earner: {top_name} with {balance.get(top_uid, 0):,} Aura. "
        f"Hottest stock: {best_coin} at {stocks.get(best_coin, 0):.1f} Aura. "
        f"Worst stock: {worst_coin} at {stocks.get(worst_coin, 0):.1f} Aura. "
        f"Biggest casino loser: {loser_name} lost {loser_amt:,} Aura. "
        f"Be funny, hype, and sarcastic. Max 4 sentences.",
        max_tokens=200
    )
    if recap:
        embed = discord.Embed(
            title="📊 Weekly Server Recap",
            description=recap,
            color=discord.Color.blurple()
        )
        embed.set_footer(text="See you next week! Keep earning 💪")
        await ch.send(embed=embed)
    casino_losses.clear()
    casino_wins.clear()
    save_data()


@tasks.loop(minutes=5)
async def market_fluctuation():
    global midday_flip_done, midday_flip_date, personality_season

    now_ist = datetime.datetime.now(IST)
    current_day = now_ist.date().toordinal()
    today_str = now_ist.date().isoformat()
    current_hour = now_ist.hour

    if midday_flip_date != today_str:
        midday_flip_date = today_str
        midday_flip_done = False

    if not midday_flip_done and 12 <= current_hour < 16:
        if random.random() < 0.15:  # ~15% chance per tick in this window
            personality_season += 1
            midday_flip_done = True
            save_data()
            logging.info(f"Mid-day personality flip triggered (season={personality_season})")

    random.seed(current_day + personality_season)
    personalities = ["stable", "rugpull", "volatile", "stable", "steady_up", "steady_down", "wildcard"]
    
    if random.random() < 0.15:
        personalities[0] = "moon"
        
    random.shuffle(personalities)
    coin_personalities = {c: p for c, p in zip(stocks.keys(), personalities)}
    random.seed()

    for coin in stocks:
        p = coin_personalities[coin]

        noise = random.uniform(-0.005, 0.005)

        if p == "moon":
            change = random.uniform(-0.02 + noise, 0.015 + noise) 
        elif p == "rugpull":
            change = random.uniform(-0.10 + noise, 0.01 + noise)
        elif p == "volatile":
            change = random.uniform(-0.05 + noise, 0.05 + noise)
        elif p == "stable":
            change = random.uniform(-0.005 + noise, 0.005 + noise)
        elif p == "steady_up":
            change = random.uniform(-0.005 + noise, 0.015 + noise)
        elif p == "steady_down":
            change = random.uniform(-0.015 + noise, 0.005 + noise)
        else:
            if random.random() < 0.01:
                change = random.choice([-0.3, 0.15])
            else:
                change = random.uniform(-0.02 + noise, 0.02 + noise)

        if random.random() < 0.008:
            shock = random.choice([-0.20, -0.15, 0.11, 0.12, 0.08])
            change += shock
            logging.info(f"Shock event on {coin}: {shock:+.0%}")
            if random.random() < 0.10:  # 10% chance to comment
                asyncio.create_task(_shock_comment(coin, shock))

        if coin in delisted_coins:
            continue

        if stocks[coin] > 350:
            if random.random() < 0.15: 
                change = random.uniform(-0.35, -0.60)
                logging.info(f"BUBBLE BURST on {coin}! Crashed by {change:+.0%}")

        if stocks[coin] > 400:
            if change > 0:
                change *= 0.25 # Cuts upward momentum
            elif change < 0:
                change *= 1.50 # Accelerates drops

        new_price = min(500.0, max(0.0, stocks[coin] * (1 + change)))
        if 0 < new_price < 1.0:
            new_price = 0.0  # snap to 0 to trigger delist cleanly

        if coin in force_market_targets:
            target = force_market_targets[coin]
            diff = target - new_price
            nudge = diff * 0.15
            new_price = min(500.0, max(0.0, new_price + nudge))
            if 0 < new_price < 1.0:
                new_price = 0.0
            if abs(new_price - target) < 2:
                del force_market_targets[coin]
                logging.info(f"force_market target reached for {coin}")

        stocks[coin] = new_price

        if stocks[coin] <= 0:
            stocks[coin] = 0.0
            wiped = []
            for uid in list(portfolios.keys()):
                if coin in portfolios[uid] and portfolios[uid][coin].get("shares", 0) > 0:
                    wiped.append(uid)
                    invested = portfolios[uid][coin].get("invested", 0.0)
                    payout = max(1, int(invested * 0.10))
                    balance[uid] += payout
                    portfolios[uid][coin] = {"shares": 0, "invested": 0.0}
            import time as _time
            relist_delay = random.randint(2, 4) * 3600  # 2-4 hours in seconds
            delisted_coins[coin] = _time.time() + relist_delay
            stock_history[coin] = []
            save_data()
            ch = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)
            if ch:
                embed = discord.Embed(
                    title="💀 COIN DELISTED",
                    description=await quick_ai(f"Write a dramatic breaking news style announcement: the crypto coin {coin} just crashed to 0 and got delisted! {len(wiped)} holders lost their shares. They got 10% back as liquidation. It will relist in {relist_delay // 3600} hours. Keep it fun and dramatic. Max 3 sentences.", max_tokens=120) or f"**{coin}** has crashed to **0 Aura** and has been delisted!\n\n**{len(wiped)} holder(s)** had their shares dissolved. Holders received 10% back. Relists in **{relist_delay // 3600} hours**.",
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text="All shares have been dissolved. No payout.")
                await ch.send(embed=embed)
            logging.info(f"{coin} delisted, {len(wiped)} holders wiped, relists in {relist_delay//3600}h")
            continue

        if coin not in stock_history:
            stock_history[coin] = []
        stock_history[coin].append(stocks[coin])

        if len(stock_history[coin]) > 144:
            stock_history[coin].pop(0)

    import time as _time
    now_ts = _time.time()
    for coin in list(delisted_coins.keys()):
        if now_ts >= delisted_coins[coin]:
            relist_price = float(random.randint(10, 80))  # random relist price
            stocks[coin] = relist_price
            stock_history[coin] = [relist_price] * 10
            del delisted_coins[coin]
            save_data()
            ch = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)
            if ch:
                embed = discord.Embed(
                    title="🔔 COIN RELISTED",
                    description=f"**{coin}** is back on the market!\nRelisted at **{int(relist_price)} Aura**. Fresh start — no bagholders.",
                    color=discord.Color.green()
                )
                await ch.send(embed=embed)
            logging.info(f"{coin} relisted at {relist_price}")

    save_data()


SCIENCE_FACTS = [
    "🔬 A teaspoon of a neutron star would weigh about 10 million tons.",
    "🧬 Your DNA, if uncoiled, would stretch from Earth to the Sun and back about 600 times.",
    "⚡ Lightning strikes Earth about 100 times every single second.",
    "🌊 The ocean covers 71% of Earth's surface but 95% of it remains unexplored.",
    "🧠 Your brain generates about 23 watts of power — enough to light a small bulb.",
    "🪐 A day on Venus is longer than a year on Venus.",
    "🌡️ Hot water can freeze faster than cold water — this is called the Mpemba Effect.",
    "🦈 Sharks are older than trees. Sharks have existed for ~450 million years, trees for ~350 million.",
    "🌌 There are more stars in the universe than grains of sand on all of Earth's beaches.",
    "🐙 Octopuses have three hearts, blue blood, and can edit their own RNA.",
    "🍌 Bananas are slightly radioactive due to their potassium content.",
    "🌍 Earth is the only planet not named after a Greek or Roman god.",
    "🔭 The Voyager 1 probe, launched in 1977, is now over 23 billion km from Earth.",
    "🧊 Ice is less dense than water — that's why icebergs float.",
    "💨 The speed of sound is about 1235 km/h, but the speed of light is about 1 billion km/h.",
    "🦴 The femur (thigh bone) is stronger than concrete.",
    "🌙 The Moon is moving away from Earth at about 3.8 cm per year.",
    "🐘 Elephants are the only animals that can't jump.",
    "🌺 Oxford University is older than the Aztec Empire.",
    "🧲 If you removed all the empty space from atoms in the human body, everyone on Earth would fit in a sugar cube.",
]

last_science_fact_date = None


last_hot_take_date = None

@tasks.loop(minutes=30)
async def daily_hot_take():
    global last_hot_take_date
    now = datetime.datetime.now(IST)
    today = now.date().isoformat()
    if last_hot_take_date == today:
        return
    if not (19 <= now.hour < 22):  # 7pm-10pm IST
        return
    if random.random() > 0.15:
        return
    last_hot_take_date = today
    ch = bot.get_channel(CHAT_CHANNEL_ID)
    if not ch:
        return
    stock_prices = ", ".join(f"{c}: {v:.1f} Aura" for c, v in stocks.items())
    take = await quick_ai(f"You are a sarcastic stock market analyst for a Discord server economy. Current prices: {stock_prices}. Give one hot take or prediction about these server stocks. Be funny and opinionated. Max 2 sentences. ALWAYS finish your sentence.", max_tokens=300)
    if take:
        embed = discord.Embed(title="🔥 Hot Take of the Day", description=take, color=discord.Color.orange())
        embed.set_footer(text="This is not financial advice. Or is it? 👀")
        await ch.send(embed=embed)


@tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=IST))  # 8pm IST every day
async def weekly_recap_task():
    now = datetime.datetime.now(IST)
    if now.weekday() != 6:  # Only on Sunday
        return
    ch = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)
    if not ch:
        return

    top_earner_id = max(weekly_aura_earned, key=weekly_aura_earned.get) if weekly_aura_earned else None
    top_earner_name = ""
    if top_earner_id:
        for g in bot.guilds:
            m = g.get_member(top_earner_id)
            if m:
                top_earner_name = m.display_name
                break
        top_earner_name = top_earner_name or f"<@{top_earner_id}>"

    top_loser_id = max(weekly_casino_lost, key=weekly_casino_lost.get) if weekly_casino_lost else None
    top_loser_name = ""
    if top_loser_id:
        for g in bot.guilds:
            m = g.get_member(top_loser_id)
            if m:
                top_loser_name = m.display_name
                break
        top_loser_name = top_loser_name or f"<@{top_loser_id}>"

    best_stock = max(stocks, key=stocks.get)
    worst_stock = min(stocks, key=stocks.get)

    prompt = (
        f"Write a fun weekly server recap for a Discord economy server. "
        f"Top Aura earner this week: {top_earner_name} with {weekly_aura_earned.get(top_earner_id, 0):,} Aura. "
        f"Biggest casino loser: {top_loser_name} lost {weekly_casino_lost.get(top_loser_id, 0):,} Aura. "
        f"Highest priced stock: {best_stock} at {stocks[best_stock]:.1f} Aura. "
        f"Lowest priced stock: {worst_stock} at {stocks[worst_stock]:.1f} Aura. "
        f"Be funny, engaging, like a sports commentator. 3-4 sentences max."
    )
    recap = await quick_ai(prompt, max_tokens=600)

    embed = discord.Embed(
        title="📊 Weekly Server Recap",
        description=recap or "Another week in the books! Check the leaderboard to see where you stand.",
        color=discord.Color.blurple()
    )
    if top_earner_id:
        embed.add_field(name="💰 Top Earner", value=f"{top_earner_name} — +{weekly_aura_earned.get(top_earner_id,0):,} Aura", inline=True)
    if top_loser_id:
        embed.add_field(name="🎰 Biggest Gambler", value=f"{top_loser_name} — lost {weekly_casino_lost.get(top_loser_id,0):,} Aura", inline=True)
    embed.add_field(name="📈 Hot Stock", value=f"{best_stock} @ {stocks[best_stock]:.1f}", inline=True)
    embed.add_field(name="📉 Cold Stock", value=f"{worst_stock} @ {stocks[worst_stock]:.1f}", inline=True)
    embed.set_footer(text="See you next week! Keep grinding 💪")

    await ch.send(embed=embed)

    weekly_aura_earned.clear()
    weekly_casino_lost.clear()


@tasks.loop(seconds=15)
async def reminder_checker():
    global pending_reminders
    now = time.time()
    fired = []
    for reminder in pending_reminders:
        if now >= float(reminder["time"]):
            ch = bot.get_channel(int(reminder["channel_id"]))
            if ch:
                try:
                    await ch.send(f"<@{reminder['user_id']}> ⏰ Reminder: **{reminder['message']}**")
                    logging.info(f"Reminder fired for user {reminder['user_id']}: {reminder['message']}")
                except Exception as e:
                    logging.error(f"Reminder send error: {e}")
            fired.append(reminder)
    if fired:
        for r in fired:
            pending_reminders.remove(r)
        save_data()

@tasks.loop(minutes=30)
async def science_fact_dropper():
    global last_science_fact_date
    now = datetime.datetime.now(IST)
    today = now.date().isoformat()

    if not (18 <= now.hour < 23):
        return

    if last_science_fact_date == today:
        return

    if random.random() > 0.20:
        return

    last_science_fact_date = today
    channel = bot.get_channel(CHAT_CHANNEL_ID)
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
    await channel.send(embed=embed)

@tasks.loop(minutes=20)
async def daily_puzzle_scheduler():
    global puzzles_sent_today, puzzle_date, active_puzzle, last_puzzle_time
    global puzzle_slots, puzzle_slots_date

    now = datetime.datetime.now(IST)
    today = now.date().isoformat()
    hour = now.hour

    if puzzle_slots_date != today:
        puzzle_slots_date = today
        puzzle_slots = {"midnight": False, "afternoon": False, "random": False}
        puzzle_date = today
        puzzles_sent_today = 0
        last_puzzle_time = 0
        active_puzzle = {"question": None, "answer": None, "solved": False}

    if last_puzzle_time and (time.time() - last_puzzle_time) < 3600:
        return


    slot = None
    chance = 0.0

    if not puzzle_slots.get("midnight") and 0 <= hour < 1:
        slot = "midnight"
        chance = 0.40

    elif not puzzle_slots.get("afternoon") and 12 <= hour < 17:
        slot = "afternoon"
        chance = 0.25

    elif not puzzle_slots.get("random") and 9 <= hour < 23:
        slot = "random"
        chance = 0.08

    if slot is None or random.random() > chance:
        return

    channel = bot.get_channel(CHAT_CHANNEL_ID)
    if not channel:
        return

    available = [p for p in PUZZLES if p["a"] not in used_puzzles]
    if not available:
        used_puzzles.clear()
        available = list(PUZZLES)

    puzzle = random.choice(available)
    used_puzzles.append(puzzle["a"])

    active_puzzle["question"] = puzzle["q"]
    active_puzzle["answer"] = puzzle["a"]
    active_puzzle["type"] = puzzle.get("type", "riddle")
    active_puzzle["solved"] = False

    puzzle_slots[slot] = True
    puzzles_sent_today += 1
    last_puzzle_time = time.time()
    save_data()

    ptype = puzzle.get("type", "riddle")
    type_config = {
        "riddle":    ("🧩", "Riddle",            discord.Color.purple(),  "Think carefully and type your answer!"),
        "scramble":  ("🔀", "Word Scramble",      discord.Color.orange(),  "Unscramble the letters to find the word!"),
        "math":      ("🔢", "Math Challenge",     discord.Color.blue(),    "Type just the number as your answer!"),
        "trivia":    ("🎯", "Trivia Question",    discord.Color.gold(),    "Type your answer in chat!"),
        "emoji":     ("🎭", "Emoji Puzzle",       discord.Color.fuchsia(), "Decode the emojis and type what it represents!"),
        "fillblank": ("✏️", "Fill in the Blank",  discord.Color.green(),   "Type the missing word to complete the phrase!"),
    }
    emoji_icon, type_name, color, hint = type_config.get(ptype, ("🧩", "Puzzle", discord.Color.purple(), "Type your answer!"))

    slot_labels = {
        "midnight":  "🌙 Midnight Puzzle",
        "afternoon": "☀️ Afternoon Puzzle",
        "random":    "🎲 Surprise Puzzle",
    }

    embed = discord.Embed(
        title=f"{emoji_icon} {type_name} — First to answer wins 50 Aura!",
        description=f"**{puzzle['q']}**\n\n*{hint}*",
        color=color
    )
    embed.set_footer(text=f"{slot_labels[slot]}  •  Type: {type_name}  •  #{puzzles_sent_today} of 3 today")
    await channel.send(embed=embed)
    
@tasks.loop(hours=24)    
async def autokick_check():
    cfg = autokick_cfg
    if not cfg.get("role_id"): 
        return
        
    warn_channel = bot.get_channel(AUTOKICK_WARN_CHANNEL_ID)
    if not warn_channel: 
        return
        
    guild = warn_channel.guild
    role = guild.get_role(cfg["role_id"])
    if not role: 
        return
        
    days_limit = cfg["days"]
    half_days = cfg["days"] / 2.0
    now = time.time()
    to_warn = []
    to_kick = []
    
    for member in role.members:
        if member.bot: 
            continue
            
        uid_str = str(member.id)
        if not user_timers.get(uid_str):
            user_timers[uid_str] = now
            save_data()
            continue
            
        elapsed_days = (now - user_timers[uid_str]) / 86400.0
        
        if elapsed_days >= days_limit: 
            to_kick.append(member)
        elif elapsed_days >= half_days and uid_str not in cfg.get("warned", []):
            to_warn.append(member)
            if "warned" not in cfg: 
                cfg["warned"] = []
            cfg["warned"].append(uid_str)
            
    if to_warn or to_kick: 
        save_data()
        
    if to_kick:
        kicked_names = []
        for m in to_kick:
            try: 
                await m.send(f"You have been kicked from **{guild.name}** as your {days_limit}-day time limit has expired.")
            except: 
                pass
                
            try: 
                await m.kick(reason=f"Time limit of {days_limit} days expired")
                kicked_names.append(f"**{m.display_name}**")
                if str(m.id) in cfg.get("warned", []): 
                    cfg["warned"].remove(str(m.id))
                if str(m.id) in user_timers: 
                    del user_timers[str(m.id)]
            except: 
                pass
                
        if kicked_names:
            await warn_channel.send(embed=discord.Embed(title="👢 Users Auto-Kicked", description=f"The following users failed to open a ticket in time and were removed:\n{', '.join(kicked_names)}", color=discord.Color.red()))
        
    if to_warn:
        mentions = " ".join([m.mention for m in to_warn])
        await warn_channel.send(content=mentions, embed=discord.Embed(title="⚠️ Time Limit Warning!", description=f"You are exactly halfway through your **{days_limit}-day** limit.\n\nPlease create a ticket or msg the issue in help channel <#{HELP_CHANNEL_ID}>, otherwise you will be automatically kicked.", color=discord.Color.orange()))

@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=IST))
async def midnight_birthday_check():
    today_str = datetime.datetime.now(IST).date().isoformat()
    today_bday_str = datetime.datetime.now(IST).strftime("%d-%m")
    
    bot_bank["date"] = today_str
    bot_bank["balance"] = 100
    save_data()

    announce = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)
    if announce: 
        await announce.send(f"{E_PARTY} **A brand new day has begun!** Time to farm some positive Aura. Claim your `/daily` now! {E_VIBE}")
        
    bday_channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
    chat_channel = bot.get_channel(CHAT_CHANNEL_ID)
    guild = bday_channel.guild if bday_channel else None
    
    if bday_channel and guild:
        role = guild.get_role(BIRTHDAY_ROLE_ID)
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
            
            embed_bday = discord.Embed(title=f"🎂 HAPPY BIRTHDAY! {E_PARTY}", description=f"Wishing a fantastic birthday to:\n{mentions}\n\n🎁 You have been given the exclusive 24h Birthday Role! Enjoy your special day! 🎉", color=discord.Color.fuchsia())
            embed_bday.set_image(url="https://media.tenor.com/E62sJ88Xj3kAAAAC/happy-birthday.gif")
            await bday_channel.send(content=mentions, embed=embed_bday)
            
            if chat_channel:
                await chat_channel.send(content=mentions, embed=discord.Embed(title=f"🎉 BIRTHDAY ALERT! 🎉", description=f"Everyone drop some love for {mentions}! It's their birthday today! 🎂🥳", color=discord.Color.gold()))

@tasks.loop(minutes=5)
async def check_birthday_roles():
    now = time.time()
    expired = [uid for uid, exp in active_birthday_roles.items() if now > exp]
    
    if expired:
        channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
        if channel:
            guild = channel.guild
            role = guild.get_role(BIRTHDAY_ROLE_ID)
            if role:
                for uid in expired:
                    member = guild.get_member(uid)
                    if member:
                        try: 
                            await member.remove_roles(role)
                        except: 
                            pass
                    del active_birthday_roles[uid]
                save_data()


ROULETTE_WHEEL = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
RED_NUMS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

def get_color_emoji(n):
    if n == 0: return "🟢"
    return "🔴" if n in RED_NUMS else "⚫"

def get_wheel_string(center_idx):
    window = [ROULETTE_WHEEL[(center_idx + i) % 37] for i in range(-2, 3)]
    return " | ".join(f"{get_color_emoji(n)} {n:02d}" for n in window)

@bot.tree.command(name="french_roulette", description="Play Casino Roulette (Bet on Colors, Parity, Dozens, Columns, or 0-36)")
@app_commands.describe(bet_on="red, black, even, odd, high, low, 1st, 2nd, 3rd, col1, col2, col3, or 0-36")
async def french_roulette(i: discord.Interaction, amount: int, bet_on: str):
    if amount <= 0: 
        return await i.response.send_message("Invalid bet!", ephemeral=True)
        
    if balance[i.user.id] < amount: 
        return await i.response.send_message(f"Not enough Aura! Your balance is {balance[i.user.id]:,}", ephemeral=True)

    high_roller = amount > 150  # guaranteed loss flag

    bet_target = bet_on.lower().strip()
    valid_text_bets = ["red", "black", "even", "odd", "high", "low", "1st", "2nd", "3rd", "col1", "col2", "col3"]
    is_number_bet = bet_target.isdigit() and 0 <= int(bet_target) <= 36
    
    if bet_target not in valid_text_bets and not is_number_bet: 
        return await i.response.send_message("❌ Invalid bet! Choose: `red`, `black`, `even`, `odd`, `high`, `low`, `1st`, `2nd`, `3rd`, `col1`, `col2`, `col3`, or a number `0-36`.", ephemeral=True)

    balance[i.user.id] -= amount
    save_data()
    
    def check_win(res, bet):
        if bet.isdigit() and int(bet) == res: 
            return True, 35
        
        res_c = "green" if res == 0 else ("red" if res in RED_NUMS else "black")
        res_p = "even" if res != 0 and res % 2 == 0 else ("odd" if res % 2 != 0 else "none")
        res_h = "low" if 1 <= res <= 18 else ("high" if 19 <= res <= 36 else "none")
        
        if bet in ["red", "black", "even", "odd", "high", "low"]:
            if bet in [res_c, res_p, res_h]: 
                return True, 1
        elif bet == "1st" and 1 <= res <= 12: 
            return True, 2
        elif bet == "2nd" and 13 <= res <= 24: 
            return True, 2
        elif bet == "3rd" and 25 <= res <= 36: 
            return True, 2
        elif bet == "col1" and res != 0 and res % 3 == 1: 
            return True, 2
        elif bet == "col2" and res != 0 and res % 3 == 2: 
            return True, 2
        elif bet == "col3" and res != 0 and res % 3 == 0: 
            return True, 2
        
        return False, 0

    result = random.randint(0, 36)
    win, payout_multiplier = check_win(result, bet_target)

    if high_roller:
        attempts = 0
        while check_win(result, bet_target)[0] and attempts < 100:
            result = random.randint(0, 36)
            attempts += 1
        win = False
        payout_multiplier = 0
    elif win and random.random() < 0.15:
        while True:
            result = random.randint(0, 36)
            win, payout_multiplier = check_win(result, bet_target)
            if not win:
                break

    res_color = "green" if result == 0 else ("red" if result in RED_NUMS else "black")

    embed = discord.Embed(title="🎡 French Roulette", color=discord.Color.blurple())
    embed.description = f"{E_LOAD} **Spinning the wheel...**\n\n**Bet:** {amount:,} Aura on **{bet_target.upper()}**"
    await i.response.send_message(embed=embed)

    for _ in range(3):
        await asyncio.sleep(1.2)
        fake_idx = random.randint(0, 36)
        fake_display = get_wheel_string(fake_idx)
        embed.description = f"{E_LOAD} **Spinning...**\n\n**Bet:** {amount:,} Aura on **{bet_target.upper()}**\n\n```\n{fake_display}\n                  ⬆️\n```"
        try:
            await i.edit_original_response(embed=embed)
        except Exception:
            pass

    await asyncio.sleep(1.2)

    display = get_wheel_string(ROULETTE_WHEEL.index(result))
    result_text = f"{get_color_emoji(result)} **{result} {res_color.upper()}**"
    
    partage = False
    if not win and result == 0 and bet_target in ["red", "black", "even", "odd", "high", "low"]:
        partage = True
        
    if win:
        profit = amount * payout_multiplier
        gross = amount + profit
        house_cut = max(1, int(gross * 0.05))
        winnings = gross - house_cut
        balance[i.user.id] += winnings
        save_data()

        final_embed = discord.Embed(title="🎡 French Roulette", color=discord.Color.green())
        final_embed.add_field(name="Result", value=result_text, inline=False)
        final_embed.add_field(name="Outcome", value=f"🎉 **YOU WON!**\nPayout: **{winnings:,} Aura** *(5% house tax applied)*", inline=False)
    elif partage:
        refund = int(amount / 2)
        balance[i.user.id] += refund
        save_data()
        
        final_embed = discord.Embed(title="🎡 French Roulette", color=discord.Color.orange())
        final_embed.add_field(name="Result", value=result_text, inline=False)
        final_embed.add_field(name="Outcome", value=f"⚖️ **LA PARTAGE!**\nLanded on Zero. Half your bet (**{refund:,} Aura**) returned.", inline=False)
    else:
        final_embed = discord.Embed(title="🎡 French Roulette", color=discord.Color.red())
        final_embed.add_field(name="Result", value=result_text, inline=False)
        final_embed.add_field(name="Outcome", value=f"💀 **YOU LOST!**\nLost: **{amount:,} Aura**", inline=False)

    final_embed.description = f"**Bet:** {amount:,} Aura on **{bet_target.upper()}**\n\n```\n{display}\n                  ⬆️                  \n```"
    final_embed.set_footer(text=f"New Balance: {balance[i.user.id]:,} Aura")
    try:
        await i.edit_original_response(embed=final_embed)
    except Exception:
        await i.followup.send(embed=final_embed)


@bot.tree.command(name="bj", description="Play Blackjack against the dealer")
async def blackjack_cmd(i: discord.Interaction, bet: int):
    if bet <= 0: 
        return await i.response.send_message("Invalid bet amount!", ephemeral=True)
        
    if balance[i.user.id] < bet: 
        return await i.response.send_message(f"Not enough Aura! Your balance is {balance[i.user.id]:,}", ephemeral=True)

    balance[i.user.id] -= bet
    save_data()
    
    view = BlackjackView(i.user, bet)
    await i.response.send_message(embed=view.build_embed(), view=view)

@bot.tree.command(name="duel", description="Challenge someone or the Bot to a Rock Paper Scissors duel")
async def duel(i: discord.Interaction, opponent: discord.Member, amount: int):
    if balance[i.user.id] < amount or amount <= 0: 
        return await i.response.send_message("Invalid bet.", ephemeral=True)
        
    if opponent.id == i.user.id: 
        return await i.response.send_message("You can't duel yourself!", ephemeral=True)
    
    if opponent.bot:
        today_str = datetime.datetime.now(IST).date().isoformat()
        if bot_bank.get("date") != today_str: 
            bot_bank["date"] = today_str
            bot_bank["balance"] = 100
            save_data()
            
        if bot_bank["balance"] < amount: 
            return await i.response.send_message(f"🤖 I only have **{bot_bank['balance']:,} Aura** left to bet today! I can't accept that duel.", ephemeral=True)

        balance[i.user.id] -= amount
        save_data()
        
        view = BotDuelRPSView(i.user, amount)
        embed = discord.Embed(title="⚔️ RPS Bot Duel", description=f"🤖 {i.user.mention}, you challenged ME for **{amount:,} Aura**!\n\nChoose your weapon below.", color=discord.Color.blue())
        await i.response.send_message(embed=embed, view=view)
    else:
        await i.response.send_message(f"⚔️ {opponent.mention}, {i.user.mention} challenged you to Rock Paper Scissors for **{amount:,} Aura**!", view=AcceptDuelView(i.user, opponent, amount, "rps"))

@bot.tree.command(name="dice_duel", description="High Rollers Dice Duel")
async def dice_duel(i: discord.Interaction, opponent: discord.Member, amount: int):
    if balance[i.user.id] < amount or amount <= 0: 
        return await i.response.send_message("Invalid bet.", ephemeral=True)
        
    if opponent.id == i.user.id: 
        return await i.response.send_message("You can't duel yourself!", ephemeral=True)
    
    if opponent.bot:
        today_str = datetime.datetime.now(IST).date().isoformat()
        if bot_bank.get("date") != today_str: 
            bot_bank["date"] = today_str
            bot_bank["balance"] = 100
            save_data()
            
        if bot_bank["balance"] < amount: 
            return await i.response.send_message(f"🤖 I only have **{bot_bank['balance']:,} Aura** left to bet today! I can't accept that duel.", ephemeral=True)

        balance[i.user.id] -= amount
        save_data()
        
        view = BotDiceDuelView(i.user, amount)
        await i.response.send_message(f"🤖 {i.user.mention}, you challenged ME to Dice for **{amount:,} Aura**! Click below to roll.", view=view)
    else:
        await i.response.send_message(f"🎲 {opponent.mention}, {i.user.mention} challenged you to a High Rollers duel for **{amount:,} Aura**!", view=AcceptDuelView(i.user, opponent, amount, "dice"))

@bot.tree.command(name="roulette", description="Russian Roulette Duel")
async def roulette(i: discord.Interaction, opponent: discord.Member, amount: int):
    if balance[i.user.id] < amount or amount <= 0: 
        return await i.response.send_message("Invalid bet.", ephemeral=True)
        
    if opponent.id == i.user.id: 
        return await i.response.send_message("You can't duel yourself!", ephemeral=True)
    
    if opponent.bot:
        today_str = datetime.datetime.now(IST).date().isoformat()
        if bot_bank.get("date") != today_str: 
            bot_bank["date"] = today_str
            bot_bank["balance"] = 100
            save_data()
            
        if bot_bank["balance"] < amount: 
            return await i.response.send_message(f"🤖 I only have **{bot_bank['balance']:,} Aura** left to bet today! I can't accept that duel.", ephemeral=True)

        balance[i.user.id] -= amount
        save_data()
        
        view = BotRouletteView(i.user, amount)
        await i.response.send_message(f"🤖 {i.user.mention}, you challenged ME to Russian Roulette for **{amount:,} Aura**!\n\nYou go first. Pull the trigger.", view=view)
    else:
        await i.response.send_message(f"🔫 {opponent.mention}, {i.user.mention} challenged you to Russian Roulette for **{amount:,} Aura**!", view=AcceptDuelView(i.user, opponent, amount, "roulette"))

@bot.tree.command(name="draw", description="Quick Draw Duel")
async def draw_cmd(i: discord.Interaction, opponent: discord.Member, amount: int):
    if balance[i.user.id] < amount or amount <= 0: 
        return await i.response.send_message("Invalid bet.", ephemeral=True)
        
    if opponent.id == i.user.id: 
        return await i.response.send_message("You can't duel yourself!", ephemeral=True)
    
    if opponent.bot:
        today_str = datetime.datetime.now(IST).date().isoformat()
        if bot_bank.get("date") != today_str: 
            bot_bank["date"] = today_str
            bot_bank["balance"] = 100
            save_data()
            
        if bot_bank["balance"] < amount: 
            return await i.response.send_message(f"🤖 I only have **{bot_bank['balance']:,} Aura** left to bet today! I can't accept that duel.", ephemeral=True)

        balance[i.user.id] -= amount
        save_data()
        
        view = BotDrawView(i.user, amount)
        await i.response.send_message(f"🤖 {i.user.mention}, you challenged ME to a Quick Draw for **{amount:,} Aura**!\n\n*Wait for the DRAW signal...*", view=view)
        
        msg = await i.original_response() 
        asyncio.create_task(view.start_draw(msg))
    else:
        await i.response.send_message(f"⚡ {opponent.mention}, {i.user.mention} challenged you to a Quick Draw for **{amount:,} Aura**!", view=AcceptDuelView(i.user, opponent, amount, "draw"))

@bot.tree.command(name="escrow", description="Create a custom locked bet with another user")
async def escrow(i: discord.Interaction, opponent: discord.Member, amount: int, condition: str):
    if amount <= 0:
        return await i.response.send_message("Amount must be greater than 0.", ephemeral=True)
        
    if balance[i.user.id] < amount:
        return await i.response.send_message("You don't have enough Aura.", ephemeral=True)
        
    if opponent.bot or opponent.id == i.user.id:
        return await i.response.send_message("Invalid opponent.", ephemeral=True)
        
    view = EscrowView(i.user, opponent, amount, condition)
    embed = discord.Embed(title="🤝 Escrow Bet Challenge", description=f"{i.user.mention} is challenging {opponent.mention} to a custom bet!\n\n**Amount:** {amount:,} Aura\n**Condition:** {condition}\n\n{opponent.mention}, click Accept to lock in the funds.", color=discord.Color.purple())
    await i.response.send_message(content=opponent.mention, embed=embed, view=view)



@bot.tree.command(name="open_withdrawals", description="Staff: Open withdrawals for X hours")
@app_commands.describe(hours="How many hours to keep withdrawals open")
async def open_withdrawals(i: discord.Interaction, hours: int):
    global withdrawal_open_until
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
    if hours <= 0 or hours > 72:
        return await i.response.send_message("Please enter between 1 and 72 hours.", ephemeral=True)
    withdrawal_open_until = datetime.datetime.now(IST) + datetime.timedelta(hours=hours)
    closes_at = withdrawal_open_until.strftime("%d %b %Y %I:%M %p IST")
    announce = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)
    embed = discord.Embed(title="💸 Withdrawals are OPEN!", description=f"You can now use `/withdraw` to cash out your Aura.\n\nWithdrawals close: **{closes_at}**", color=discord.Color.green())
    if announce:
        await announce.send(embed=embed)
    await i.response.send_message(f"✅ Withdrawals opened for **{hours} hour(s)**. Closes at {closes_at}.", ephemeral=True)
    await asyncio.sleep(hours * 3600)
    if withdrawal_open_until and datetime.datetime.now(IST) >= withdrawal_open_until:
        withdrawal_open_until = None
        if announce:
            await announce.send(embed=discord.Embed(title="🔒 Withdrawals Closed", description="The withdrawal window has ended.", color=discord.Color.red()))

@bot.tree.command(name="close_withdrawals", description="Staff: Close withdrawals immediately")
async def close_withdrawals(i: discord.Interaction):
    global withdrawal_open_until
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
    withdrawal_open_until = None
    await i.response.send_message("🔒 Withdrawals closed.", ephemeral=True)

@bot.tree.command(name="withdraw", description="Withdraw your Aura")
@app_commands.choices(method=[
    app_commands.Choice(name="UPI", value="upi"), 
    app_commands.Choice(name="Crypto", value="crypto"), 
    app_commands.Choice(name="Reddit Account (Cost: 2000 Aura)", value="reddit")
])
async def withdraw(i: discord.Interaction, amount: int, method: str, details: str):
    global withdrawal_open_until
    now = datetime.datetime.now(IST)
    if withdrawal_open_until is None or now > withdrawal_open_until:
        return await i.response.send_message("🛑 Withdrawals are currently **closed**. Wait for staff to open them.", ephemeral=True)

    if amount < 1000: 
        return await i.response.send_message("Minimum withdrawal is 1000 Aura ($1.00).", ephemeral=True)
        
    if method == "reddit" and amount != 2000: 
        return await i.response.send_message("A Reddit Account costs exactly 2000 Aura.", ephemeral=True)
        
    uid = i.user.id
    if balance[uid] < amount: 
        return await i.response.send_message(f"Not enough Aura! Balance: {balance[uid]:,}", ephemeral=True)
        
    payout_channel = bot.get_channel(PAYOUT_CHANNEL_ID)
    if not payout_channel: 
        return await i.response.send_message("Payout channel not set.", ephemeral=True)
        
    balance[uid] -= amount
    save_data()
    
    item_str = f"${(amount/AURA_TO_USD):.2f} via {method.upper()}" if method != "reddit" else "1x Reddit Account"
    
    embed = discord.Embed(title="🚨 NEW PAYOUT REQUEST", color=discord.Color.orange())
    embed.add_field(name="User", value=f"{i.user.mention} ({uid})", inline=False)
    embed.add_field(name="Amount & Item", value=f"{amount:,} Aura -> {item_str}", inline=False)
    embed.add_field(name="Details", value=f"`{details}`", inline=False)
    
    payout_msg = await payout_channel.send(embed=embed, view=PayoutView(uid, amount, method, details, str(0)))
    pending_payouts[str(payout_msg.id)] = {"uid": uid, "amt": amount, "method": method, "details": details}
    await payout_msg.edit(view=PayoutView(uid, amount, method, details, str(payout_msg.id)))
    save_data()
    await i.response.send_message(embed=simple_embed("✅ Request Submitted", f"Withdrawal request for **{item_str}** submitted!", discord.Color.green()), ephemeral=True)

@bot.tree.command(name="daily", description="Claim your daily Aura reward")
async def daily(i: discord.Interaction):
    now_ist = datetime.datetime.now(IST)
    today = now_ist.date().isoformat()
    yesterday = (now_ist.date() - datetime.timedelta(days=1)).isoformat()
    uid = i.user.id

    if str(last_daily.get(uid)) == today:
        midnight = (now_ist + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        secs = int((midnight - now_ist).total_seconds())
        h, m = divmod(secs // 60, 60)
        embed = discord.Embed(
            title="Already Claimed",
            description=f"Come back in **{h}h {m}m** at midnight IST.\nCurrent streak: **{daily_streak[uid]} day{'s' if daily_streak[uid] != 1 else ''}**",
            color=discord.Color.orange()
        )
        embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)
        return await i.response.send_message(embed=embed, ephemeral=True)

    if str(last_daily.get(uid)) == yesterday:
        daily_streak[uid] += 1
    else:
        daily_streak[uid] = 1
    streak = daily_streak[uid]

    roll = random.randint(1, 100)
    if roll <= 95:
        amt = random.randint(1, 100)
    else:
        amt = random.randint(101, 200)

    streak_bonus = min(streak, 30) * 2
    amt += streak_bonus

    milestone_msg = ""
    if streak == 7:
        amt += 30
        milestone_msg = "\n+30 Aura  —  7 Day Streak Bonus"
    elif streak == 14:
        amt += 75
        milestone_msg = "\n+75 Aura  —  14 Day Streak Bonus"
    elif streak == 30:
        amt += 150
        milestone_msg = "\n+150 Aura  —  30 Day Legendary Bonus"

    old_b = balance[uid]
    balance[uid] += amt
    weekly_aura_earned[uid] += amt
    asyncio.create_task(check_balance_milestone(uid, old_b, balance[uid]))
    last_daily[uid] = today
    save_data()

    if streak >= 30:
        streak_label = f"{streak} days — LEGENDARY"
    elif streak >= 14:
        streak_label = f"{streak} days — On Fire"
    elif streak >= 7:
        streak_label = f"{streak} days — Week Warrior"
    elif streak >= 3:
        streak_label = f"{streak} days — Building Up"
    else:
        streak_label = f"{streak} day{'s' if streak > 1 else ''} — Just Started"

    def make_wheel(slots):
        row = "|".join(f"{n:^5}" for n in slots)
        arrow = " " * 13 + "^^^"
        return f"{row}\n{arrow}"

    spin_embed = discord.Embed(title="Daily Wheel", color=discord.Color.blue())
    spin_embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)

    for tick in range(5):
        slots = [random.randint(1, 100) for _ in range(5)]
        spin_embed.description = f"{E_LOAD} Spinning...\n```\n{make_wheel(slots)}\n```"
        if tick == 0:
            await i.response.send_message(embed=spin_embed)
        else:
            await i.edit_original_response(embed=spin_embed)
        await asyncio.sleep(0.55)

    final_slots = [random.randint(1, 100) for _ in range(2)] + [amt] + [random.randint(1, 100) for _ in range(2)]
    is_jackpot = roll > 95
    color = discord.Color.gold() if is_jackpot else discord.Color.green()
    title = "JACKPOT" if is_jackpot else "Daily Claimed"

    next_milestone = "7" if streak < 7 else "14" if streak < 14 else "30" if streak < 30 else None

    final_embed = discord.Embed(title=title, color=color)
    final_embed.set_author(name=i.user.display_name, icon_url=i.user.display_avatar.url)
    final_embed.description = f"```\n{make_wheel(final_slots)}\n```\n**+{amt} Aura** earned{milestone_msg}"
    final_embed.add_field(name="Streak", value=streak_label, inline=True)
    final_embed.add_field(name="Streak Bonus", value=f"+{streak_bonus} Aura", inline=True)
    final_embed.add_field(name="Balance", value=f"{balance[uid]:,} Aura", inline=True)
    footer = f"Next milestone: {next_milestone} days — come back tomorrow!" if next_milestone else "Max streak reached. Legend."
    final_embed.set_footer(text=footer)

    await i.edit_original_response(embed=final_embed)
    
@bot.tree.command(name="bal", description="Check your Aura Balance")
async def bal(i: discord.Interaction, user: Optional[discord.Member] = None):
    u = user or i.user
    amt = balance[u.id]
    
    if amt < 0: status = "In Debt 📉"
    elif amt < 100: status = "Homeless 🏚️"
    elif amt < 500: status = "Broke 💸"
    elif amt < 1000: status = "Getting There 📈"
    else: status = "Tycoon 🎩"
    
    embed = discord.Embed(title="💳 Personal Vault", color=discord.Color.from_rgb(43, 45, 49))
    embed.set_thumbnail(url=u.display_avatar.url)
    embed.add_field(name=f"👤 Account Holder", value=f"**{u.display_name}**", inline=False)
    embed.add_field(name=f"{E_COIN} Available Balance", value=f"```fix\n{amt:,} Aura```", inline=False)
    embed.add_field(name="📊 Status", value=status, inline=True)
    embed.add_field(name="📅 Member Since", value=f"<t:{int(u.joined_at.timestamp())}:D>", inline=True)
    
    server_icon = i.guild.icon.url if i.guild and i.guild.icon else None
    embed.set_footer(text="Earn more Aura by chatting in the server!", icon_url=server_icon)
    
    await i.response.send_message(embed=embed)

@bot.tree.command(name="msgs", description="Check message count")
async def msgs(i: discord.Interaction, user: Optional[discord.Member] = None):
    u = user or i.user
    await i.response.send_message(embed=simple_embed("Message Stats", f"💬 {u.mention} has sent **{message_count[u.id]:,}** messages."))

@bot.tree.command(name="gift", description="Gift Aura to another user")
async def gift(i: discord.Interaction, user: discord.Member, amount: int):
    if amount <= 0 or balance[i.user.id] < amount: 
        return await i.response.send_message("Invalid amount.", ephemeral=True)
        
    if user.bot or user.id == i.user.id: 
        return await i.response.send_message("Invalid target.", ephemeral=True)
        
    balance[i.user.id] -= amount
    balance[user.id] += amount
    save_data()
    
    await i.response.send_message(embed=discord.Embed(title="🎁 Gift Delivered!", description=f"Gifted **{amount:,}** Aura to {user.mention}.", color=discord.Color.green()))

@bot.tree.command(name="remove_aura", description="Permanently delete some of your own Aura")
async def remove_aura(i: discord.Interaction, amount: int):
    if amount <= 0:
        return await i.response.send_message("Invalid amount.", ephemeral=True)
        
    if balance[i.user.id] < amount:
        return await i.response.send_message(f"You don't have enough Aura to burn! Balance: {balance[i.user.id]:,}", ephemeral=True)
    
    before = balance[i.user.id]
    balance[i.user.id] -= amount
    save_data()

    await i.response.send_message(embed=discord.Embed(title="🔥 Aura Burned", description=f"You have permanently destroyed **{amount:,}** of your own Aura.", color=discord.Color.red()))

    log_ch = bot.get_channel(GIVE_LOG_CHANNEL_ID)
    if log_ch:
        embed = discord.Embed(title="🔥 Aura Burned", color=discord.Color.dark_orange())
        embed.add_field(name="User", value=i.user.mention, inline=True)
        embed.add_field(name="Burned", value=f"**-{amount:,} Aura**", inline=True)
        embed.add_field(name="Balance Before", value=f"{before:,}", inline=True)
        embed.add_field(name="Balance After", value=f"{balance[i.user.id]:,}", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await log_ch.send(embed=embed)

@bot.tree.command(name="gamble", description="Solo Coinflip")
@app_commands.choices(side=[
    app_commands.Choice(name="Heads", value="heads"), 
    app_commands.Choice(name="Tails", value="tails")
])
async def gamble(i: discord.Interaction, amount: int, side: str):
    if amount <= 0 or balance[i.user.id] < amount: 
        return await i.response.send_message("Invalid bet!", ephemeral=True)
    
    win_chance = 0 if amount > 150 else 20  # guaranteed loss for bets over 150
    payout_multiplier = 0.90 
    
    if random.randint(1, 100) <= win_chance:
        outcome = side
        profit = int(amount * payout_multiplier)
        balance[i.user.id] += profit
        save_data()
        
        await i.response.send_message(embed=simple_embed(
            "🎉 Won!", 
            f"Coin landed on **{outcome}**!\nYou won **{profit:,}** Aura *(10% House Tax applied)*.", 
            discord.Color.green()
        ))
    else:
        outcome = "tails" if side == "heads" else "heads"
        balance[i.user.id] -= amount
        save_data()
        
        await i.response.send_message(embed=simple_embed(
            "💀 Lost!", 
            f"Coin landed on **{outcome}**!\nYou lost **{amount:,}** Aura.", 
            discord.Color.red()
        ))

@bot.tree.command(name="leaderboard", description="View the Server Leaderboard")
@app_commands.choices(category=[
    app_commands.Choice(name="Invites", value="invites"),
    app_commands.Choice(name="Messages", value="msgs"), 
    app_commands.Choice(name="Aura Value", value="bal"),
    app_commands.Choice(name="Portfolio Value", value="port")
])
async def leaderboard(i: discord.Interaction, category: str):
    try:
        if category == "invites":
            if not invite_event_active and not invite_counts:
                return await i.response.send_message("No invite event data available.", ephemeral=True)
            source = dict(invite_counts)
            label = "Invite Leaderboard"
            emoji = "📨"
        elif category == "msgs":
            source = message_count
            label = "Most Active Chatters"
            emoji = "💬"
        elif category == "bal":
            source = balance
            label = "Richest Members"
            emoji = E_COIN
        else:
            source = {}
            for uid, holding in portfolios.items():
                p_val = 0
                if isinstance(holding, dict):
                    for c, d in holding.items():
                        if isinstance(d, dict):
                            amt = d.get("shares", 0)
                            if amt > 0:
                                val_raw = amt * stocks.get(c, 0)
                                p_val += (val_raw - (val_raw * 0.05))
                if p_val > 0: 
                    source[uid] = int(p_val)
            label = "Top Investors"
            emoji = "📈"
        
        sorted_data = sorted(source.items(), key=lambda x: int(x[1]), reverse=True)[:10]
        
        if not sorted_data:
            return await i.response.send_message(embed=discord.Embed(title=f"🏆 Top 10 | {label}", description="No data available yet.", color=discord.Color.gold()))

        desc = ""
        for idx, (u, v) in enumerate(sorted_data):
            if idx == 0: 
                rank = "🥇"
            elif idx == 1: 
                rank = "🥈"
            elif idx == 2: 
                rank = "🥉"
            else: 
                rank = f"` #{idx+1} `" 

            member = i.guild.get_member(int(u)) if i.guild else None
            name = member.display_name if member else f"<@{u}>"
            desc += f"{rank} {name} — **{int(v):,}** {emoji}\n\n"

        embed = discord.Embed(title=f"🏆 Server Leaderboard | {label}", description=desc, color=discord.Color.gold())
        
        if i.guild and i.guild.icon: 
            embed.set_thumbnail(url=i.guild.icon.url)
            
        embed.set_footer(text=f"Requested by {i.user.display_name}", icon_url=i.user.display_avatar.url)
        
        await i.response.send_message(embed=embed)
    except Exception as e:
        await i.response.send_message(f"Leaderboard Error: {e}", ephemeral=True)



class ChartStyleView(discord.ui.View):
    def __init__(self, coin: str, style: str = "line"):
        super().__init__(timeout=120)
        self.coin = coin
        self.current_style = style

        coin_select = discord.ui.Select(
            placeholder=f"📊 Viewing: {coin}",
            options=[
                discord.SelectOption(label=c, value=c, emoji="🟢" if c == coin else None)
                for c in DEFAULT_STOCKS.keys()
            ],
            custom_id="coin_select",
            row=0
        )
        coin_select.callback = self.switch_coin
        self.add_item(coin_select)

    def build_embed(self):
        hist = stock_history.get(self.coin, [stocks[self.coin]] * 15)
        current = stocks[self.coin]
        old = hist[0] if hist else current
        trend_pct = ((current - old) / old) * 100 if old > 0 else 0
        emoji = "📈" if trend_pct >= 0 else "📉"
        color = discord.Color.green() if trend_pct >= 0 else discord.Color.red()

        high = max(hist) if hist else current
        low = min(hist) if hist else current
        sparkline = generate_sparkline(hist)

        style_labels = {
            "line": "📈 Line Graph",
            "area": "⛰️ Area Graph",
            "candle": "🕯️ Candlestick",
            "spark": "✨ Sparkline"
        }

        if self.current_style == "line":
            chart = generate_line_chart(hist, width=28, height=8)
        elif self.current_style == "area":
            chart = generate_area_chart(hist, height=8)
        elif self.current_style == "candle":
            chart = generate_candlestick_chart(hist, height=8)
        else:
            chart = f"Trend:\n{sparkline}"

        embed = discord.Embed(
            title=f"{emoji}  {self.coin}  —  Market Chart",
            color=color
        )
        embed.description = f"```text\n{chart}\n```"
        embed.add_field(name="💰 Current Price", value=f"```fix\n{int(current):,} Aura\n```", inline=True)
        embed.add_field(name="📊 Trend", value=f"```fix\n{trend_pct:+.2f}%\n```", inline=True)
        embed.add_field(name="🕐 Data Points", value=f"```fix\n{len(hist)} ticks\n```", inline=True)
        embed.add_field(name="🟢 Period High", value=f"```fix\n{int(high):,} Aura\n```", inline=True)
        embed.add_field(name="🔴 Period Low", value=f"```fix\n{int(low):,} Aura\n```", inline=True)
        embed.add_field(name="📉 Range", value=f"```fix\n{int(high - low):,} Aura\n```", inline=True)
        embed.add_field(name="✨ Sparkline", value=f"`{sparkline}`", inline=False)
        embed.set_footer(text=f"Chart Style: {style_labels.get(self.current_style, 'Line Graph')}  •  Updates every 5 minutes")

        return embed

    async def switch_coin(self, i: discord.Interaction):
        self.coin = i.data["values"][0]
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.placeholder = f"📊 Viewing: {self.coin}"
                item.options = [
                    discord.SelectOption(label=c, value=c, emoji="🟢" if c == self.coin else None)
                    for c in DEFAULT_STOCKS.keys()
                ]
        await i.response.edit_message(embed=self.build_embed(), view=self)

    async def update_chart(self, i: discord.Interaction, style: str):
        self.current_style = style
        await i.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Line Graph", emoji="📈", style=discord.ButtonStyle.primary, row=1)
    async def btn_line(self, i: discord.Interaction, b: discord.ui.Button):
        await self.update_chart(i, "line")

    @discord.ui.button(label="Area Graph", emoji="⛰️", style=discord.ButtonStyle.secondary, row=1)
    async def btn_area(self, i: discord.Interaction, b: discord.ui.Button):
        await self.update_chart(i, "area")

    @discord.ui.button(label="Candles", emoji="🕯️", style=discord.ButtonStyle.secondary, row=1)
    async def btn_candle(self, i: discord.Interaction, b: discord.ui.Button):
        await self.update_chart(i, "candle")

    @discord.ui.button(label="Spark", emoji="✨", style=discord.ButtonStyle.secondary, row=1)
    async def btn_spark(self, i: discord.Interaction, b: discord.ui.Button):
        await self.update_chart(i, "spark")

@bot.tree.command(name="stocks", description="View the live Mod Coins market prices")
async def view_stocks(i: discord.Interaction):
    desc = ""
    import time as _time
    for coin, price in stocks.items():
        if coin in delisted_coins:
            secs = max(0, int(delisted_coins[coin] - _time.time()))
            h, m = divmod(secs // 60, 60)
            desc += f"**{coin}** — 💀 DELISTED (relists in {h}h {m}m)\n\n"
            continue
        hist = stock_history.get(coin, [price]*15)
        old_price = hist[0] if hist else price
        trend_pct = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
        trend_emoji = "📈" if trend_pct >= 0 else "📉"
        spark = generate_sparkline(hist)
        desc += f"**{coin}** — {int(price):,} Aura  {trend_emoji} `{trend_pct:+.1f}%`\n`{spark}`\n\n"
        
    await i.response.send_message(embed=discord.Embed(title="📊 Live Mod Coins Market", description=desc, color=discord.Color.brand_green()))

@bot.tree.command(name="coin_chart", description="View a detailed chart for a specific Mod Coin")
@app_commands.choices(coin=[app_commands.Choice(name=c, value=c) for c in DEFAULT_STOCKS.keys()])
async def coin_chart(i: discord.Interaction, coin: str):
    chart_view = ChartStyleView(coin)
    await i.response.send_message(embed=chart_view.build_embed(), view=chart_view)

@bot.tree.command(name="insider_tip", description="Pay 250 Aura for inside info on a specific coin (20% chance of bad info)")
@app_commands.choices(coin=[app_commands.Choice(name=c, value=c) for c in DEFAULT_STOCKS.keys()])
async def insider_tip(i: discord.Interaction, coin: str):
    global insider_uses_date, insider_uses_today

    today_str = datetime.datetime.now(IST).date().isoformat()
    if insider_uses_date != today_str:
        insider_uses_date = today_str
        insider_uses_today.clear()

    if insider_uses_today[i.user.id] >= 2:
        return await i.response.send_message("🛑 You've already used your 2 insider tips for today. Come back tomorrow.", ephemeral=True)

    if balance[i.user.id] < 250:
        return await i.response.send_message("You need 250 Aura to bribe me for inside info!", ephemeral=True)

    balance[i.user.id] -= 250
    insider_uses_today[i.user.id] += 1
    save_data()

    current_day = datetime.datetime.now(IST).date().toordinal()
    random.seed(current_day + personality_season)

    personalities = ["moon", "rugpull", "volatile", "stable", "steady_up", "steady_down", "wildcard"]
    random.shuffle(personalities)
    coin_personalities = {c: p for c, p in zip(stocks.keys(), personalities)}
    random.seed()

    p = coin_personalities[coin]

    if random.random() < 0.20:
        other = [x for x in personalities if x != p]
        p = random.choice(other)

    tips = {
        "moon":       f"**{coin}** is gearing up for a massive MOON mission today. Buy everything you can.",
        "rugpull":    f"Stay far away from **{coin}**. The devs are planning a rugpull today.",
        "volatile":   f"**{coin}** is going to be incredibly volatile today. Huge swings up and down.",
        "stable":     f"**{coin}** is basically a stablecoin today. Don't expect much movement.",
        "steady_up":  f"**{coin}** is seeing steady, consistent accumulation today. Safe upward bet.",
        "steady_down":f"**{coin}** is slowly bleeding out today. Better to sell off your bags.",
        "wildcard":   f"**{coin}** is a wildcard today. It could randomly skyrocket or crash in a single tick.",
    }

    uses_left = 2 - insider_uses_today[i.user.id]
    embed = discord.Embed(title="🕵️‍♂️ Insider Market Tip", description=f"*(Whispering)* Look, don't tell the feds I told you this, but {tips[p]}", color=discord.Color.dark_embed())
    embed.set_footer(text=f"Tips remaining today: {uses_left}/2  •  Info may not be 100% accurate")
    await i.response.send_message(embed=embed, ephemeral=True)
@bot.tree.command(name="invest", description="Buy coins from the market (5% Broker Fee)")
@app_commands.choices(coin=[app_commands.Choice(name=c, value=c) for c in DEFAULT_STOCKS.keys()])
async def invest_cmd(i: discord.Interaction, coin: str, shares: int):
    if shares <= 0:
        return await i.response.send_message("Invalid amount.", ephemeral=True)
    if coin in delisted_coins:
        import time as _time
        secs = max(0, int(delisted_coins[coin] - _time.time()))
        h, m = divmod(secs // 60, 60)
        return await i.response.send_message(f"💀 **{coin} is delisted!** Relists in **{h}h {m}m**.", ephemeral=True)
    if stocks[coin] < 1:
        return await i.response.send_message(f"❌ **{coin}** is too cheap to invest in right now.", ephemeral=True)
    
    raw_cost = stocks[coin] * shares
    fee = int(raw_cost * 0.05)
    total_cost = int(raw_cost + fee)
    
    if total_cost > 400:
        return await i.response.send_message("🛑 **Max Cap:** You can only invest up to **400 Aura** per transaction.", ephemeral=True)
    if balance[i.user.id] < total_cost:
        return await i.response.send_message(f"You need **{total_cost:,} Aura** (includes 5% fee) to buy {shares} shares of {coin}.", ephemeral=True)
        
    current_portfolio_value = sum(
        portfolios[i.user.id][c].get("shares", 0) * stocks.get(c, 0)
        for c in portfolios[i.user.id]
    )
    if current_portfolio_value + raw_cost > 1500:
        remaining = max(0, int(1500 - current_portfolio_value))
        return await i.response.send_message(f"🛑 **Portfolio Cap!** Only **{remaining:,} Aura** of room left (max 1,500).", ephemeral=True)
        
    current_shares_held = portfolios[i.user.id][coin].get("shares", 0)
    if current_shares_held + shares > MAX_SHARES_PER_COIN:
        allowed = max(0, MAX_SHARES_PER_COIN - current_shares_held)
        if allowed == 0:
            return await i.response.send_message(f"🛑 **Share Cap!** You already hold max {MAX_SHARES_PER_COIN} shares of {coin}.", ephemeral=True)
        return await i.response.send_message(f"🛑 **Share Cap!** You can only buy **{allowed} more shares** of {coin}.", ephemeral=True)
        
    balance[i.user.id] -= total_cost
    portfolios[i.user.id][coin]["shares"] += shares
    portfolios[i.user.id][coin]["invested"] = portfolios[i.user.id][coin].get("invested", 0.0) + total_cost
    save_data()
    
    await i.response.send_message(f"📈 **INVESTMENT SECURED**\nBought **{shares} {coin}** @ {stocks[coin]:.1f} Aura\nTotal Cost: **{total_cost:,} Aura** *(includes {fee:,} Aura broker fee)*.")

@bot.tree.command(name="sell", description="Sell your coins back to the market (5% Broker Fee)")
@app_commands.choices(coin=[app_commands.Choice(name=c, value=c) for c in DEFAULT_STOCKS.keys()])
async def sell_cmd(i: discord.Interaction, coin: str, shares: int):
    global sell_earnings_date
    if shares <= 0:
        return await i.response.send_message("Invalid amount.", ephemeral=True)
    if coin in delisted_coins:
        return await i.response.send_message(f"💀 **{coin} is delisted!** Your shares were dissolved. Nothing to sell.", ephemeral=True)
        
    today = datetime.datetime.now(IST).date().isoformat()
    if sell_earnings_date != today:
        sell_earnings_date = today
        daily_sell_earnings.clear()
        save_data()
        
    current_shares = portfolios[i.user.id][coin].get("shares", 0)
    if current_shares <= 0:
        return await i.response.send_message(f"You don't have any shares of {coin}.", ephemeral=True)
    if current_shares < shares:
        return await i.response.send_message(f"You only have {current_shares} shares of {coin}.", ephemeral=True)
        
    if current_shares > MAX_SHARES_PER_COIN:
        ratio = MAX_SHARES_PER_COIN / current_shares
        portfolios[i.user.id][coin]["shares"] = MAX_SHARES_PER_COIN
        portfolios[i.user.id][coin]["invested"] = max(0.0, portfolios[i.user.id][coin].get("invested", 0.0) * ratio)
        current_shares = MAX_SHARES_PER_COIN
        shares = min(shares, current_shares)
        
    proportion = shares / current_shares
    invested_reduction = portfolios[i.user.id][coin].get("invested", 0.0) * proportion
    
    raw_revenue = stocks[coin] * shares
    fee = int(raw_revenue * 0.05)
    net_revenue = int(raw_revenue - fee)
    
    already_earned = daily_sell_earnings[i.user.id]
    remaining_cap = max(0, MAX_DAILY_SELL_EARNINGS - already_earned)
    if remaining_cap == 0:
        return await i.response.send_message(f"🛑 **Daily Sell Cap Reached!** You've earned {MAX_DAILY_SELL_EARNINGS:,} Aura today. Come back tomorrow!", ephemeral=True)
        
    capped = net_revenue > remaining_cap
    if capped:
        price_after_fee = stocks[coin] * 0.95
        shares_sellable = int(remaining_cap / price_after_fee) if price_after_fee > 0 else 0
        if shares_sellable == 0:
            return await i.response.send_message(f"🛑 Only **{remaining_cap:,} Aura** left in today's cap but 1 share costs **{int(price_after_fee):,} Aura**. Come back tomorrow!", ephemeral=True)
        shares = shares_sellable
        proportion = shares / current_shares
        invested_reduction = portfolios[i.user.id][coin].get("invested", 0.0) * proportion
        fee = int(stocks[coin] * shares * 0.05)
        net_revenue = int(stocks[coin] * shares - fee)
        
    portfolios[i.user.id][coin]["shares"] -= shares
    portfolios[i.user.id][coin]["invested"] = max(0.0, portfolios[i.user.id][coin].get("invested", 0.0) - invested_reduction)
    
    if portfolios[i.user.id][coin]["shares"] <= 0:
        portfolios[i.user.id][coin] = {"shares": 0, "invested": 0.0}
        
    daily_sell_earnings[i.user.id] += net_revenue
    balance[i.user.id] += net_revenue
    save_data()
    
    cap_note = f"\n⚠️ Cap hit — only sold **{shares} shares** (max payout today reached)." if capped else ""
    await i.response.send_message(f"📉 **SHARES SOLD**\nSold **{shares} {coin}**\nNet Return: **{net_revenue:,} Aura** *(After {fee:,} Aura broker fee)*.{cap_note}\n📊 Today's earnings: **{daily_sell_earnings[i.user.id]:,} / {MAX_DAILY_SELL_EARNINGS:,} Aura**")

@bot.tree.command(name="portfolio", description="View your current investments and P/L")
async def portfolio_cmd(i: discord.Interaction, user: Optional[discord.Member] = None):
    u = user or i.user
    holding = portfolios[u.id]
    if not holding or all(d.get("shares", 0) == 0 for d in holding.values()):
        return await i.response.send_message("Empty portfolio. Go `/invest`!", ephemeral=True)
        
    desc = ""
    total_net_value = 0
    total_invested = 0
    
    for coin, data_dict in holding.items():
        amt = data_dict.get("shares", 0)
        invested = data_dict.get("invested", 0.0)
        if amt > 0:
            net_val = (amt * stocks.get(coin, 0)) * 0.95
            total_net_value += net_val
            total_invested += invested
            pl = net_val - invested
            pl_pct = (pl / invested * 100) if invested > 0 else 0
            emoji = "🟢" if pl >= 0 else "🔴"
            desc += f"**{coin}**: {amt} shares @ {stocks.get(coin,0):.1f} Aura\n` ↳ P/L:` {emoji} **{int(pl):,}** ({pl_pct:+.1f}%)\n\n"

    total_pl = total_net_value - total_invested
    total_pl_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0
    
    embed = discord.Embed(title=f"📊 {u.display_name}'s Portfolio", description=desc, color=discord.Color.blurple())
    embed.add_field(name="Total Value", value=f"{int(total_net_value):,} Aura", inline=True)
    embed.add_field(name="Total P/L", value=f"{'🟢' if total_pl >= 0 else '🔴'} {int(total_pl):,} ({total_pl_pct:+.1f}%)", inline=True)
    await i.response.send_message(embed=embed)

    
@bot.tree.command(name="invite_event", description="Staff: Start or end the invite event")
@app_commands.describe(action="start or end")
@app_commands.choices(action=[
    app_commands.Choice(name="start", value="start"),
    app_commands.Choice(name="end", value="end"),
])
async def invite_event_cmd(i: discord.Interaction, action: str):
    global invite_event_active, invite_counts, invite_map, cached_invites
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)

    announce = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)

    if action == "start":
        if invite_event_active:
            return await i.response.send_message("Invite event is already running!", ephemeral=True)
        invite_event_active = True
        invite_counts.clear()
        invite_map.clear()
        for guild in bot.guilds:
            try:
                cached_invites[guild.id] = {inv.code: inv.uses for inv in await guild.invites()}
            except Exception:
                pass
        save_data()
        event_desc = (
            "**Invite your friends and earn rewards!**\n\n"
            "**How it works:**\n"
            "• Invite members to the server\n"
            "• Each valid invite = **20 Aura** at the end of the event\n"
            "• Invited member must stay until the event ends to count\n"
            "• If they leave before the event ends, the invite won't count\n"
            "• **Minimum 100 valid invites required to qualify for cash prizes**\n\n"
            "**Top Prizes:**\n"
            "🥇 1st — **$10**\n🥈 2nd — **$5**\n🥉 3rd & 4th — **$2**\n🏅 5th — **$1**\n\n"
            "**How to join:**\n"
            "• Go to Server Settings → Invites → Create a personal invite link\n"
            "• Use `/my_invites` to check your invite count anytime\n"
            "• Use `/leaderboard invites` to see the rankings\n\n"
            "Good luck everyone! 🚀"
        )
        embed = discord.Embed(
            title="🎉 Invite Event Started!",
            description=event_desc,
            color=discord.Color.green()
        )
        await i.channel.send(embed=embed)
        await i.response.send_message("✅ Invite event started!", ephemeral=True)

    elif action == "end":
        if not invite_event_active:
            return await i.response.send_message("No invite event is running!", ephemeral=True)
        invite_event_active = False
        save_data()

        sorted_inv = sorted(invite_counts.items(), key=lambda x: x[1], reverse=True)
        prizes = {0: "$10", 1: "$5", 2: "$2", 3: "$2", 4: "$1"}

        for uid, count in sorted_inv:
            if count > 0:
                balance[uid] += count * 20
        save_data()

        desc = "**Event has ended! Here are the final results:**\n\n"
        for idx, (uid, count) in enumerate(sorted_inv[:10]):
            member = i.guild.get_member(uid) if i.guild else None
            name = member.display_name if member else f"<@{uid}>"
            prize = prizes.get(idx, "")
            qualified = count >= 100
            prize_str = f" — **{prize}**" if prize and qualified else (" — *(needs 100+ invites for prize)*" if prize and not qualified else "")
            rank = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"][idx]
            desc += f"{rank} **{name}** — {count} invites (+{count*20} Aura){prize_str}\n"

        desc += "\n*Aura rewards have been distributed! Prize payouts handled by staff.*"
        embed = discord.Embed(title="🏆 Invite Event Results!", description=desc, color=discord.Color.gold())
        if announce:
            await announce.send(embed=embed)
        await i.response.send_message("✅ Invite event ended and rewards distributed!", ephemeral=True)

@bot.tree.command(name="my_invites", description="Check your invite count in the current event")
async def my_invites(i: discord.Interaction):
    if not invite_event_active:
        return await i.response.send_message("No invite event is currently running.", ephemeral=True)
    count = invite_counts[i.user.id]
    await i.response.send_message(
        f"📨 **{i.user.display_name}** has **{count} valid invite(s)** so far!\n"
        f"Aura at end of event: **{count * 20} Aura**"
    )


@bot.tree.command(name="close_all_tickets", description="Staff: Delete all tickets in the payment category")
async def close_all_tickets(i: discord.Interaction):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
    await i.response.defer(ephemeral=True)
    category = i.guild.get_channel(1448805721071292661)
    if not category or not isinstance(category, discord.CategoryChannel):
        return await i.followup.send("Payment category not found.", ephemeral=True)
    deleted = 0
    for channel in category.channels:
        try:
            await channel.delete(reason=f"Bulk close by {i.user.display_name}")
            deleted += 1
        except Exception as e:
            logging.error(f"Could not delete {channel.name}: {e}")
    await i.followup.send(f"✅ Closed and deleted **{deleted}** ticket(s).", ephemeral=True)




@bot.tree.command(name="roast", description="Roast someone (or yourself)")
async def roast(i: discord.Interaction, user: discord.Member):
    await i.response.defer()
    if user.id == bot.user.id:
        reply = await quick_ai(f"{i.user.display_name} tried to roast me, the bot. Roast them back harder. Funny, savage, short. 1-2 sentences. ALWAYS finish the sentence completely.", max_tokens=150)
        await i.followup.send(f"{i.user.mention} {reply if reply else 'Nice try 😂'}")
    elif user.id == i.user.id:
        reply = await quick_ai(f"Write a funny self-roast for someone named {i.user.display_name}. Short, savage but fun. 1-2 sentences. ALWAYS finish the sentence completely.", max_tokens=150)
        await i.followup.send(f"{i.user.mention} {reply if reply else roast_bag.get_next()}")
    else:
        reply = await quick_ai(f"Roast a Discord user named {user.display_name}. Requested by {i.user.display_name}. Funny, creative, not offensive. 1-2 sentences. ALWAYS finish the sentence completely.", max_tokens=150)
        await i.followup.send(f"{user.mention} {reply if reply else roast_bag.get_next()}")

@bot.tree.command(name="confess", description="Submit an anonymous confession")
async def confess(i: discord.Interaction, message: str):
    channel = bot.get_channel(CONFESSION_CHANNEL_ID)
    if not channel:
        return await i.response.send_message("Confession channel not found! Tell staff to check the config.", ephemeral=True)
        
    embed = discord.Embed(title="🕵️ Anonymous Confession", description=f'"{message}"', color=discord.Color.dark_theme())
    embed.set_footer(text="Submit yours using /confess or the button below")

    msg = await channel.send(embed=embed, view=ConfessionView())
    confession_authors[str(msg.id)] = i.user.id
    await i.response.send_message("✅ Your confession has been submitted anonymously!", ephemeral=True)

@bot.tree.command(name="poll", description="Create a Poll (Separate options with commas)")
async def create_poll(i: discord.Interaction, question: str, options: str):
    opts = [o.strip() for o in options.split(",") if o.strip()]
    
    if len(opts) < 2:
        return await i.response.send_message("Please provide at least 2 options separated by commas.", ephemeral=True)
    if len(opts) > 25:
        return await i.response.send_message("Discord limits buttons to 25 maximum.", ephemeral=True)
        
    poll_id = str(int(time.time() * 1000)) 
    
    polls[poll_id] = {
        "q": question,
        "opts": opts,
        "author_name": i.user.display_name,
        "author_icon": i.user.display_avatar.url if i.user.display_avatar else None,
        "votes": {}
    }
    
    save_data()
    view = PollView(poll_id)
    await i.response.send_message(embed=view.build_embed(), view=view)

async def end_giveaway(gid: str):
    g = giveaways.get(gid)
    if not g or g.get("ended"): 
        return
        
    g["ended"] = True
    save_data()
    channel = bot.get_channel(g["channel_id"])
    
    if not channel: 
        return
        
    if not g["participants"]: 
        return await channel.send(embed=simple_embed("Giveaway Ended", f"No one entered for **{g['prize']}**.", discord.Color.red()))
        
    winners = random.sample(g["participants"], min(len(g["participants"]), g["winners"]))
    g["previous_winners"] = winners
    save_data()
    mentions = ", ".join(f"<@{w}>" for w in winners)
    
    await channel.send(content=mentions, embed=discord.Embed(title=f"{E_PARTY} Winners Selected!", description=f"Prize: **{g['prize']}**\n\n👑 **Congratulations:**\n{mentions}", color=discord.Color.gold()))

async def schedule_end(gid: str, delay: float):
    await asyncio.sleep(delay)
    await end_giveaway(gid)

@bot.tree.command(name="giveaway", description="Start giveaway")
async def giveaway_start(i: discord.Interaction, prize: str, duration: str, winners: int = 1, role: Optional[discord.Role] = None, min_msgs: Optional[int] = None, min_bal: Optional[int] = None):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    d_sec = parse_duration(duration)
    if not d_sec: 
        return await i.response.send_message("Invalid duration (e.g., 10m, 1h).", ephemeral=True)
        
    global last_giveaway
    gid = str(int((time.time() + d_sec) * 1000))
    end_time = time.time() + d_sec
    
    giveaways[gid] = {
        "id": gid, 
        "prize": prize, 
        "host_id": i.user.id, 
        "channel_id": i.channel.id, 
        "participants": [], 
        "role_id": role.id if role else None, 
        "min_msgs": min_msgs, 
        "min_balance": min_bal, 
        "winners": winners, 
        "end_time": end_time, 
        "ended": False
    }
    
    last_giveaway = gid
    save_data()
    
    await i.response.send_message("Giveaway started!", ephemeral=True)
    await i.channel.send(embed=build_giveaway_embed(giveaways[gid], i.guild), view=GiveawayView(gid))
    
    bot.loop.create_task(schedule_end(gid, d_sec))

@bot.tree.command(name="reroll", description="Reroll giveaway")
async def reroll(i: discord.Interaction, giveaway_id: Optional[str] = None, winners: int = 1):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if giveaway_id:
        g = giveaways.get(giveaway_id)
    else:
        ended_giveaways = [v for v in giveaways.values() if v.get("channel_id") == i.channel.id and v.get("ended")]
        sorted_giveaways = sorted(ended_giveaways, key=lambda x: x["end_time"], reverse=True)
        g = next(iter(sorted_giveaways), None)
        
    if not g or not g["participants"]: 
        return await i.response.send_message("Invalid giveaway or no entries.", ephemeral=True)
        
    previous_winners = set(g.get("previous_winners", []))
    eligible = [p for p in g["participants"] if p not in previous_winners]

    if not eligible:
        return await i.response.send_message("No eligible participants left to reroll (all have already won).", ephemeral=True)

    wins = random.sample(eligible, min(winners, len(eligible)))
    g["previous_winners"] = list(previous_winners | set(wins))
    save_data()
    mentions = ", ".join(f"<@{w}>" for w in wins)
    
    await i.response.send_message(content=mentions, embed=simple_embed("🎲 Reroll!", f"New winner(s) for **{g['prize']}**!", discord.Color.gold()))

@bot.tree.command(name="end_giveaway", description="Staff: Instantly end the most recent active giveaway")
async def end_giveaway_now(i: discord.Interaction):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)

    active = [(gid, g) for gid, g in giveaways.items() if not g.get("ended")]
    if not active:
        return await i.response.send_message("No active giveaways running right now.", ephemeral=True)

    gid, g = min(active, key=lambda x: x[1]["end_time"])

    await i.response.send_message(f"⏩ Ending giveaway for **{g['prize']}** instantly...", ephemeral=True)
    await end_giveaway(gid)

GIVE_LOG_CHANNEL_ID = 1448767355449512037

@bot.tree.command(name="give", description="Staff: Give Aura to a user")
async def give(i: discord.Interaction, user: discord.Member, amount: int):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)

    before = balance[user.id]
    balance[user.id] += amount
    save_data()

    await i.response.send_message(f"Gave **{amount:,}** Aura to {user.mention}.")

    log_ch = bot.get_channel(GIVE_LOG_CHANNEL_ID)
    if log_ch:
        embed = discord.Embed(title="💸 Aura Given", color=discord.Color.green())
        embed.add_field(name="Staff", value=i.user.mention, inline=True)
        embed.add_field(name="Recipient", value=user.mention, inline=True)
        embed.add_field(name="Amount", value=f"**+{amount:,} Aura**", inline=True)
        embed.add_field(name="Balance Before", value=f"{before:,}", inline=True)
        embed.add_field(name="Balance After", value=f"{balance[user.id]:,}", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await log_ch.send(embed=embed)

@bot.tree.command(name="take", description="Staff: Take Aura from a user and keep it")
async def take(i: discord.Interaction, user: discord.Member, amount: int):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if amount <= 0: 
        return await i.response.send_message("Amount must be greater than 0.", ephemeral=True)

    before = balance[user.id]
    balance[user.id] -= amount
    balance[i.user.id] += amount
    save_data()

    await i.response.send_message(f"Seized **{amount:,}** Aura from {user.mention} and added it to your account! 💰")

    log_ch = bot.get_channel(GIVE_LOG_CHANNEL_ID)
    if log_ch:
        embed = discord.Embed(title="💰 Aura Taken", color=discord.Color.red())
        embed.add_field(name="Staff", value=i.user.mention, inline=True)
        embed.add_field(name="From", value=user.mention, inline=True)
        embed.add_field(name="Amount", value=f"**-{amount:,} Aura**", inline=True)
        embed.add_field(name="Balance Before", value=f"{before:,}", inline=True)
        embed.add_field(name="Balance After", value=f"{balance[user.id]:,}", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await log_ch.send(embed=embed)

@bot.tree.command(name="ban", description="Staff: Ban a user with optional message deletion")
@app_commands.choices(delete_history=[
    app_commands.Choice(name="Don't Delete Any Messages", value=0), 
    app_commands.Choice(name="Delete Previous 24 Hours", value=1), 
    app_commands.Choice(name="Delete Previous 7 Days", value=7)
])
async def ban_user(i: discord.Interaction, user: discord.Member, reason: str = "No reason provided", delete_history: int = 0):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if user.top_role >= i.user.top_role and i.user.id != i.guild.owner_id: 
        return await i.response.send_message("❌ You cannot ban someone with an equal or higher role.", ephemeral=True)
        
    try:
        try:
            embed_dm = discord.Embed(title="You have been banned", color=discord.Color.red())
            embed_dm.add_field(name="Server", value=i.guild.name, inline=True)
            embed_dm.add_field(name="Reason", value=reason, inline=True)
            await user.send(embed=embed_dm)
        except Exception:
            pass  # DMs closed, continue anyway
        await user.ban(reason=f"Banned by {i.user.display_name} - {reason}", delete_message_days=delete_history)
        await i.response.send_message(embed=discord.Embed(title="🔨 User Banned", description=f"**User:** {user.mention}\n**Reason:** {reason}\n**Deleted Msgs:** {delete_history} days", color=discord.Color.red()))
    except discord.Forbidden: 
        await i.response.send_message("❌ I do not have permission to ban this user.", ephemeral=True)
        
@bot.tree.command(name="force_market", description="Admin Only: Secretly nudge a coin's price towards a target over time")
@app_commands.choices(coin=[app_commands.Choice(name=c, value=c) for c in DEFAULT_STOCKS.keys()])
@app_commands.default_permissions(administrator=True) # Hides it from regular users in the menu
async def force_market(i: discord.Interaction, coin: str, target_price: float):
    ADMIN_ROLE_ID = 1448719741756768308
    has_admin_role = any(role.id == ADMIN_ROLE_ID for role in i.user.roles)
    
    if not has_admin_role:
        return await i.response.send_message("🛑 You do not have the required Admin role to use this command.", ephemeral=True)
        
    if target_price < 0:
        return await i.response.send_message("Target price cannot be negative.", ephemeral=True)
        
    force_market_targets[coin] = target_price
    
    await i.response.send_message(
        f"🤫 **Market Manipulated:** The invisible hand has been activated.\n"
        f"**{coin}** will now gradually gravitate towards **{target_price} Aura** over the next few hours.", 
        ephemeral=True
    )
    
@bot.tree.command(name="autokick_setup", description="Staff: Setup strict time-limit kick for a role")
async def autokick_setup(i: discord.Interaction, role: discord.Role, days: int):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if days < 2: 
        return await i.response.send_message("Days must be at least 2.", ephemeral=True)
        
    autokick_cfg["role_id"] = role.id
    autokick_cfg["days"] = days
    
    if "warned" not in autokick_cfg: 
        autokick_cfg["warned"] = []
        
    for m in role.members:
        if not m.bot and str(m.id) not in user_timers: 
            user_timers[str(m.id)] = time.time()
            
    save_data()
    await i.response.send_message(f"✅ Strict Time-limit auto-kick enabled!\nUsers given the {role.mention} role will be:\n⚠️ Warned after **{days/2}** days.\n👢 Kicked after **{days}** days.", ephemeral=True)

@bot.tree.command(name="autokick_disable", description="Staff: Disable the time-limit kicker")
async def autokick_disable(i: discord.Interaction):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    autokick_cfg["role_id"] = None
    save_data()
    await i.response.send_message("🛑 Auto-kicker disabled.", ephemeral=True)

@bot.tree.command(name="set_msg_reward", description="Staff: Change messages required to earn Aura")
async def set_msg_reward_cmd(i: discord.Interaction, messages_needed: int, aura_reward: int):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    global msg_threshold, msg_reward
    msg_threshold = messages_needed
    msg_reward = aura_reward
    save_data()
    
    await i.response.send_message(f"✅ Rules updated! Earn **{aura_reward} Aura** every **{messages_needed}** messages.", ephemeral=True)

@bot.tree.command(name="egg_add", description="Staff: Add a new easter egg phrase")
@app_commands.choices(tier=[
    app_commands.Choice(name="Hard (500 Aura)", value="hard"), 
    app_commands.Choice(name="Easy (100 Aura)", value="easy")
])
async def egg_add(i: discord.Interaction, tier: str, phrase: str):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    phrase = phrase.lower().strip() 
    
    if tier == "hard" and phrase not in hard_eggs: 
        hard_eggs.append(phrase)
        amt = 500
    elif phrase not in easy_eggs: 
        easy_eggs.append(phrase)
        amt = 100
        
    save_data()
    
    chat_channel = bot.get_channel(CHAT_CHANNEL_ID)
    if chat_channel: 
        await chat_channel.send(embed=discord.Embed(title="🥚 New Easter Egg Hidden!", description=f"A new **{tier.title()}** Easter Egg is hidden...\nFind it first to claim **{amt} Aura**! 🕵️‍♂️", color=discord.Color.gold()))
        
    await i.response.send_message(f"✅ Added `{phrase}` to the **{tier.upper()}** egg list.", ephemeral=True)

@bot.tree.command(name="egg_remove", description="Staff: Remove an easter egg phrase")
@app_commands.choices(tier=[
    app_commands.Choice(name="Hard (500 Aura)", value="hard"), 
    app_commands.Choice(name="Easy (100 Aura)", value="easy")
])
async def egg_remove(i: discord.Interaction, tier: str, phrase: str):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    phrase = phrase.lower().strip()
    
    try:
        if tier == "hard": 
            hard_eggs.remove(phrase)
        else: 
            easy_eggs.remove(phrase)
            
        save_data()
        await i.response.send_message(f"🗑️ Removed `{phrase}`.", ephemeral=True)
    except ValueError: 
        await i.response.send_message(f"❌ Could not find `{phrase}`.", ephemeral=True)

@bot.tree.command(name="egg_list", description="Staff: View all active easter eggs")
async def egg_list(i: discord.Interaction):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    embed = discord.Embed(title="🥚 Active Easter Eggs", color=discord.Color.gold())
    embed.add_field(name="Hard (500 Aura)", value=", ".join(f"`{e}`" for e in hard_eggs) or "None", inline=False)
    embed.add_field(name="Easy (100 Aura)", value=", ".join(f"`{e}`" for e in easy_eggs) or "None", inline=False)
    
    await i.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setup_birthday_panel", description="Staff: Deploys the persistent Birthday Panel")
async def setup_birthday_panel(i: discord.Interaction):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
    if not channel: 
        return await i.response.send_message("Invalid Birthday Channel ID.", ephemeral=True)
        
    embed = discord.Embed(title=f"🎂 Birthday Calendar", description=f"Click the button below to register your birthday!\n\n**On your birthday, you will receive:**\n👑 **Special Birthday Role** (24h)\n🎉 **Server-wide Wish**\n\n*Note: You can only set this once.*", color=discord.Color.fuchsia())
    embed.set_image(url="https://media.discordapp.net/attachments/1053423486078566571/111111111111111111/birthday_banner.png?width=1000&height=300")
    
    await channel.send(embed=embed, view=BirthdayPanelView())
    await i.response.send_message("Birthday Panel deployed!", ephemeral=True)

@bot.tree.command(name="resetbirthday", description="Staff: Reset a user's birthday")
async def resetbirthday(i: discord.Interaction, user: discord.Member):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    if user.id in birthdays:
        del birthdays[user.id]
        save_data()
        await i.response.send_message(f"✅ Reset birthday for {user.mention}.", ephemeral=True)
    else: 
        await i.response.send_message("User hasn't set a birthday yet.", ephemeral=True)
    
@bot.tree.command(name="test_birthdays", description="Staff: Force the midnight birthday check to run right now")
async def test_birthdays(i: discord.Interaction):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    await i.response.send_message("⚙️ Manually triggering the midnight birthday check...", ephemeral=True)
    await midnight_birthday_check.coro()

@bot.tree.command(name="assign", description="Staff: Assign role")
async def assign_role(i: discord.Interaction, user: discord.Member, role: discord.Role):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    try: 
        await user.add_roles(role)
        await i.response.send_message(f"✅ Added {role.mention} to {user.mention}.")
    except discord.Forbidden: 
        await i.response.send_message(f"❌ **Error:** I cannot assign this role!", ephemeral=True)

@bot.tree.command(name="unassign", description="Staff: Remove role")
async def unassign_role(i: discord.Interaction, user: discord.Member, role: discord.Role):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    try: 
        await user.remove_roles(role)
        await i.response.send_message(f"🗑️ Removed {role.mention} from {user.mention}.")
    except discord.Forbidden: 
        await i.response.send_message(f"❌ **Error:** I cannot remove this role!", ephemeral=True)

@bot.tree.command(name="list_role", description="Staff: List role members")
async def list_role(i: discord.Interaction, role: discord.Role):
    if not is_staff(i.user): 
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    await i.response.send_message(embed=discord.Embed(title=f"Audit: {role.name} ({len(role.members)})", description="\n".join([x.mention for x in role.members][:50]), color=discord.Color.blue()))

    

@bot.tree.command(name="verify", description="Staff: Verify ticket")
async def verify(i: discord.Interaction, user: discord.Member, role1: Optional[discord.Role]=None, role2: Optional[discord.Role]=None, role3: Optional[discord.Role]=None):
    if not is_staff(i.user) or not is_ticket_channel(i.channel): 
        return await i.response.send_message("Staff/Ticket channel only.", ephemeral=True)

    await i.response.defer()

    try:
        new_name = user.display_name[:100]
        await i.channel.edit(name=new_name)
        
        for rid in REMOVE_ROLE_IDS:
            r = i.guild.get_role(rid)
            if r and r in user.roles: 
                await user.remove_roles(r)
                
        roles_to_add = [i.guild.get_role(rid) for rid in AUTO_ROLE_IDS if i.guild.get_role(rid)]
        
        if role1: roles_to_add.append(role1)
        if role2: roles_to_add.append(role2)
        if role3: roles_to_add.append(role3)
            
        if roles_to_add: 
            await user.add_roles(*roles_to_add)
        
        formatted_ticket_name = new_name.lower().replace(" ", "-")
        desc = (f"**Welcome!** {user.mention}\nTo claim tasks, please send your ticket as soon as tasks are available.\n\n**📍 Where to send your ticket:**\n<#1450947408606269583>\n<#1450948163002302464>\n<#1450947898324947099>\n\n**Important points:**\n- Your ticket name is **#{formatted_ticket_name}**\n- Task channels are opened only when tasks are available\n\n{E_VIBE} **Time to earn!!!**")
        
        embed = discord.Embed(title=f"{E_SUCCESS} **VERIFIED** {E_SUCCESS}", description=desc, color=discord.Color.green())
        
        if roles_to_add: 
            embed.add_field(name="🛠 Assigned Roles", value=", ".join(r.mention for r in roles_to_add), inline=False)
            
        await i.followup.send(embed=embed)
        
    except discord.Forbidden:
        await i.followup.send("❌ **Error:** I don't have permission to edit this channel or add these roles! Ensure the bot's role is placed at the top of the hierarchy.", ephemeral=True)

@bot.tree.command(name="notfit", description="Staff: Deny ticket")
async def notfit(i: discord.Interaction, user: discord.Member):
    if not is_staff(i.user) or not is_ticket_channel(i.channel): 
        return await i.response.send_message("Staff/Ticket channel only.", ephemeral=True)
        
    await i.channel.edit(name=f"not fit-{user.display_name}"[:100])
    
    desc = (f"{user.mention}, sorry, you are not fit for doing tasks yet. Your account needs at least:\n- 100 karma\n- 20 comment karma\n- 1 month old\n- Moderate+ CQS\n\nYou are welcome to stay and apply again later!")
    await i.response.send_message(embed=discord.Embed(title=f"{E_WARN} Application Update", description=desc, color=discord.Color.red()))

@bot.tree.command(name="help", description="Show all available bot commands")
async def help_cmd(i: discord.Interaction):
    embed = discord.Embed(title=f"{E_VIBE} Command Menu", color=discord.Color.blurple())
    
    embed.add_field(name="🎰 Casino & Games", 
                    value="`/gamble`, `/bj`, `/french_roulette`, `/duel`, `/dice_duel`\n`/roulette`, `/draw`, `/escrow`", 
                    inline=False)
    
    embed.add_field(name="📈 Mod Coins (Market)", 
                    value="`/stocks`, `/coin_chart`, `/invest`, `/sell`, `/portfolio`, `/insider_tip`", 
                    inline=False)
    
    embed.add_field(name="💰 Economy & Social", 
                    value="`/bal`, `/daily`, `/withdraw`, `/gift`, `/remove_aura`, `/leaderboard`\n`/msgs`, `/my_invites`, `/roast`, `/confess`, `/poll`", 
                    inline=False)
    
    embed.add_field(name="🛠️ Staff (Economy & Events)", 
                    value="`/give`, `/take`, `/open_withdrawals`, `/close_withdrawals`, `/set_msg_reward`\n`/giveaway`, `/reroll`, `/end_giveaway`, `/invite_event`\n`/egg_add`, `/egg_remove`, `/egg_list`, `/force_recap`, `/force_puzzle`", 
                    inline=False)
    
    embed.add_field(name="🛡️ Staff (Moderation & Setup)", 
                    value="`/verify`, `/notfit`, `/ban`, `/assign`, `/unassign`, `/list_role`\n`/autokick_setup`, `/autokick_disable`, `/close_all_tickets`\n`/setup_birthday_panel`, `/resetbirthday`, `/test_birthdays`\n**Prefix Commands:** `!hardsync`, `!reshuffle_market`", 
                    inline=False)
    
    await i.response.send_message(embed=embed)


@bot.command()
async def hardsync(ctx):
    if not is_staff(ctx.author): 
        return await ctx.send("Staff only.")
        
    msg = await ctx.send("🔄 **Syncing commands...**\n1️⃣ Clearing guild-specific duplicates...")
    try:
        bot.tree.clear_commands(guild=ctx.guild)
        await bot.tree.sync(guild=ctx.guild)
        
        await msg.edit(content="🔄 **Syncing commands...**\n2️⃣ Pushing global commands...")
        await asyncio.sleep(1)
        
        synced = await bot.tree.sync()
        
        await msg.edit(content=f"✅ **SYNC COMPLETE!**\nSynced **{len(synced)}** global commands. Duplicates cleared.\n\n*(Press **Ctrl + R** to refresh Discord!)*")
    except Exception as e:
        await msg.edit(content=f"❌ **CRITICAL ERROR:** {e}")

@bot.command()
async def reshuffle_market(ctx):
    """Force a market personality reshuffle — one time only."""
    global personality_season
    if not is_staff(ctx.author):
        return await ctx.send("Staff only.")
    if personality_season > 0:
        return await ctx.send("❌ This command has already been used.")
    personality_season += 1
    save_data()
    await ctx.send(f"🔀 **Market reshuffled!** Coins have new personalities for today.")
    
@bot.tree.command(name="force_recap", description="Staff: Manually trigger the weekly recap right now")

async def force_recap(i: discord.Interaction):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
    
    await i.response.defer(ephemeral=True)
    ch = bot.get_channel(DAILY_ANNOUNCE_CHANNEL_ID)
    if not ch:
        return await i.followup.send("Announce channel not found.", ephemeral=True)

    top_earner_id = max(weekly_aura_earned, key=weekly_aura_earned.get) if weekly_aura_earned else None
    top_earner_name = ""
    if top_earner_id:
        for g in bot.guilds:
            m = g.get_member(top_earner_id)
            if m:
                top_earner_name = m.display_name
                break
        top_earner_name = top_earner_name or f"<@{top_earner_id}>"

    top_loser_id = max(weekly_casino_lost, key=weekly_casino_lost.get) if weekly_casino_lost else None
    top_loser_name = ""
    if top_loser_id:
        for g in bot.guilds:
            m = g.get_member(top_loser_id)
            if m:
                top_loser_name = m.display_name
                break
        top_loser_name = top_loser_name or f"<@{top_loser_id}>"

    best_stock = max(stocks, key=stocks.get) if stocks else "None"
    worst_stock = min(stocks, key=stocks.get) if stocks else "None"

    prompt = (
        f"Write a fun weekly server recap for a Discord economy server. "
        f"Top Aura earner this week: {top_earner_name} with {weekly_aura_earned.get(top_earner_id, 0):,} Aura. "
        f"Biggest casino loser: {top_loser_name} lost {weekly_casino_lost.get(top_loser_id, 0):,} Aura. "
        f"Highest priced stock: {best_stock} at {stocks.get(best_stock, 0):.1f} Aura. "
        f"Lowest priced stock: {worst_stock} at {stocks.get(worst_stock, 0):.1f} Aura. "
        f"Be funny, engaging, like a sports commentator. 4 sentences max."
    )
    recap = await quick_ai(prompt, max_tokens=600)

    embed = discord.Embed(
        title="📊 Weekly Server Recap",
        description=recap or "Another week in the books! Check the leaderboard to see where you stand.",
        color=discord.Color.blurple()
    )
    if top_earner_id:
        embed.add_field(name="💰 Top Earner", value=f"{top_earner_name} — +{weekly_aura_earned.get(top_earner_id,0):,} Aura", inline=True)
    if top_loser_id:
        embed.add_field(name="🎰 Biggest Gambler", value=f"{top_loser_name} — lost {weekly_casino_lost.get(top_loser_id,0):,} Aura", inline=True)
    
    if stocks:
        embed.add_field(name="📈 Hot Stock", value=f"{best_stock} @ {stocks.get(best_stock, 0):.1f}", inline=True)
        embed.add_field(name="📉 Cold Stock", value=f"{worst_stock} @ {stocks.get(worst_stock, 0):.1f}", inline=True)
    
    embed.set_footer(text="Keep grinding 💪")

    await ch.send(embed=embed)
    await i.followup.send("✅ Weekly recap forced and sent to the announce channel!", ephemeral=True)

@bot.tree.command(name="force_puzzle", description="Staff: Instantly drop a chat puzzle")
async def force_puzzle_cmd(i: discord.Interaction):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    channel = bot.get_channel(CHAT_CHANNEL_ID)
    if not channel:
        return await i.response.send_message("Chat channel not found.", ephemeral=True)
        
    available = [p for p in PUZZLES if p["a"] not in used_puzzles]
    if not available:
        used_puzzles.clear()
        available = list(PUZZLES)
        
    puzzle = random.choice(available)
    used_puzzles.append(puzzle["a"])
    
    active_puzzle["question"] = puzzle["q"]
    active_puzzle["answer"] = puzzle["a"]
    active_puzzle["type"] = puzzle.get("type", "riddle")
    active_puzzle["solved"] = False
    save_data()
    
    ptype = active_puzzle["type"]
    type_config = {
        "riddle":    ("🧩", "Riddle",            discord.Color.purple(),  "Think carefully and type your answer!"),
        "scramble":  ("🔀", "Word Scramble",      discord.Color.orange(),  "Unscramble the letters to find the word!"),
        "math":      ("🔢", "Math Challenge",     discord.Color.blue(),    "Type just the number as your answer!"),
        "trivia":    ("🎯", "Trivia Question",    discord.Color.gold(),    "Type your answer in chat!"),
        "emoji":     ("🎭", "Emoji Puzzle",       discord.Color.fuchsia(), "Decode the emojis and type what it represents!"),
        "fillblank": ("✏️", "Fill in the Blank",  discord.Color.green(),   "Type the missing word to complete the phrase!"),
    }
    emoji_icon, type_name, color, hint = type_config.get(ptype, ("🧩", "Puzzle", discord.Color.purple(), "Type your answer!"))
    
    embed = discord.Embed(
        title=f"{emoji_icon} {type_name} — First to answer wins 50 Aura!",
        description=f"**{puzzle['q']}**\n\n*{hint}*",
        color=color
    )
    embed.set_footer(text=f"⚙️ Forced by Staff  •  Type: {type_name}")
    
    await channel.send(embed=embed)
    await i.response.send_message("✅ Puzzle forced into the chat!", ephemeral=True)
    
bot.run(TOKEN)
