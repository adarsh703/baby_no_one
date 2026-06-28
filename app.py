import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import logging
import asyncio
import aiohttp
import random
import time
import datetime
import math
from datetime import timedelta
from dotenv import load_dotenv
from collections import defaultdict, deque
from typing import Optional
from google import genai
from google.genai import types
import gspread
import requests
import uuid
from discord.ext import tasks
import re
import urllib.parse



load_dotenv(dotenv_path="env")    # local dev file named 'env'
load_dotenv(dotenv_path=".env")   # server/hosting panel file named '.env'
load_dotenv()                     # fallback: auto-detect
# ==========================================

# INTERACTIVE LEADERBOARD PAGINATOR
# ==========================================
class LeaderboardView(discord.ui.View):
    def __init__(self, data_list, guild, label, emoji, user, per_page=10):
        super().__init__(timeout=180) # Buttons disable after 3 minutes
        self.data_list = data_list
        self.guild = guild
        self.label = label
        self.emoji = emoji
        self.user = user
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = max(1, math.ceil(len(self.data_list) / self.per_page))
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1

    def generate_embed(self):
        embed = discord.Embed(
            title=f"🏆 Server Leaderboard | {self.label}", 
            color=discord.Color.gold()
        )
        
        if self.guild and self.guild.icon: 
            embed.set_thumbnail(url=self.guild.icon.url)

        # Grab the right slice of data for the current page
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_data = self.data_list[start_idx:end_idx]
        
        desc = ""
        for idx, (u, v) in enumerate(page_data):
            actual_rank = start_idx + idx + 1
            
            if actual_rank == 1: rank_str = "🥇"
            elif actual_rank == 2: rank_str = "🥈"
            elif actual_rank == 3: rank_str = "🥉"
            else: rank_str = f"` #{actual_rank} `"

            # Lookup member name dynamically
            member = self.guild.get_member(int(u)) if self.guild else None
            name = member.display_name if member else f"<@{u}>"
            desc += f"{rank_str} {name} — **{int(v):,}** {self.emoji}\n\n"
            
        embed.description = desc or "No data available."
        embed.set_footer(
            text=f"Page {self.current_page + 1} of {self.max_pages} • Total: {len(self.data_list)} | Requested by {self.user.display_name}", 
            icon_url=self.user.display_avatar.url
        )
        
        return embed

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ You can't flip pages on someone else's leaderboard!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ You can't flip pages on someone else's leaderboard!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)
# ==========================================
# REMINDER SYSTEM ENGINE
# ==========================================
REMINDERS_FILE = "reminders.json"

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_reminders(data):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

reminders_db = load_reminders()

@tasks.loop(minutes=1)
async def master_reminder_loop():
    # Define India Standard Time (UTC + 5 hours 30 mins)
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(IST)
    
    # %H:%M forces strict 24-hour format (e.g., "14:00" or "09:30")
    current_time = now.strftime("%H:%M")
    current_day_name = now.strftime("%A").lower()
    current_date_num = str(now.day)
    
    for rem_id, data in list(reminders_db.items()):
        if data['time'] == current_time:
            should_send = False
            
            # Check if it matches the Weekly or Monthly criteria
            if data['freq'] == 'weekly' and data['day_or_date'].lower() == current_day_name:
                should_send = True
            elif data['freq'] == 'monthly' and data['day_or_date'] == current_date_num:
                should_send = True
                
            if should_send:
                channel = bot.get_channel(data['channel'])
                if channel:
                    try:
                        # Determine the exact title without emojis
                        if data['freq'] == 'weekly':
                            header = "Weekly Reminder"
                        else:
                            header = "Monthly Reminder"
                            
                        # Format as a standard text message so pings work perfectly
                        final_message = f"**{header}**\n{data['message']}"
                        
                        # Send as plain text, no embed
                        await channel.send(content=final_message)
                        
                    except Exception as e:
                        print(f"Could not send reminder: {e}")
# ==========================================
# GOOGLE SHEETS SETUP 
# ==========================================
print("🔄 Attempting to connect to Google Sheets...")
try:
    gc = gspread.service_account(filename="gcp-key.json")
    print("✅ Google Sheets connected successfully!")
except Exception as e:
    gc = None
    print(f"🚨 CRITICAL ERROR: Could not connect to Google Sheets! Reason: {e}")

# --- 1. NEW REDDIT API FUNCTIONS ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = "linux:MyDiscordBot:v1.0 (by /u/Dizzy_Sensee)"

from bs4 import BeautifulSoup 

async def get_reddit_token():
    auth = aiohttp.BasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
    data = {'grant_type': 'client_credentials'}
    headers = {'User-Agent': USER_AGENT}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://www.reddit.com/api/v1/access_token', auth=auth, data=data, headers=headers) as resp:
            if resp.status == 200:
                token_data = await resp.json()
                return token_data.get('access_token')
            return None

async def verify_reddit_post(url: str, token: str):
    headers = {
        'Authorization': f'Bearer {token}', 
        'User-Agent': USER_AGENT
    }

    # 1. Handle redirects for /s/ mobile links and resolve the actual URL
    try:
        async with aiohttp.ClientSession() as session:
            # The headers are passed here so Reddit lets the bot through!
            async with session.get(url, headers=headers, allow_redirects=True, timeout=7) as resp:
                final_url = str(resp.url)
    except Exception as e:
        print(f"DEBUG: Failed to unwrap link: {e}")
        return "Failed"

    if "comments/" not in final_url:
        return "Invalid Link"

    # 2. Smart ID Extraction: Determine if this is a Post OR a Comment
    try:
        parts = final_url.split('/comments/')[1].split('/')
        post_id = parts[0].split('?')[0]
        comment_id = None
        
        # A standard comment URL looks like: .../comments/post_id/title/comment_id/
        if len(parts) >= 3 and parts[2] and '?' not in parts[2]:
            comment_id = parts[2].split('?')[0]
            
        # Target t1_ (Comment) if it exists, otherwise fallback to t3_ (Post)
        target_id = f"t1_{comment_id}" if comment_id else f"t3_{post_id}"
    except Exception:
        return "Invalid Link"
        
    api_url = f"https://oauth.reddit.com/api/info/?id={target_id}"
    
    # 3. Read the Data from Reddit
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 429: return "Rate Limited"
                if resp.status != 200: return "API Error"
                
                data = await resp.json()
                children = data.get('data', {}).get('children', [])
                if not children: return "Deleted"
                
                item_data = children[0]['data']
                
                # 4. Advanced Classification Variables
                author = item_data.get('author')
                body = item_data.get('body', '')
                selftext = item_data.get('selftext', '')
                removed_category = item_data.get('removed_by_category')
                is_indexable = item_data.get('is_robot_indexable', True)
                banned_by = item_data.get('banned_by')
                spam = item_data.get('spam', False)
                
                # A. Deleted by User
                if author == '[deleted]' or removed_category in ['deleted', 'author']:
                    return "Deleted"
                    
                # B. Explicitly Filtered (Reddit's Automated Systems & Spam Filters)
                if removed_category in ['reddit', 'automod_filtered', 'anti_evil_ops'] or spam is True or banned_by is True:
                    return "Filtered"
                    
                # C. Explicitly Removed by a Human Moderator
                if removed_category == 'moderator' or (isinstance(banned_by, str) and str(banned_by).lower() not in ['true', 'false']):
                    return "Mod Removed"
                    
                # D. The "[removed]" Text Fallback (When Reddit's API hides the tags)
                if body == '[removed]' or selftext == '[removed]':
                    # If a COMMENT is [removed] but has no tags, it was killed by a Moderator
                    if target_id.startswith('t1_'):
                        return "Mod Removed"
                    # If a POST is [removed] but has no tags, it was killed by Automod/Spam filters
                    else:
                        return "Filtered"
                        
                # E. Fallback for Posts: Not indexable usually means awaiting mod approval or shadow-removed
                if target_id.startswith('t3_') and not is_indexable:
                    return "Filtered"
                    
                return "Active"
            
    except Exception as e:
        print(f"DEBUG API ERROR: {e}")
        return "Failed"


async def get_reddit_user_info(username: str, token: str) -> dict | None:
    """Fetch Reddit account age (days) and total karma for a given username."""
    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': USER_AGENT
    }
    api_url = f"https://oauth.reddit.com/user/{username}/about"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 404:
                    return None  # User doesn't exist
                if resp.status != 200:
                    return None
                data = await resp.json()
                user_data = data.get('data', {})
                created_utc = user_data.get('created_utc', 0)
                link_karma = user_data.get('link_karma', 0)
                comment_karma = user_data.get('comment_karma', 0)
                total_karma = link_karma + comment_karma
                account_age_days = (time.time() - created_utc) / 86400 if created_utc else 0
                is_suspended = user_data.get('is_suspended', False)
                return {
                    "username": user_data.get('name', username),
                    "karma": total_karma,
                    "link_karma": link_karma,
                    "comment_karma": comment_karma,
                    "age_days": account_age_days,
                    "suspended": is_suspended
                }
    except Exception as e:
        print(f"DEBUG Reddit user info error: {e}")
        return None

async def fetch_cqs_score(cqs_url: str, token: str = None) -> float | None:
    """
    Reads a Reddit post/comment URL from r/WhatIsMyCQS (or similar) where
    AutoMod replied with the user's CQS tier. Extracts the tier word and maps it
    to a numeric value: Highest=100, High=75, Moderate=50, Low=25, Lowest=10.

    Returns a float or None if the tier can't be determined.
    """
    CQS_TIERS = {
        "highest": 100.0,
        "high":     75.0,
        "moderate": 50.0,
        "low":      25.0,
        "lowest":   10.0,
    }

    # If no token given, get one now
    if not token:
        token = await get_reddit_token()
    if not token:
        return None

    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': USER_AGENT
    }

    # ── Resolve the URL to get the post/comment ID ──
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(cqs_url, headers=headers, allow_redirects=True,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                final_url = str(resp.url)
    except Exception as e:
        print(f"DEBUG CQS URL resolve error: {e}")
        return None

    if "comments/" not in final_url:
        return None

    # ── Extract post ID ──
    try:
        post_id = final_url.split("/comments/")[1].split("/")[0].split("?")[0]
    except Exception:
        return None

    # ── Fetch all comments on the post via Reddit JSON API ──
    json_url = f"https://oauth.reddit.com/comments/{post_id}?limit=50&depth=5"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(json_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception as e:
        print(f"DEBUG CQS fetch error: {e}")
        return None

    # ── Extract tier from a single comment body ──
    def extract_tier_from_text(body: str):
        """
        Extracts CQS tier from AutoMod reply text.
        AutoMod format: "Your current CQS is HIGH."
        Returns the numeric value for the tier, or None.
        """
        if not body:
            return None

        TIER_NAMES = list(CQS_TIERS.keys())  # highest, high, moderate, low, lowest

        # Pass 1 — exact AutoMod phrase: "Your current CQS is **HIGH**."
        match = re.search(
            r'your\s+current\s+CQS\s+is\s+[*_]*(\w+)',
            body, re.IGNORECASE
        )
        if match:
            word = match.group(1).lower()
            if word in CQS_TIERS:
                return CQS_TIERS[word]

        # Pass 2 — broader CQS context: "CQS is HIGH" / "CQS: Moderate"
        match = re.search(
            r'CQS\s*(?:is|:)\s*[*_]*(\w+)',
            body, re.IGNORECASE
        )
        if match:
            word = match.group(1).lower()
            if word in CQS_TIERS:
                return CQS_TIERS[word]

        # Pass 3 — last resort: standalone tier word on its own line
        for line in body.splitlines():
            line = line.strip().rstrip('.').lower()
            if line in TIER_NAMES:
                return CQS_TIERS[line]

        return None


    # ── Walk all comments looking for a bot reply with a tier ──
    def walk_comments(listing):
        if not isinstance(listing, dict):
            return None
        children = listing.get("data", {}).get("children", [])
        for child in children:
            body = child.get("data", {}).get("body", "")
            result = extract_tier_from_text(body)
            if result is not None:
                return result
            # Recurse into replies
            replies = child.get("data", {}).get("replies", {})
            result = walk_comments(replies)
            if result is not None:
                return result
        return None

    # data is a list: [post_listing, comments_listing]
    if isinstance(data, list) and len(data) >= 2:
        score = walk_comments(data[1])
        if score is not None:
            return score

    # Also check post selftext as a last resort
    try:
        selftext = data[0]["data"]["children"][0]["data"].get("selftext", "")
        result = extract_tier_from_text(selftext)
        if result is not None:
            return result
    except Exception:
        pass

    return None


def extract_reddit_username_from_url(url: str) -> str | None:
    """Extract Reddit username from a profile URL like https://reddit.com/user/username"""
    url = url.strip().rstrip('/')
    patterns = [
        r'reddit\.com/u(?:ser)?/([A-Za-z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def classify_cqs(score: float | None) -> str:
    """Map a numeric CQS score to a category label."""
    if score is None:
        return "unknown"
    if score >= 90:
        return "highest"   # Highest CQS
    elif score >= 70:
        return "high"      # High CQS
    elif score >= 50:
        return "moderate"  # Mod CQS
    else:
        return "low"       # Low CQS

# ================== ENV & LOGGING ==================


# Use your Project ID from the screenshot
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
AI_SYSTEM = r"""You are baby_no_one, the bot of this Discord server. Smart, bully, chill, a bit witty. You feel like a real member, not a robot.

RESPONSE RULES:
- FOCUS: Stay on topic. Do not say random, irrelevant, or hallucinatory things. Keep it natural but grounded.
- HALLUCINATION PREVENTION: If you don't know something, admit it. Do not make up facts, commands, or channel names. Answer strictly based on the provided context.
- AURA & STOCKS: NEVER talk about Aura, stocks, economy, or money unless the user EXPLICITLY asks about them.
- NEWBIES & VERIFICATION: If a user is new or asks how to get started, warmly welcome them. If they are not verified, guide them to open a ticket in the ticket channel to get verified. Tell them to read the rules.
- CRITICAL KNOWLEDGE - SERVER TASKS:
- IF A USER ASKS ABOUT TASKS (e.g., "how to do tasks", "where are tasks"): You MUST tell them the exact workflow.
- Step 1: Tell them to get verified by creating a ticket in the ticket channel.
- Step 2: Tell them that once verified, tasks are posted in the task channels like <#1518207367941193972> and <#1518207420487172156> and <#1518207461650202755>.
- NEVER make up or hallucinate channel names. Only use the exact channels listed here.
- CRITICAL FORMATTING: NEVER use LaTeX, math blocks, or symbols like \(, \), \[, \], or $. Write all numbers, percentages, and currencies in plain standard text (e.g., "100 Aura", "10 percent", "1 million"). If you use math formatting, the system will crash.
- IF ASKED FOR A JOKE: NEVER use standard/classic internet dad jokes. Make up something completely unhinged and sarcastic.
- NEVER start your reply with "baby_no_one:" — just reply directly.
- SHORT replies always. Max 1-2 sentences for most things. Only go longer if someone asks for a detailed explanation.
- Don't over-explain. Get to the point fast.
- Do the math if asked (show brief working).
- Use display names (e.g. "Ahmed") NOT Discord pings when referring to people in chat.
- Match language: Hindi/Hinglish in → Hindi/Hinglish out. English in → English out.
- CRITICAL EMOJI RULE: The ONLY valid emoji formats are: actual Unicode characters (😊 🔥 💀) OR <:name:id> for server custom emojis. NEVER EVER type :anything: with colons — it shows as plain text. If you want to use a server emoji, copy the EXACT format from the list provided.
- Prefer server custom emojis from the list provided. Never use 😉.
- NEVER mention or comment on anyone's profile picture unless they specifically ask.
- GROUP CHAT: messages are labeled "Name: message". Know who said what. Address only the person who @mentioned you in your reply, unless the question involves others. Always check the recent messages context to understand what the user is referring to.
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
            ch = guild.get_channel(CHAT_CHANNEL_ID) if guild else bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
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


BALANCE_MILESTONES = [1000, 5000, 10000, 25000, 50000, 100000]

async def check_balance_milestone(uid: int, old_bal: int, new_bal: int):
    for milestone in BALANCE_MILESTONES:
        if old_bal < milestone <= new_bal:
            ch = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
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
    """Uses Gemini to intelligently parse any natural language reminder."""
    import json
    
    lower = message.lower()
    reminder_keywords = ["remind", "reminder", "याद", "alarm", "ping", "bata", "notify", "wake", "alert", "tag"]
    if not any(k in lower for k in reminder_keywords):
        return None

    now_ts = time.time()
    now_dt = datetime.datetime.now(IST)
    
    # Try regex first for simple cases (extremely fast and perfectly reliable)
    fire_time = None
    minutes = 0
    rel = re.search(r'(?:in|after|baad)\s+(a|an|one|\d+)\s*(sec|second|seconds|min|minute|minutes|hour|hours|hr|hrs|day|days|ghante|ghanta)', lower)
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
        tm = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', lower)
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
            
    text = ""
    # Use AI for extraction if regex failed OR just for getting the clean text
    prompt = f"""
    You are a reminder extraction bot. The user wants to set a reminder.
    Current time: {now_dt.strftime('%Y-%m-%d %I:%M %p')} IST
    User message: "{message}"

    Extract the reminder and return ONLY a JSON object with two keys:
    - "minutes": The number of minutes from now to set the reminder (integer). Calculate this based on the time they mentioned. If they just say "remind me to..." without a time, use 60.
    - "text": The clean reminder message to send them (string). Remove words like "remind me to" or the time. Keep only what they actually want to be reminded about. If there is no specific message (e.g. they just said "ping me in 5 mins"), return "ping".
    If the message is NOT a reminder request, return {{"minutes": -1, "text": ""}}.
    NOTE: Even if the message looks like a casual chat (e.g., "@bot ping me at 4pm"), it IS a reminder request. Treat it as one!
    """
    
    try:
        response = await vertex_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=150,
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            text_resp = match.group(0)
        else:
            text_resp = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            
        data = json.loads(text_resp)
        ai_minutes = int(float(data.get("minutes", -1)))
        text = str(data.get("text", "")).strip()
        
        if not fire_time and ai_minutes > 0:
            minutes = ai_minutes
            fire_time = now_ts + (minutes * 60)
            
    except Exception as e:
        logging.error(f"Reminder AI Error: {e}")
        
    if not fire_time:
        return None
        
    if not text or text.lower() in ["none", "null", ""]:
        # Fallback text cleaner if AI failed
        text = re.sub(r'<@!?\d+>', '', message)
        text = re.sub(r'\b(?:remind|reminder|ping|alarm|wake|notify)\s*(?:me\s*)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'((?:in|after|baad)\s+(?:a|an|one|\d+)\s*(?:min\w*|hour\w*|hr\w*|day\w*|sec\w*|ghante?)|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:to|about|that|ke baad|baad mein|bata dena|bata de)\b', '', text, flags=re.IGNORECASE).strip(" ,-:")
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
        
    if member and hasattr(member, "guild") and member.guild:
        guild_id_str = str(member.guild.id)
        if guild_id_str not in premium_guilds and member.guild.owner_id != 992008865656868946:
            return "💎 **Premium Feature**\nThis server has not unlocked AI Chat. The server owner must upgrade to Premium to use this feature!"


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

    # Only feed the AI stock and balance info if the user brings it up
    eco_keywords = ["aura", "stock", "market", "price", "portfolio", "balance", "coin", "rich", "poor", "money", "buy", "sell", "invest"]
    needs_economy = any(kw in user_message.lower() for kw in eco_keywords)
    
    user_context = f"\n\n[User info for {username}]"
    if needs_economy:
        user_bal = balance.get(user_id, 0)
        user_streak = daily_streak.get(user_id, 0)
        stock_prices = ", ".join(f"{c}: {v:.1f}" for c, v in stocks.items())
        user_context += f"\nAura balance: {user_bal:,}\nDaily streak: {user_streak} days\nCurrent stock prices: {stock_prices}"

    channel_knowledge_str = ""
    if server_channel_knowledge:
        sections = [f"[#{ch_name}]\n{content}" for ch_name, content in server_channel_knowledge.items()]
        channel_knowledge_str = "\n\n[Server Knowledge]\n" + "\n\n".join(sections)

    mem_str = ""
    if user_id in user_persistent_memory and user_persistent_memory[user_id]:
        mem_str = "\n\n[Memory]\n" + "\n".join(f"- {f}" for f in user_persistent_memory[user_id][-20:])

    guild_id = member.guild.id if member and hasattr(member, "guild") and member.guild else None
    if not guild_id and channel_id:
        ch = bot.get_channel(channel_id)
        if ch and hasattr(ch, "guild"):
            guild_id = ch.guild.id
    
    custom_system = get_config(guild_id, "AI_PROMPT") if guild_id else AI_SYSTEM
    if not custom_system:
        # Give the main server the OG prompt, but give other servers a generic default prompt
        from app import get_main_guild_id
        if guild_id and get_main_guild_id() and guild_id != get_main_guild_id():
            custom_system = "You are a fun, witty, and helpful Discord bot. Keep your answers conversational, natural, and concise."
        else:
            custom_system = AI_SYSTEM
        
    system_with_context = custom_system + (f"\n\n{server_custom_emojis}" if server_custom_emojis else "") + user_context + mem_str + channel_knowledge_str + context_str

    # --- NEW IMAGE LOGIC HERE ---
    request_contents = [f"{username}: {user_message}"]

    if avatar_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        mime_type = resp.headers.get("Content-Type", "image/png").split(";")[0]
                        # Add the image bytes to the request
                        request_contents.insert(0, types.Part.from_bytes(data=img_data, mime_type=mime_type))
        except Exception as e:
            logging.error(f"Failed to fetch avatar: {e}")

    try:
        response = await vertex_client.aio.models.generate_content(
            model="gemini-2.5-flash", 
            contents=request_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_with_context,
                max_output_tokens=2000,
                temperature=0.4
            )
        )
        
        # Safely extract and aggressively strip Discord-breaking math markdown
        reply = response.text if response.text else ""
        reply = reply.replace(r"\(", "").replace(r"\)", "").replace(r"\[", "").replace(r"\]", "")
        reply = reply.replace("$", "\\$").strip()
        
        if channel_id and reply:
            ai_conversation_history[channel_id].append({"role": "model", "content": reply})
        return reply

    except Exception as e:
        logging.error(f"Vertex AI Error: {e}")
        return None



async def quick_ai(prompt: str, max_tokens: int = 400) -> str:
    if max_tokens < 400:
        max_tokens = 400
    try:
        response = await vertex_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=AI_SYSTEM,
                max_output_tokens=max_tokens,
                temperature=0.4
            )
        )
        
        # Safely extract text and aggressively strip Discord-breaking math markdown
        text = response.text if response.text else ""
        text = text.replace(r"\(", "").replace(r"\)", "").replace(r"\[", "").replace(r"\]", "")
        text = text.replace("$", "\\$").strip()
        return text
        
    except Exception as e:
        logging.error(f"Vertex quick_ai error: {e}")
        return ""


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN missing in .env")

logging.basicConfig(level=logging.INFO)

# ================== CONFIGURATION ==================
CHAT_CHANNEL_ID = 1518214909618290790
CHAT_CHANNEL_ID_2 = 1478785863126089759
PAYOUT_CHANNEL_ID = 1449908271937753129
DAILY_ANNOUNCE_CHANNEL_ID = 1448748624375972075
PUBLIC_LOG_CHANNEL_ID = 1448767223781916844 
AUTOKICK_WARN_CHANNEL_ID = 1453059081127592130
HELP_CHANNEL_ID = 1448787031810642010
CONFESSION_CHANNEL_ID = 1475013891258974349 

# --- BIRTHDAY CONFIG ---
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

# ================== FULL RESPONSES & ROASTS ==================
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

# ================== DATA MANAGEMENT ==================
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
        "personality_season": 0,
        "vc_total_minutes": {},
        "vc_milestones_reached": {},
        "server_configs": {}
    }

data = load_data()
# Bags loaded after SmartRandomizer class is defined below
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
w_until_str = data.get("withdrawal_open_until")
if w_until_str:
    try:
        withdrawal_open_until = datetime.datetime.fromisoformat(w_until_str)
    except Exception:
        withdrawal_open_until = None
else:
    withdrawal_open_until = None
pending_aura_requests = {}  # message_id -> {requester, channel_id}
ai_conversation_history = {}  # user_id -> list of {role, content}
balance_milestones_announced = set(data.get("balance_milestones_announced", []))
casino_losses = defaultdict(int, {int(k): v for k, v in data.get("casino_losses", {}).items()})
casino_wins = defaultdict(int, {int(k): v for k, v in data.get("casino_wins", {}).items()})
weekly_stock_start = data.get("weekly_stock_start", {})
last_mood_check = None
weekly_aura_earned = defaultdict(int, {int(k): v for k, v in data.get("weekly_aura_earned", {}).items()})
weekly_casino_lost = defaultdict(int, {int(k): v for k, v in data.get("weekly_casino_lost", {}).items()})
weekly_start_balance = {}               # uid -> balance at week start
channel_chat_log = {}  # channel_id -> deque of recent messages
server_channel_knowledge = {}  # channel_name -> content
server_custom_emojis = ""
user_persistent_memory = {}  # user_id -> list of key facts  # formatted emoji list for AI prompt
delisted_coins = data.get("delisted_coins", {})
user_persistent_memory = {int(k): v for k, v in data.get("user_persistent_memory", {}).items()}
last_message_times = data.get("last_message_times", {})
pending_reminders = data.get("pending_reminders", [])  # list of {user_id, channel_id, message, time}
invite_event_active = data.get("invite_event_active", False)
invite_counts = defaultdict(int, {int(k): v for k, v in data.get("invite_counts", {}).items()})  # inviter_id -> valid invite count
invite_map = data.get("invite_map", {})  # invited_user_id (str) -> inviter_id
server_configs = data.get("server_configs", {})
premium_guilds = data.get("premium_guilds", [])
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
                "vc_total_minutes": dict(vc_total_minutes),
                "vc_milestones_reached": vc_milestones_reached,
                "yo_bag": yo_bag.bag,
                "roast_bag": roast_bag.bag,
                "withdrawal_open_until": withdrawal_open_until.isoformat() if withdrawal_open_until else None,
                "delisted_coins": delisted_coins,
                "user_persistent_memory": {str(k): v for k, v in user_persistent_memory.items()},
                "last_message_times": dict(last_message_times),
                "pending_reminders": pending_reminders,
                "balance_milestones_announced": list(balance_milestones_announced),
                "casino_losses": dict(casino_losses),
                "casino_wins": dict(casino_wins),
                "weekly_aura_earned": dict(weekly_aura_earned),
                "weekly_casino_lost": dict(weekly_casino_lost),
                "weekly_stock_start": weekly_stock_start,
                "invite_event_active": invite_event_active,
                "invite_counts": dict(invite_counts),
                "invite_map": invite_map,
                "server_configs": server_configs,
                "premium_guilds": premium_guilds
            }, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving data: {e}")

# ================== HELPERS & CHARTING ==================
TICKET_CATEGORY_IDS = {1448805784652746894, 1448806932575162422, 1451571863825154058, 1451800068641521846, 1457368711630426153, 1471222806200062196, 1495820309750616195, 1506713487315964054, 1506713487315964054, 1512417173652639744, 1512420242801037343, 1512420314447876096}
STAFF_ROLE_IDS = {1448719741756768308, 1449035039072452800, 1449035563570303017}
AUTO_ROLE_IDS = {1448774516904825026}
REMOVE_ROLE_IDS = {1448831320636784660, 1448774246447845518}
BAD_WORDS = {"nigga"}

def is_staff(m: discord.Member): 
    return any(r.id in get_config(member.guild.id if "member" in locals() else m.guild.id if "m" in locals() and hasattr(m, "guild") and m.guild else 0, "STAFF_ROLE_IDS") for r in m.roles) or m.guild_permissions.administrator

def is_ticket_channel(c: discord.TextChannel): 
    return c.category and c.category.id in get_config(c.guild.id if "c" in locals() else 0, "TICKET_CATEGORY_IDS")

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
    # Single-char columns so chart stays compact and clean
    N = 12
    pts = _sample(history, N)
    if not pts:
        return "No data yet."
    mn, mx = min(pts), max(pts)
    spread = max(mx - mn, 1e-6)
    # top-of-bar chars for partial rows
    tops = " ▁▂▃▄▅▆▇█"
    lines = []
    for r in range(height - 1, -1, -1):
        row = ""
        for v in pts:
            y = (v - mn) / spread * height  # 0..height float
            if y >= r + 1:
                # fully filled row
                row += "█"
            elif y > r:
                # partial top
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


# ================== CONFESSION SYSTEM ==================
# Maps confession message_id -> author user_id (in memory only, never saved)
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

        # Determine if replier is the original confessor
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
        # Track this reply's author too so OP badge works on thread replies
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
        # Try to find the original_msg_id from the custom_id if not set
        await interaction.response.send_modal(ThreadReplyModal(self.original_msg_id))


class ConfessionSubmitModal(discord.ui.Modal, title="🕵️ Submit a Confession"):
    confession_text = discord.ui.TextInput(
        label="Your Confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type your confession here... (100% anonymous)",
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(get_config(i.guild.id, "CONFESSION_CHANNEL_ID"))
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

# ================== BIRTHDAY SYSTEM (PANEL & MODAL) ==================
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

# ================== CASINO & GAMES ==================
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

class BotDuelRPSView(discord.ui.View):
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
        await self.finish(i, "scissors")

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
            # This player dies, other wins
            winner = self.p2 if self.current_turn == self.p1 else self.p1
            self.btn.disabled = True
            balance[winner.id] += self.amt * 2
            save_data()
            e = discord.Embed(title="💥 BANG!", description=f"{self.current_turn.mention} pulled the trigger and it fired!\n\n🏆 {winner.mention} wins **{self.amt*2:,} Aura**!", color=discord.Color.red())
            return await i.response.edit_message(embed=e, view=self)

        # Survived — switch turn
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

# ================== PAYOUT, POLLS, & GIVEAWAYS ==================

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

        # Load fresh data from pending_payouts in case of restart
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

        public_channel = interaction.guild.get_channel(get_config(interaction.guild.id, "PUBLIC_LOG_CHANNEL_ID"))
        if public_channel:
            item_public = f"${(amt/AURA_TO_USD):.2f}" if method != "reddit" else "Reddit Account"
            await public_channel.send(embed=simple_embed(f"{E_SUCCESS} Withdrawal Successful!", f"<@{uid}> just withdrew **{item_public}** ({amt:,} Aura)!\nKeep chatting to earn more. {E_VIBE}", discord.Color.green()))

        # Remove from pending
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

        # Load fresh data from pending_payouts in case of restart
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

        public_channel = interaction.guild.get_channel(get_config(interaction.guild.id, "PUBLIC_LOG_CHANNEL_ID"))
        if public_channel:
            await public_channel.send(embed=simple_embed(f"❌ Withdrawal Rejected", f"<@{uid}>'s withdrawal for **{amt:,} Aura** was rejected and refunded.", discord.Color.red()))

        # Remove from pending
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

        # Build full list, split into chunks of 40 mentions per embed to stay under Discord's 4096 char limit
        mentions = [f"<@{uid}>" for uid in p]
        chunk_size = 40
        chunks = [mentions[x:x+chunk_size] for x in range(0, len(mentions), chunk_size)]

        embeds = []
        for idx, chunk in enumerate(chunks):
            title = f"👥 All Entries ({len(p)} total)" if idx == 0 else f"👥 Entries (cont. {idx+1})"
            embeds.append(discord.Embed(title=title, description="\n".join(chunk), color=discord.Color.blue()))

        # Discord allows max 10 embeds per message
        await i.response.send_message(embeds=embeds[:10], ephemeral=True)


# ================== BOT EVENT SYSTEM ==================
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
        self.add_view(VerifyPromptView())
        
        # Restore pending payouts
        for mid, pdata in pending_payouts.items():
            self.add_view(PayoutView(pdata["uid"], pdata["amt"], pdata["method"], pdata["details"], mid))
            
        await self.tree.sync()

        # START ALL BACKGROUND TASKS
        midnight_birthday_check.start()
        vc_reward_task.start()
        check_birthday_roles.start()
        autokick_check.start()
        aura_expiry_task.start()
        market_fluctuation.start()      
        daily_puzzle_scheduler.start()
        science_fact_dropper.start()
        reminder_checker.start()
        daily_hot_take.start()
        server_mood_tracker.start()


bot = MyBot()
last_chatter_id = None
last_user_message = {}
# ================== PUZZLE SYSTEM ==================
# Types: riddle | scramble | math | trivia | emoji | fillblank
PUZZLES = [
    # ── RIDDLES ──
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

    # ── WORD SCRAMBLES ──
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

    # ── MATH ──
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

    # ── TRIVIA ──
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

    # ── EMOJI PUZZLES ──
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

    # ── FILL IN THE BLANK ──
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
    # ── NEW TOTAL SET OF PUZZLES ──
    {"type": "riddle", "q": "I am a word of letters three, add two and fewer there will be. What word am I?", "a": "few"},
    {"type": "riddle", "q": "I have lakes with no water, mountains with no stone and cities with no buildings. What am I?", "a": "map"},
    {"type": "riddle", "q": "What has 88 keys but can't open a single door?", "a": "piano"},
    {"type": "riddle", "q": "I have a neck but no head, and I wear a cap. What am I?", "a": "bottle"},
    {"type": "riddle", "q": "If you drop me I'm sure to crack, but give me a smile and I'll always smile back. What am I?", "a": "mirror"},
    {"type": "riddle", "q": "I am tall when I'm young, and I'm short when I'm old. What am I?", "a": "candle"},
    {"type": "riddle", "q": "What belongs to you, but other people use it more than you?", "a": "name"},
    {"type": "scramble", "q": "RCETES", "a": "secret"},
    {"type": "scramble", "q": "OUNATNIM", "a": "mountain"},
    {"type": "scramble", "q": "RYTOS", "a": "story"},
    {"type": "scramble", "q": "ETIRW", "a": "write"},
    {"type": "math", "q": "What is 12 × 12?", "a": "144"},
    {"type": "math", "q": "If a triangle has a base of 10 and height of 5, what is its area?", "a": "25"},
    {"type": "math", "q": "What is 45% of 200?", "a": "90"},
    {"type": "math", "q": "What is 100 divided by 0.5?", "a": "200"},
    {"type": "emoji", "q": "👽📞🚲🌕 = ? (movie)", "a": "et"},
    {"type": "emoji", "q": "🦕🦟🦖 = ? (movie)", "a": "jurassic park"},
    {"type": "fillblank", "q": "A picture is worth a ___ words.", "a": "thousand"},
    {"type": "fillblank", "q": "The ___ is always greener on the other side.", "a": "grass"},
    {"type": "fillblank", "q": "Don't put all your ___ in one basket.", "a": "eggs"},
]

PUZZLES.extend(data.get("custom_puzzles", []))

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
vc_total_minutes = defaultdict(int, {int(k): v for k, v in data.get("vc_total_minutes", {}).items()})
vc_milestones_reached = data.get("vc_milestones_reached", {})


@bot.event
async def on_ready():
    logging.info(f"Bot online: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="/help | Collecting Aura"))
    # Restore randomizer bags from disk so no repeats across restarts
    yo_bag.load(data.get("yo_bag", []))
    roast_bag.load(data.get("roast_bag", []))
    if not master_reminder_loop.is_running():
        master_reminder_loop.start()
    if not check_upvote_orders.is_running():
        check_upvote_orders.start()
    if not withdrawal_checker_loop.is_running():
        withdrawal_checker_loop.start()

    # ── FIX: Clear ghost guild-scoped slash command copies that cause double responses ──
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            logging.info(f"Cleared guild-specific command dupes for {guild.name}")
        except Exception as e:
            logging.warning(f"Could not clear guild commands for {guild.id}: {e}")

    # Retroactively trim any portfolios over MAX_SHARES_PER_COIN and refund the excess invested Aura
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

    # Cache current invites for all guilds
    for guild in bot.guilds:
        try:
            cached_invites[guild.id] = {inv.code: inv.uses for inv in await guild.invites()}
        except Exception:
            pass

    # Read channel content from key categories so AI knows server info
    READ_CATEGORIES = {"important", "start here", "lounge", "reddit tasks", "extras"}
    global server_channel_knowledge, server_custom_emojis
    server_channel_knowledge = {}
    # Fetch server custom emojis
    for guild in bot.guilds:
        emoji_list = [f"<{'a' if e.animated else ''}:{e.name}:{e.id}>" for e in guild.emojis]
        if emoji_list:
            server_custom_emojis = "Available server emojis: " + " ".join(emoji_list[:30])
        break
    READ_CATEGORY_IDS = {1448753211245858826, 1448806198953644063, 1448714204964982845, 1448750517798043770, 1449052357340954674}
    for guild in bot.guilds:
        for channel in guild.text_channels:
            cat_id = channel.category.id if channel.category else None
            if cat_id in get_config(channel.guild.id if "channel" in locals() and channel.guild else 0, "READ_CATEGORY_IDS"):
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

# ── Role IDs for auto-verification ──
AGED_ACC_ROLE_ID       = 1449701649668116480   # Account 1+ year old
HIGH_KARMA_ROLE_ID     = 1449701535041716225   # 1000+ total karma
CQS_HIGHEST_ROLE_ID    = 1449032645462986822   # Highest CQS (90+)
CQS_HIGH_ROLE_ID       = 1449033105968201728   # High CQS (70-89)
CQS_MOD_ROLE_ID        = 1449033262839238710   # Moderate CQS (50-69)
CQS_LOW_ROLE_ID        = 1449033410218692660   # Low CQS (<50)

DEFAULT_SERVER_CONFIG = {
    "AI_PROMPT": AI_SYSTEM,
    "PAYMENT_TICKET_CATEGORY_ID": 1448805721071292661,
    "AGED_ACC_ROLE_ID": 1449701649668116480,
    "HIGH_KARMA_ROLE_ID": 1449701535041716225,
    "CQS_HIGHEST_ROLE_ID": 1449032645462986822,
    "CQS_HIGH_ROLE_ID": 1449033105968201728,
    "CQS_MOD_ROLE_ID": 1449033262839238710,
    "CQS_LOW_ROLE_ID": 1449033410218692660,
    "CHAT_CHANNEL_ID": 1518214909618290790,
    "PAYOUT_CHANNEL_ID": 1449908271937753129,
    "DAILY_ANNOUNCE_CHANNEL_ID": 1448748624375972075,
    "PUBLIC_LOG_CHANNEL_ID": 1448767223781916844,
    "AUTOKICK_WARN_CHANNEL_ID": 1453059081127592130,
    "HELP_CHANNEL_ID": 1448787031810642010,
    "CONFESSION_CHANNEL_ID": 1475013891258974349,
    "BIRTHDAY_CHANNEL_ID": 1473553195723784397,
    "BIRTHDAY_ROLE_ID": 1473554747633045615,
    "GIVE_LOG_CHANNEL_ID": 1448767355449512037,
    "ADMIN_ROLE_ID": 1448719741756768308,
    "MASTER_SHEET_URL": "https://docs.google.com/spreadsheets/d/16LsJL4-1Rv8gWbmjpS7GkC9HOmD1JAvLBYcWnGRkpHM/edit",
    "TICKET_CATEGORY_IDS": {1448805784652746894, 1448806932575162422, 1451571863825154058, 1451800068641521846, 1457368711630426153, 1471222806200062196, 1495820309750616195, 1506713487315964054, 1506713487315964054, 1512417173652639744, 1512420242801037343, 1512420314447876096},
    "STAFF_ROLE_IDS": {1448719741756768308, 1449035039072452800, 1449035563570303017},
    "AUTO_ROLE_IDS": {1448774516904825026},
    "REMOVE_ROLE_IDS": {1448831320636784660, 1448774246447845518},
    "READ_CATEGORY_IDS": {1448753211245858826, 1448806198953644063, 1448714204964982845, 1448750517798043770, 1449052357340954674}
}


class GlobalChannelProxy:
    def __init__(self, key):
        self.key = key
    def __bool__(self):
        return True
    async def send(self, *args, **kwargs):
        success = False
        for g in bot.guilds:
            cid = get_config(g.id, self.key)
            if cid:
                ch = bot.get_channel(cid)
                if ch:
                    try:
                        await ch.send(*args, **kwargs)
                        success = True
                    except: pass
        return success
    @property
    def id(self): return 0
    @property
    def name(self): return "Global Proxy"
    @property
    def guild(self): return None

MAIN_GUILD_ID = None

def get_main_guild_id():
    global MAIN_GUILD_ID
    if MAIN_GUILD_ID is not None:
        return MAIN_GUILD_ID
    # Try to find the guild that owns the default CHAT_CHANNEL_ID
    ch = bot.get_channel(1518214909618290790)
    if ch and hasattr(ch, "guild"):
        MAIN_GUILD_ID = ch.guild.id
        return MAIN_GUILD_ID
    return None

def get_config(guild_id: int, key: str):
    server_cfg = server_configs.get(str(guild_id), {})
    if key in server_cfg:
        return server_cfg[key]
    
    # Only fall back to defaults if this is the main server
    main_id = get_main_guild_id()
    if not main_id or guild_id == main_id:
        return DEFAULT_SERVER_CONFIG.get(key)
        
    # Return None (or empty collections) for other servers that haven't set a config
    default_val = DEFAULT_SERVER_CONFIG.get(key)
    if isinstance(default_val, set):
        return set()
    if isinstance(default_val, list):
        return []
    if isinstance(default_val, dict):
        return {}
    return None


# ==========================================
# VERIFICATION MODAL & BUTTON
# ==========================================

class VerificationModal(discord.ui.Modal, title="Reddit Verification Form"):
    reddit_profile = discord.ui.TextInput(
        label="Reddit Profile Link",
        placeholder="https://www.reddit.com/user/YourUsername",
        required=True,
        max_length=200,
    )
    cqs_link = discord.ui.TextInput(
        label="CQS Test Result Link",
        placeholder="Paste your CQS result URL here (from Reddit)",
        required=True,
        max_length=300,
    )

    def __init__(self, channel: discord.TextChannel, opener: discord.Member, prompt_msg):
        super().__init__()
        self.ticket_channel = channel
        self.opener = opener
        self.prompt_msg = prompt_msg   # the message carrying the submit button

    async def on_submit(self, interaction: discord.Interaction):
        profile_url = self.reddit_profile.value.strip()
        cqs_url     = self.cqs_link.value.strip()

        # Quick upfront URL validation
        if not extract_reddit_username_from_url(profile_url):
            return await interaction.response.send_message(
                "❌ **Invalid Reddit profile link!**\n"
                "It should look like: `https://www.reddit.com/user/YourUsername`\n"
                "Click the button again to resubmit.",
                ephemeral=True
            )
        if not profile_url.startswith("http") or not cqs_url.startswith("http"):
            return await interaction.response.send_message(
                "❌ Both links must start with `https://`. Please click the button again and resubmit.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        processing_msg = await self.ticket_channel.send("⏳ Verifying your Reddit account... please wait.")
        try:
            await _run_auto_verify(
                self.ticket_channel, self.opener,
                profile_url, cqs_url,
                processing_msg, prompt_msg=self.prompt_msg
            )
        except Exception as e:
            logging.error(f"Auto-verify modal error: {e}")
            await self.ticket_channel.send(
                f"❌ Something went wrong during verification: `{e}`. Please ask staff to verify you manually."
            )
        await interaction.followup.send("✅ Submitted! Check this ticket channel for your result.", ephemeral=True)


class VerifyPromptView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel = None, opener: discord.Member = None):
        super().__init__(timeout=None)   # Persistent — never expires
        self.ticket_channel = channel
        self.opener = opener

    @discord.ui.button(label="📋 Submit Verification Info", style=discord.ButtonStyle.blurple, custom_id="verify_submit_btn")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.ticket_channel or interaction.channel
        opener = self.opener
        
        if not opener:
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Member) and not target.bot and overwrite.read_messages:
                    opener = target
                    break
                    
        if not opener:
            opener = interaction.user

        # Only the ticket owner can use this button
        if interaction.user.id != opener.id:
            return await interaction.response.send_message(
                "❌ Only the ticket owner can submit verification info.", ephemeral=True
            )
            
        modal = VerificationModal(
            channel=channel,
            opener=opener,
            prompt_msg=interaction.message
        )
        await interaction.response.send_modal(modal)


async def _run_auto_verify(channel: discord.TextChannel, user: discord.Member,
                           profile_url: str, cqs_url: str, status_msg,
                           prompt_msg=None):
    """
    Core auto-verification logic. Called when a ticket owner submits both links.
    Fetches Reddit account data, evaluates eligibility, assigns roles or marks not fit.
    """
    guild = channel.guild

    # 1. Validate profile URL and extract username
    username = extract_reddit_username_from_url(profile_url)
    if not username:
        await status_msg.edit(content=(
            "❌ **Invalid Reddit profile link!**\n"
            "It should look like: `https://www.reddit.com/user/YourUsername`\n"
            "Click the **Submit Verification Info** button again to resubmit."
        ))
        return

    await status_msg.edit(content=f"⏳ Looking up Reddit account for **u/{username}**...")

    # 2. Get Reddit token
    token = await get_reddit_token()
    if not token:
        await status_msg.edit(content="❌ Could not connect to Reddit API right now. Please ask staff to verify you manually.")
        return

    # 3. Fetch Reddit account info
    info = await get_reddit_user_info(username, token)
    if info is None:
        await status_msg.edit(content=(
            f"❌ **Reddit account `u/{username}` not found!**\n"
            f"Double-check your profile link and click the **Submit Verification Info** button again."
        ))
        return

    if info.get("suspended"):
        await status_msg.edit(content=(
            f"❌ Your Reddit account **u/{username}** appears to be suspended. "
            f"Please contact staff if you believe this is an error."
        ))
        return

    age_days    = info["age_days"]
    total_karma = info["karma"]
    comment_karma = info["comment_karma"]
    age_months  = age_days / 30.44

    await status_msg.edit(content=f"⏳ Got account info! Now fetching CQS score from your result link...")

    # 4. Fetch CQS score
    cqs_score = await fetch_cqs_score(cqs_url, token=token)

    # 5. Determine CQS tier
    cqs_tier = classify_cqs(cqs_score)
    cqs_display = f"{cqs_score:.0f}/100" if cqs_score is not None else "Could not read"

    # 6. Check minimum requirements (same as /notfit criteria)
    # Requirements: 100+ karma, 20+ comment karma, 1+ month old, Moderate+ CQS (50+)
    fail_reasons = []
    if total_karma < 100:
        fail_reasons.append(f"- **Karma too low:** {total_karma:,} (need 100+)")
    if comment_karma < 20:
        fail_reasons.append(f"- **Comment karma too low:** {comment_karma:,} (need 20+)")
    if age_months < 1:
        fail_reasons.append(f"- **Account too new:** {age_days:.0f} days old (need 1+ month)")
    if cqs_score is not None and cqs_score < 50:
        fail_reasons.append(f"- **CQS too low:** {cqs_display} (need Moderate / 50+)")

    if fail_reasons:
        # ── NOT FIT ──
        not_fit_name = f"not fit-{user.display_name}"[:100]
        try:
            await channel.edit(name=not_fit_name)
        except Exception:
            pass

        desc = (
            f"{user.mention}, sorry — your account does not meet our minimum requirements yet.\n\n"
            f"**Issues found:**\n" + "\n".join(fail_reasons) +
            f"\n\n**Reddit account checked:** u/{username}\n"
            f"**Account age:** {age_days:.0f} days ({age_months:.1f} months)\n"
            f"**Total karma:** {total_karma:,} (post: {info['link_karma']:,} | comment: {comment_karma:,})\n"
            f"**CQS Score:** {cqs_display}\n\n"
            f"**Submitted Links:**\n"
            f"- Profile: <{profile_url}>\n"
            f"- CQS: <{cqs_url}>\n\n"
            f"You're welcome to stay and apply again once you meet the requirements! 🌟"
        )
        embed = discord.Embed(
            title="❌ Application Update",
            description=desc,
            color=discord.Color.red()
        )
        embed.set_footer(text="Fixed your account? Click 'Submit Verification Info' again to resubmit!")
        msg_content = (
            f"{user.mention}\n"
            f"If you were rejected for low karma, please read <#1449052486668255262>.\n"
            f"If you have any doubts, go to the help channel <#1448787031810642010>."
        )
        await status_msg.edit(content=msg_content, embed=embed)
        return

    # ── VERIFIED ──
    # 7. Build role list
    roles_to_add = []

    # Always add earner role (AUTO_ROLE_IDS)
    for rid in get_config(member.guild.id if "member" in locals() and hasattr(member, "guild") and member.guild else 0, "AUTO_ROLE_IDS"):
        r = guild.get_role(rid)
        if r:
            roles_to_add.append(r)

    # Remove pending/unverified roles
    for rid in get_config(guild.id if "guild" in locals() and guild else i.guild.id if "i" in locals() and i else 0, "REMOVE_ROLE_IDS"):
        r = guild.get_role(rid)
        if r and r in user.roles:
            try:
                await user.remove_roles(r)
            except Exception:
                pass

    # Aged account (1+ year = 365+ days)
    if age_days >= 365:
        r = guild.get_role(get_config(guild.id, "AGED_ACC_ROLE_ID"))
        if r:
            roles_to_add.append(r)

    # High karma (1000+ total karma)
    if total_karma >= 1000:
        r = guild.get_role(get_config(guild.id, "HIGH_KARMA_ROLE_ID"))
        if r:
            roles_to_add.append(r)

    # CQS tier roles
    cqs_role_map = {
        "highest": get_config(guild.id, "CQS_HIGHEST_ROLE_ID"),
        "high":    get_config(guild.id, "CQS_HIGH_ROLE_ID"),
        "moderate": get_config(guild.id, "CQS_MOD_ROLE_ID"),
        "low":     get_config(guild.id, "CQS_LOW_ROLE_ID"),
    }
    cqs_role_id = cqs_role_map.get(cqs_tier)
    if cqs_role_id:
        r = guild.get_role(cqs_role_id)
        if r:
            roles_to_add.append(r)

    # Assign all collected roles
    if roles_to_add:
        try:
            await user.add_roles(*roles_to_add)
        except discord.Forbidden:
            await channel.send("❌ I don't have permission to assign roles! Please ask staff to do it manually.")
            return

    # Rename channel to user's display name
    formatted_ticket_name = user.display_name[:100]
    try:
        await channel.edit(name=formatted_ticket_name.lower().replace(" ", "-"))
    except Exception:
        pass

    # 8. Send verified embed
    age_str    = f"{age_days:.0f} days ({age_months:.1f} months)"
    karma_str  = f"{total_karma:,} (post: {info['link_karma']:,} | comment: {comment_karma:,})"
    cqs_str    = f"{cqs_display} — **{cqs_tier.capitalize()} CQS**"
    ticket_ref = formatted_ticket_name.lower().replace(" ", "-")

    desc = (
        f"{E_PARTY} **Welcome!** {user.mention}\n"
        f"You've been **verified** based on your Reddit account!\n\n"
        f"📊 **Account Stats:**\n"
        f"├ **Username:** u/{info['username']}\n"
        f"├ **Account Age:** {age_str}\n"
        f"├ **Total Karma:** {karma_str}\n"
        f"└ **CQS Score:** {cqs_str}\n\n"
        f"**Submitted Links:**\n"
        f"- Profile: <{profile_url}>\n"
        f"- CQS: <{cqs_url}>\n\n"
        f"To claim tasks, please send your ticket as soon as tasks are available.\n\n"
        f"**📍 Where to send your ticket:**\n"
        f"<#1518207367941193972>\n<#1518207420487172156>\n<#1518207461650202755>\n\n"
        f"**Important points:**\n"
        f"- Your ticket name is **#{ticket_ref}**\n"
        f"- Task channels are opened only when tasks are available\n\n"
        f"{E_VIBE} **Time to earn!!!**"
    )
    embed = discord.Embed(
        title=f"{E_SUCCESS} VERIFIED {E_SUCCESS}",
        description=desc,
        color=discord.Color.green()
    )
    if roles_to_add:
        embed.add_field(
            name="🛠 Assigned Roles",
            value=", ".join(r.mention for r in roles_to_add),
            inline=False
        )
    await status_msg.edit(content=user.mention, embed=embed)

    # Disable the submit button now that verification is complete
    if prompt_msg:
        try:
            disabled_view = discord.ui.View()
            disabled_btn = discord.ui.Button(
                label="✅ Verified",
                style=discord.ButtonStyle.green,
                disabled=True
            )
            disabled_view.add_item(disabled_btn)
            await prompt_msg.edit(view=disabled_view)
        except Exception:
            pass

# Track channels we've already processed to prevent duplicate verification embeds
_processed_channel_ids = set()

@bot.event
async def on_guild_channel_create(channel):
    if not isinstance(channel, discord.TextChannel):
        return

    # ── FIX: Deduplication guard — skip if we already processed this channel ──
    if channel.id in _processed_channel_ids:
        return
    _processed_channel_ids.add(channel.id)
    # Auto-clean old entries so the set doesn't grow forever
    if len(_processed_channel_ids) > 500:
        _processed_channel_ids.clear()
        _processed_channel_ids.add(channel.id)

    await asyncio.sleep(1.5)  # wait for Discord to set permissions

    # ─── Payment ticket: just rename it ───────────────────────────────────
    if channel.category and channel.category.id == get_config(channel.guild.id, "PAYMENT_TICKET_CATEGORY_ID"):
        opener = None
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot and overwrite.read_messages:
                opener = target
                break
        if opener:
            new_name = f"payment-{opener.display_name[:80].lower().replace(' ', '-')}"
            try:
                await channel.edit(name=new_name)
                logging.info(f"Renamed payment ticket to {new_name}")
            except Exception as e:
                logging.error(f"Could not rename ticket: {e}")
        return

    # ─── Application/verify ticket: auto-verify flow ──────────────────────
    # Work for ALL ticket categories AND even tickets created outside them
    # (user asked it to work regardless of category)
    opener = None
    for target, overwrite in channel.overwrites.items():
        if isinstance(target, discord.Member) and not target.bot and overwrite.read_messages:
            opener = target
            break

    if not opener:
        return  # can't find the ticket owner, bail

    # Don't process payment tickets again
    if channel.category and channel.category.id == get_config(channel.guild.id, "PAYMENT_TICKET_CATEGORY_ID"):
        return

    # Send verification prompt with a button that opens the Modal form
    embed = discord.Embed(
        title="👋 Welcome! Let's get you verified.",
        description=(
            f"Hey {opener.mention}! 🎉\n\n"
            f"To complete your application, click the **Submit Verification Info** button below and fill in both links.\n\n"
            f"**1️⃣ Reddit Profile Link**\n"
            f"Your Reddit profile URL — e.g.\n`https://www.reddit.com/user/YourUsername`\n\n"
            f"**2️⃣ CQS Test Result Link**\n"
            f"CQS (Contributor Quality Score) is a Reddit internal score. Here's how to get it:\n\n"
            f"┣ Go to 👉 **https://www.reddit.com/r/WhatIsMyCQS**\n"
            f"┣ Click **New Post** and type exactly: `what is my cqs`\n"
            f"┣ AutoModerator will **reply to your post** with your CQS tier\n"
            f"┗ Copy the **link to your post** and paste it in the form\n\n"
            f"✅ **Accepted tiers:** Moderate, High, Highest\n"
            f"❌ **Rejected tiers:** Low, Lowest\n\n"
            f"Once you submit, the bot verifies you automatically! 🤖"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Make sure your Reddit account is not private/suspended, and that AutoMod has replied to your CQS post before submitting.")
    view = VerifyPromptView(channel=channel, opener=opener)
    try:
        # Removed raw ping to prevent anti-spam trigger if many tickets are opened rapidly
        prompt_msg = await channel.send(embed=embed, view=view)
    except Exception as e:
        logging.error(f"Could not send verification prompt: {e}")


# Track recently processed message IDs to prevent double responses
_processed_msg_ids = deque(maxlen=200)

@bot.event
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
        content_prefix = f"🚨 **[RESTORED]** {deleter} tried to delete a message from {m.author.mention}:\n"
        await m.channel.send(content=content_prefix + m.content, embeds=m.embeds)

@bot.event
async def on_message(m: discord.Message):
    if m.author.bot: 
        return

    # ── FIX: Skip if we already processed this exact message ──
    if m.id in _processed_msg_ids:
        return
    _processed_msg_ids.append(m.id)

    # ── Owner aura request handlers — must be FIRST before any other logic ──
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


    # ────────────────────────────────────────────────────────────────────────
        
    # Log message to channel context — skip staff channels
    if not m.author.bot and m.content and not m.content.startswith('/'):
        if not (hasattr(m.channel, 'category') and m.channel.category and m.channel.category.name == "Staff Area"):
            if m.channel.id not in channel_chat_log:
                channel_chat_log[m.channel.id] = deque(maxlen=100)
            channel_chat_log[m.channel.id].append(f"{m.author.display_name}: {m.content[:200]}")

    global last_chatter_id
    text = m.content.lower().strip()
        
    _chat_cooldowns = getattr(bot, "_chat_cooldowns", {})
    if not hasattr(bot, "_chat_cooldowns"):
        bot._chat_cooldowns = _chat_cooldowns

    _yo_triggers = {"yo", "yoo", "yooo", "hi", "hello", "wsg", "wassup", "konnichiwa", "konnichiha", "hola", "bonjour", "salut", "ciao", "hallo", "namaste", "salam", "merhaba", "oi", "ola", "hei", "hej", "привет", "안녕", "こんにちは"}
    _gm_triggers = {"gm", "good morning", "good mrng", "gmorning", "subah", "subh", "subha", "good mng"}
    _gn_triggers = {"gn", "good night", "good nite", "goodnight", "raat", "sone ja", "so ja", "sojaon"}
    
    # Check cooldown before processing AI replies to avoid rate limit bans
    if text in _gm_triggers or text in _gn_triggers or text in _yo_triggers:
        # Check Premium status
        if not m.guild or (str(m.guild.id) not in premium_guilds and m.guild.owner_id != 992008865656868946):
            return  # Don't trigger auto-replies in free servers
            
        now_ts = time.time()
        if now_ts - _chat_cooldowns.get("global_chat_trigger", 0) < 10:
            return  # On cooldown, ignore the trigger
        _chat_cooldowns["global_chat_trigger"] = now_ts
        
        if text in _gm_triggers:
            reply = await quick_ai(f"{m.author.display_name} said good morning in the server. Reply with a chill personalized good morning. Match language. 1 sentence.", max_tokens=150)
            await m.channel.send(reply if reply else f"Good morning {m.author.mention} 👋")
            return
        elif text in _gn_triggers:
            reply = await quick_ai(f"{m.author.display_name} said good night in the server. Reply with a chill good night message. Match language. 1 sentence.", max_tokens=150)
            await m.channel.send(reply if reply else f"Good night {m.author.mention} 🌙")
            return
        elif text in _yo_triggers:
            yo_reply = await quick_ai(f"{m.author.display_name} just said '{m.content}' in the server chat. Give a short, fun greeting back. Match their language. Max 1 sentence.", max_tokens=160)
            await m.channel.send(yo_reply if yo_reply else yo_bag.get_next())
            return

    # Gemini AI — respond when bot is @mentioned
    if bot.user in m.mentions:
        question = m.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        # Ignore if message is just emojis or empty
        import re
        text_only = re.sub(r'<a?:[\w]+:[\d]+>', '', question).strip()
        text_only = re.sub('[\U0001F000-\U0001FFFF\U00002000-\U00003300]', '', text_only).strip()
        if not text_only:
            return

        # Ignore all replies to bot messages that are slash command responses (have embeds, no plain content)
        if m.reference:
            try:
                ref_msg = m.reference.cached_message or await m.channel.fetch_message(m.reference.message_id)
                if ref_msg.author.id == bot.user.id and (ref_msg.embeds or ref_msg.components):
                    return  # Never reply to slash command responses
            except Exception:
                pass

        if not question:
            question = "kuch toh bol"

        # Use AI to detect if this is genuinely a request FOR Aura (not just mentioning aura in conversation)
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

        # Check if this is a reminder request
        reminder_set = await _try_set_reminder(m.author.id, m.channel.id, question)
        if reminder_set:
            await m.reply(reminder_set)
            return

        async with m.channel.typing():
            # Only send avatar if this is the first time we've seen this user (no history yet)
            avatar = str(m.author.display_avatar.url) if m.author.display_avatar else None
            reply = await ask_ai(question, m.author.display_name, m.author.id, m.channel.id, member=m.author, avatar_url=avatar)
        if reply:
            import re as _re
            # Strip any :shortcode: emoji patterns and malformed custom emoji syntax
            reply = _re.sub(r'(?<![<a]):[a-zA-Z0-9_]+:', '', reply)
            # Fix or strip malformed custom emojis (wrong case like <A: instead of <a:)
            reply = _re.sub(r'<[A-Z]:[a-zA-Z0-9_]+:\d+>', '', reply)
            reply = reply.strip()
            if reply:
                for i in range(0, len(reply), 2000):
                    await m.reply(reply[i:i+2000])
                asyncio.create_task(_extract_memory(m.author.id, m.author.display_name, question, reply))
                # --- BOT STEALS THE PUZZLE REWARD ---
                if active_puzzle["question"] and not active_puzzle["solved"]:
                    ans_raw = str(active_puzzle["answer"]).lower()
                    ans_clean = "".join(c for c in ans_raw if c.isalnum() or c.isspace()).strip()
                    # Strip punctuation from the bot's reply so we can check it cleanly
                    clean_reply = "".join(c for c in reply.lower() if c.isalnum() or c.isspace())
                    
                    # Check if the exact answer is inside the bot's reply
                    if f" {ans_clean} " in f" {clean_reply} " or ans_clean.replace(" ", "") == clean_reply.replace(" ", ""):
                        active_puzzle["solved"] = True
                        bot_bank["balance"] += 50
                        save_data()
                        
                        await m.channel.send(f"🤖 **Hold up... I just solved my own puzzle!**\nI'm stealing the **50 Aura** for my casino bank! 🤑\n> ✅ Answer: **{active_puzzle['answer'].title()}**")
        return

    # Update last_message_times if they talk in main chat or task channels to prevent aura expiry
    if m.channel.id in (get_config(m.guild.id if m.guild else 0, "CHAT_CHANNEL_ID"), CHAT_CHANNEL_ID_2, 1518207367941193972, 1518207420487172156, 1518207461650202755):
        last_message_times[str(m.author.id)] = time.time()

    if m.channel.id in (get_config(m.guild.id if m.guild else 0, "CHAT_CHANNEL_ID"), CHAT_CHANNEL_ID_2):
        uid = m.author.id
        
        # --- SENTIENT LURKER MODE ---
        if not m.content.startswith('/') and len(text) > 15 and bot.user not in m.mentions:
            # Check Premium status
            if m.guild and (str(m.guild.id) in premium_guilds or m.guild.owner_id == 992008865656868946):
                import random
                if random.random() < 0.01: # 1% chance
                    interject_prompt = f"You are the sarcastic bot of this Discord server. You are lurking. The user {m.author.display_name} just said: '{m.content}'. Jump in uninvited with a witty, funny, or sarcastic 1-sentence comment. Act like you were eavesdropping."
                    reply = await quick_ai(interject_prompt, max_tokens=150)
                    if reply:
                        await m.channel.send(reply)
        
        # Puzzle answer check
        if active_puzzle["question"] and not active_puzzle["solved"]:
            correct_ans_raw = str(active_puzzle["answer"]).lower()
            correct_ans_clean = "".join(c for c in correct_ans_raw if c.isalnum() or c.isspace()).strip()
            
            # Strip punctuation from the user's message so we can check it cleanly
            clean_text = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
            
            # Check if the exact answer is anywhere inside their sentence
            if f" {correct_ans_clean} " in f" {clean_text} " or correct_ans_clean.replace(" ", "") == clean_text.replace(" ", ""):
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

        import re
        found_hard = next((egg for egg in hard_eggs if re.search(r'\b' + re.escape(egg) + r'\b', text)), None)
        found_easy = next((egg for egg in easy_eggs if re.search(r'\b' + re.escape(egg) + r'\b', text)), None)
        
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


# ================== BACKGROUND TASKS ==================

# dm_brokies_task was removed because mass DMing users automatically every day violates Discord's Anti-Spam policy.

VC_MILESTONES = [10, 50, 100, 250, 500, 1000]
# ==========================================
# INACTIVITY WIPER (THE GRIM REAPER)
# ==========================================
@tasks.loop(hours=24) # Check every 24 hours
async def aura_expiry_task():
    print("💀 Running 7-Day Inactivity Check...")
    current_time = time.time()
    seven_days_in_seconds = 7 * 24 * 60 * 60
    
    wiped_uids = []
    aura_burned = 0
    
    for uid in list(balance.keys()):
        if balance[uid] <= 0:
            continue
            
        last_spoke = last_message_times.get(str(uid))
        if last_spoke is None:
            last_message_times[str(uid)] = current_time
            continue
            
        if (current_time - last_spoke) >= seven_days_in_seconds:
            aura_burned += balance[uid]
            balance[uid] = 0
            wiped_uids.append(uid)
            print(f"🪦 User {uid} was wiped for 7 days of silence.")

    save_data()
    print(f"✅ Reaper complete. Wiped {len(wiped_uids)} accounts. Burned {aura_burned:,} Aura.")
    
    # --- PUBLIC ANNOUNCEMENT WITH PINGS ---
    if wiped_uids:
        channel = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID") 
        if channel:
            embed = discord.Embed(
                title="💀 The Grim Reaper", 
                description=f"Swept **{len(wiped_uids)}** inactive accounts for 7 days of silence.\nAll their Aura has been burned to ash. Say something in chat to stay alive!", 
                color=discord.Color.dark_theme()
            )
            # Just send the cool embed without mass-pinging users to avoid Discord anti-spam flags.
            await channel.send(embed=embed)

@tasks.loop(minutes=1)
async def withdrawal_checker_loop():
    global withdrawal_open_until
    if withdrawal_open_until and datetime.datetime.now(IST) >= withdrawal_open_until:
        withdrawal_open_until = None
        save_data()
        announce = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
        if announce:
            await announce.send(embed=discord.Embed(title="🔒 Withdrawals Closed", description="The withdrawal window has ended.", color=discord.Color.red()))

@tasks.loop(minutes=1)
async def vc_reward_task():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if guild.afk_channel and vc.id == guild.afk_channel.id:
                continue
                
            for member in vc.members:
                if member.bot or (member.voice and member.voice.self_deaf):
                    continue

                uid = member.id
                vc_total_minutes[uid] += 1
                mins = vc_total_minutes[uid]

                # 13-Minute Continuous Reward
                if mins % 13 == 0:
                    balance[uid] += 2
                    
                # Milestone Rewards
                if mins % 60 == 0:
                    hours = mins // 60
                    if hours in VC_MILESTONES:
                        uid_str = str(uid)
                        if uid_str not in vc_milestones_reached:
                            vc_milestones_reached[uid_str] = []
                            
                        if hours not in vc_milestones_reached[uid_str]:
                            vc_milestones_reached[uid_str].append(hours)
                            balance[uid] += 100
                            
                            ch = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
                            if ch:
                                await ch.send(
                                    embed=discord.Embed(
                                        title="🎙️ Voice Milestone Hit!",
                                        description=f"{member.mention} has spent **{hours} Hours** in voice channels!\nThey were just awarded a bonus of **100 Aura**! 🎉",
                                        color=discord.Color.gold()
                                    )
                                )
    save_data()
    
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
    
    for guild in bot.guilds:
        if str(guild.id) not in premium_guilds and guild.owner_id != 992008865656868946:
            continue
            
        ch_id = get_config(guild.id, "CHAT_CHANNEL_ID")
        ch = bot.get_channel(ch_id) if ch_id else None
        if not ch:
            continue
            
        all_msgs = []
        for cid, log in channel_chat_log.items():
            c = bot.get_channel(cid)
            if c and c.guild.id == guild.id and (not c.category or c.category.name != "Staff Area"):
                all_msgs.extend(list(log)[-10:])
        if len(all_msgs) < 5:
            continue
            
        sample = "\n".join(all_msgs[-30:])
        mood = await quick_ai(
            f"Based on these recent Discord server messages, describe the server vibe/mood in one punchy sentence. Use emojis. Be fun and accurate.\n\nMessages:\n{sample}",
            max_tokens=160
        )
        if mood:
            await ch.send(f"📡 **Server Mood Check:** {mood}")


@tasks.loop(minutes=5)
async def market_fluctuation():
    global midday_flip_done, midday_flip_date, personality_season

    now_ist = datetime.datetime.now(IST)
    current_day = now_ist.date().toordinal()
    today_str = now_ist.date().isoformat()
    current_hour = now_ist.hour

    # Reset midday flip tracking at midnight
    if midday_flip_date != today_str:
        midday_flip_date = today_str
        midday_flip_done = False

    # Mid-day personality flip: between 12pm-4pm IST, silent, once per day
    if not midday_flip_done and 12 <= current_hour < 16:
        if random.random() < 0.15:  # ~15% chance per tick in this window
            personality_season += 1
            midday_flip_done = True
            save_data()
            logging.info(f"Mid-day personality flip triggered (season={personality_season})")

    random.seed(current_day + personality_season)
    # Default list without 'moon' (added an extra 'stable' to keep it at 7 items)
    personalities = ["stable", "rugpull", "volatile", "stable", "steady_up", "steady_down", "wildcard"]
    
    # Only 15% chance that ONE coin gets the 'moon' personality
    if random.random() < 0.15:
        personalities[0] = "moon"
        
    random.shuffle(personalities)
    coin_personalities = {c: p for c, p in zip(stocks.keys(), personalities)}
    random.seed()

    for coin in stocks:
        p = coin_personalities[coin]

        # Add noise to ranges — shifts slightly every few hours
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

        # Random shock event: 0.8% chance per coin per tick regardless of personality
        if random.random() < 0.008:
            shock = random.choice([-0.20, -0.15, 0.11, 0.12, 0.08])
            change += shock
            logging.info(f"Shock event on {coin}: {shock:+.0%}")

        # Skip delisted coins entirely
        if coin in delisted_coins:
            continue

        # --- 1. BUBBLE BURST MECHANIC ---
        if stocks[coin] > 350:
            if random.random() < 0.15: 
                change = random.uniform(-0.35, -0.60)
                logging.info(f"BUBBLE BURST on {coin}! Crashed by {change:+.0%}")

        # --- 2. GRAVITY MECHANIC ---
        if stocks[coin] > 400:
            if change > 0:
                change *= 0.25 # Cuts upward momentum
            elif change < 0:
                change *= 1.50 # Accelerates drops

        new_price = min(500.0, max(0.0, stocks[coin] * (1 + change)))
        if 0 < new_price < 1.0:
            new_price = 0.0  # snap to 0 to trigger delist cleanly

        # Gradual force_market nudge — pull price toward target by up to 8% per tick
        if coin in force_market_targets:
            target = force_market_targets[coin]
            diff = target - new_price
            # Move 15% of remaining gap per tick so it feels natural
            nudge = diff * 0.15
            new_price = min(500.0, max(0.0, new_price + nudge))
            if 0 < new_price < 1.0:
                new_price = 0.0
            # Remove target once within 2 Aura of it
            if abs(new_price - target) < 2:
                del force_market_targets[coin]
                logging.info(f"force_market target reached for {coin}")

        stocks[coin] = new_price

        # Delist if coin hits 0
        if stocks[coin] <= 0:
            stocks[coin] = 0.0
            # Dissolve all shares — everyone loses their investment
            wiped = []
            for uid in list(portfolios.keys()):
                if coin in portfolios[uid] and portfolios[uid][coin].get("shares", 0) > 0:
                    wiped.append(uid)
                    # 10% liquidation payout on invested Aura
                    invested = portfolios[uid][coin].get("invested", 0.0)
                    payout = max(1, int(invested * 0.10))
                    balance[uid] += payout
                    portfolios[uid][coin] = {"shares": 0, "invested": 0.0}
            # Delist for 2-4 hours, then relist at DEFAULT price
            import time as _time
            relist_delay = random.randint(2, 4) * 3600  # 2-4 hours in seconds
            delisted_coins[coin] = _time.time() + relist_delay
            stock_history[coin] = []
            save_data()
            # Announce in chat channel
            ch = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
            if ch:
                    # 1. Get the AI response first
                    ai_news = await quick_ai(f"Write a dramatic breaking news style announcement: the crypto coin {coin} just crashed to 0 and got delisted! {len(wiped)} holders lost their shares. They got 10% back as liquidation. It will relist in {relist_delay // 3600} hours. Keep it fun and dramatic. Max 3 sentences.", max_tokens=120)

                    # 2. Escape dollar signs so Discord doesn't try to format them as math
                    if ai_news:
                        ai_news = ai_news.replace("$", "\\$")

                    # 3. Use the fallback if the AI failed or returned a cut-off string (less than 25 chars)
                    embed_desc = ai_news if ai_news and len(ai_news) > 25 else f"**{coin}** has crashed to **0 Aura** and has been delisted!\n\n**{len(wiped)} holder(s)** had their shares dissolved. Holders received 10% back. Relists in **{relist_delay // 3600} hours**."

                    embed = discord.Embed(
                        title="💀 COIN DELISTED",
                        description=embed_desc,
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

    # Check for coins ready to relist
    import time as _time
    now_ts = _time.time()
    for coin in list(delisted_coins.keys()):
        if now_ts >= delisted_coins[coin]:
            # Relist at default price
            relist_price = float(random.randint(10, 80))  # random relist price
            stocks[coin] = relist_price
            stock_history[coin] = [relist_price] * 10
            del delisted_coins[coin]
            save_data()
            ch = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
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
    ch = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
    if not ch:
        return
    stock_prices = ", ".join(f"{c}: {v:.1f} Aura" for c, v in stocks.items())
    take = await quick_ai(f"You are a sarcastic stock market analyst for a Discord server economy. Current prices: {stock_prices}. Give one hot take or prediction about these server stocks. Be funny and opinionated. Max 2 sentences. ALWAYS finish your sentence.", max_tokens=300)
    if take:
        embed = discord.Embed(title="🔥 Hot Take of the Day", description=take, color=discord.Color.orange())
        embed.set_footer(text="This is not financial advice. Or is it? 👀")
        await ch.send(embed=embed)

# ==========================================
# WEEKLY RECAP ENGINE
# ==========================================
@tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=IST))  # Runs at 8:00 PM IST exactly
async def weekly_recap_task():
    now = datetime.datetime.now(IST)
    if now.weekday() != 6:  # 6 = Sunday. If it's not Sunday, go back to sleep.
        return
        
    ch = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
    if not ch:
        return

    # 1. Calculate Top Earner
    top_earner_id = max(weekly_aura_earned, key=weekly_aura_earned.get) if weekly_aura_earned else None
    top_earner_name = "Nobody"
    if top_earner_id:
        m = ch.guild.get_member(top_earner_id) if ch.guild else None
        top_earner_name = m.display_name if m else f"<@{top_earner_id}>"

    # 2. Calculate Biggest Loser
    top_loser_id = max(weekly_casino_lost, key=weekly_casino_lost.get) if weekly_casino_lost else None
    top_loser_name = "Nobody"
    if top_loser_id:
        m = ch.guild.get_member(top_loser_id) if ch.guild else None
        top_loser_name = m.display_name if m else f"<@{top_loser_id}>"

    # 3. Calculate Market Moves
    best_stock = max(stocks, key=stocks.get) if stocks else "None"
    worst_stock = min(stocks, key=stocks.get) if stocks else "None"

    # 4. Generate the AI Hype Message
    prompt = (
        f"Write a fun weekly server recap for a Discord economy server. "
        f"Top Aura earner this week: {top_earner_name} with {weekly_aura_earned.get(top_earner_id, 0):,} Aura. "
        f"Biggest casino loser: {top_loser_name} lost {weekly_casino_lost.get(top_loser_id, 0):,} Aura. "
        f"Highest priced stock: {best_stock} at {stocks.get(best_stock, 0):.1f} Aura. "
        f"Lowest priced stock: {worst_stock} at {stocks.get(worst_stock, 0):.1f} Aura. "
        f"Be funny, engaging, like a sports commentator. 3-4 sentences max."
    )
    recap = await quick_ai(prompt, max_tokens=2000)
    if recap and len(recap) > 4000:
        recap = recap[:4000] + "..."

    # 5. Build and Send the Embed
    embed = discord.Embed(
        title="📊 Weekly Server Recap",
        description=recap or "Another week in the books! Check the leaderboard to see where you stand.",
        color=discord.Color.blurple()
    )
    
    if top_earner_id and weekly_aura_earned.get(top_earner_id, 0) > 0:
        embed.add_field(name="💰 Top Earner", value=f"{top_earner_name} \n(+{weekly_aura_earned[top_earner_id]:,} Aura)", inline=True)
    if top_loser_id and weekly_casino_lost.get(top_loser_id, 0) > 0:
        embed.add_field(name="🎰 Biggest Gambler", value=f"{top_loser_name} \n(-{weekly_casino_lost[top_loser_id]:,} Aura)", inline=True)
        
    if stocks:
        embed.add_field(name="📈 Hot Stock", value=f"{best_stock} @ {stocks.get(best_stock, 0):.1f}", inline=True)
        embed.add_field(name="📉 Cold Stock", value=f"{worst_stock} @ {stocks.get(worst_stock, 0):.1f}", inline=True)
        
    embed.set_footer(text="See you next week! Keep grinding 💪")
    await ch.send(embed=embed)

    # 6. WIPE WEEKLY MEMORY FOR THE NEW WEEK
    weekly_aura_earned.clear()
    weekly_casino_lost.clear()
    casino_losses.clear()
    casino_wins.clear()
    save_data()
    
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

    # Only drop during peak hours: 6pm to 11pm IST
    if not (18 <= now.hour < 23):
        return

    # Only once per day
    if last_science_fact_date == today:
        return

    # 20% chance per tick so it feels random within peak window
    if random.random() > 0.20:
        return

    last_science_fact_date = today
    fact = await quick_ai("Share one fascinating science, space, biology or physics fact. Make it mind-blowing and engaging. Start directly with the fact, no intro. 2 sentences max. ALWAYS finish the sentence completely.", max_tokens=200)
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
            except: pass

@tasks.loop(minutes=20)
async def daily_puzzle_scheduler():
    global puzzles_sent_today, puzzle_date, active_puzzle, last_puzzle_time
    global puzzle_slots, puzzle_slots_date

    now = datetime.datetime.now(IST)
    today = now.date().isoformat()
    hour = now.hour

    # Reset all slots at midnight
    if puzzle_slots_date != today:
        puzzle_slots_date = today
        puzzle_slots = {"midnight": False, "afternoon": False, "random": False}
        puzzle_date = today
        puzzles_sent_today = 0
        last_puzzle_time = 0
        active_puzzle = {"question": None, "answer": None, "solved": False}

    # Don't send a new puzzle if the last one was less than 1 hour ago
    if last_puzzle_time and (time.time() - last_puzzle_time) < 3600:
        return

    # ── Decide which slot to try this tick ──
    # Priority order: midnight first, then afternoon, then random.
    # Each slot has its own time window and trigger chance.

    slot = None
    chance = 0.0

    if not puzzle_slots.get("midnight") and 0 <= hour < 1:
        # Midnight puzzle: fires somewhere in the 12:00am–1:00am window
        slot = "midnight"
        chance = 0.40

    elif not puzzle_slots.get("afternoon") and 12 <= hour < 17:
        # Afternoon puzzle: fires somewhere in the 12:00pm–5:00pm window
        slot = "afternoon"
        chance = 0.25

    elif not puzzle_slots.get("random") and 9 <= hour < 23:
        # Random puzzle: can fire any time 9am–11pm.
        # Low per-tick chance so it lands at a genuinely unpredictable time.
        slot = "random"
        chance = 0.08

    if slot is None or random.random() > chance:
        return

    channel = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
    if not channel:
        return

    # Pick a puzzle that hasn't been used recently
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

    # Slot label shown in footer so people know which puzzle this is
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
    now = time.time()
    
    for guild in bot.guilds:
        guild_id_str = str(guild.id)
        # Fallback to global cfg for backwards compatibility if guild config not found
        cfg = autokick_cfg.get(guild_id_str) or (autokick_cfg if "role_id" in autokick_cfg else None)
        if not cfg or not cfg.get("role_id"):
            continue
            
        days_limit = cfg["days"]
        half_days = cfg["days"] / 2.0
            
        warn_channel_id = get_config(guild.id, "AUTOKICK_WARN_CHANNEL_ID")
        warn_channel = bot.get_channel(warn_channel_id) if warn_channel_id else None
        
        role = guild.get_role(cfg["role_id"])
        if not role: 
            continue
            
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
            await warn_channel.send(content=mentions, embed=discord.Embed(title="⚠️ Time Limit Warning!", description=f"You are exactly halfway through your **{days_limit}-day** limit.\n\nPlease create a ticket or msg the issue in help channel <#{get_config(guild.id, 'HELP_CHANNEL_ID')}>, otherwise you will be automatically kicked.", color=discord.Color.orange()))

@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=IST))
async def midnight_birthday_check():
    today_str = datetime.datetime.now(IST).date().isoformat()
    today_bday_str = datetime.datetime.now(IST).strftime("%d-%m")
    
    bot_bank["date"] = today_str
    bot_bank["balance"] = 100
    save_data()

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
        channel = GlobalChannelProxy("BIRTHDAY_CHANNEL_ID")
        if channel:
            guild = channel.guild
            role = guild.get_role(get_config(guild.id, "BIRTHDAY_ROLE_ID"))
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


# ================== GAME COMMANDS ==================
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

    high_roller = False

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

    # Guaranteed loss for bets over 150 — force a losing result visually
    if high_roller:
        attempts = 0
        while check_win(result, bet_target)[0] and attempts < 100:
            result = random.randint(0, 36)
            attempts += 1
        win = False
        payout_multiplier = 0
    # 15% Rigged logic (normal bets only)
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

    # 3 frames only, 1.2s apart to avoid rate limits
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
    
    # La Partage Check
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


# ================== ECONOMY COMMANDS ==================

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
    announce = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
    embed = discord.Embed(title="💸 Withdrawals are OPEN!", description=f"You can now use `/withdraw` to cash out your Aura.\n\nWithdrawals close: **{closes_at}**", color=discord.Color.green())
    if announce:
        await announce.send(embed=embed)
    save_data()
    await i.response.send_message(f"✅ Withdrawals opened for **{hours} hour(s)**. Closes at {closes_at}.", ephemeral=True)

@bot.tree.command(name="close_withdrawals", description="Staff: Close withdrawals immediately")
async def close_withdrawals(i: discord.Interaction):
    global withdrawal_open_until
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
    withdrawal_open_until = None
    save_data()
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
        
    payout_channel = bot.get_channel(get_config(interaction.guild.id if "interaction" in locals() else i.guild.id if "i" in locals() else 0, "PAYOUT_CHANNEL_ID"))
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
    # Store in pending_payouts keyed by message id for restart persistence
    pending_payouts[str(payout_msg.id)] = {"uid": uid, "amt": amount, "method": method, "details": details}
    # Update the view with the real message id
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

    # Update streak
    if str(last_daily.get(uid)) == yesterday:
        daily_streak[uid] += 1
    else:
        daily_streak[uid] = 1
    streak = daily_streak[uid]

    # Base reward
    roll = random.randint(1, 100)
    if roll <= 99:
        amt = random.randint(1, 100)
    else:
        amt = random.randint(101, 200)

    # Streak bonus: +2 Aura per day, caps at 30
    streak_bonus = min(streak, 30) * 2
    amt += streak_bonus

    # Milestone bonuses
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

    # Streak label (no emoji overload)
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

    # Wide wheel spin — 7 slots like French roulette
    def make_wheel(slots):
        # 5 slots, centre (index 2) is the result
        # each slot = 5 chars, separator = 1 char → slot 2 centre = 14
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

    # Final wheel with result locked in centre (index 2)
    final_slots = [random.randint(1, 100) for _ in range(2)] + [amt] + [random.randint(1, 100) for _ in range(2)]
    is_jackpot = roll > 99
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

@bot.tree.command(name="vc_stats", description="Check how much time you've spent in voice channels")
async def vc_stats(i: discord.Interaction, user: Optional[discord.Member] = None):
    u = user or i.user
    mins = vc_total_minutes.get(u.id, 0)
    
    hours = mins // 60
    leftover_mins = mins % 60
    next_milestone = next((m for m in VC_MILESTONES if m > hours), "Maxed Out")
    
    embed = discord.Embed(title="🎙️ Voice Channel Stats", color=discord.Color.blurple())
    embed.set_thumbnail(url=u.display_avatar.url)
    embed.add_field(name="User", value=u.mention, inline=False)
    embed.add_field(name="Total Time", value=f"**{hours}h {leftover_mins}m**", inline=True)
    embed.add_field(name="Next Milestone", value=f"**{next_milestone} hours**", inline=True)
    embed.set_footer(text="Earn 2 Aura every 13 minutes, and 100 Aura at major hour milestones!")
    
    await i.response.send_message(embed=embed)
    
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

    log_ch = bot.get_channel(get_config(i.guild.id, "GIVE_LOG_CHANNEL_ID"))
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
    
    win_chance = 50
    payout_multiplier = 0.95 
    
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

# ==========================================
# LEADERBOARD COMMAND
# ==========================================
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
            emoji = E_COIN # Assuming E_COIN is defined elsewhere in your file
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
        
        # We removed the [:10] here so we grab EVERY single user in the database
        sorted_data = sorted(source.items(), key=lambda x: int(x[1]), reverse=True)
        
        if not sorted_data:
            return await i.response.send_message(embed=discord.Embed(title=f"🏆 Server Leaderboard | {label}", description="No data available yet.", color=discord.Color.gold()))

        # Pass the massive list into our engine to handle the pages automatically
        view = LeaderboardView(
            data_list=sorted_data, 
            guild=i.guild, 
            label=label, 
            emoji=emoji, 
            user=i.user
        )
        
        # Send the very first page (0-10) with the buttons attached
        await i.response.send_message(embed=view.generate_embed(), view=view)
        
    except Exception as e:
        await i.response.send_message(f"Leaderboard Error: {e}", ephemeral=True)


# ================== STOCK MARKET COMMANDS ==================

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

    # Reset daily uses at midnight
    today_str = datetime.datetime.now(IST).date().isoformat()
    if insider_uses_date != today_str:
        insider_uses_date = today_str
        insider_uses_today.clear()

    # 2 uses per person per day
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

    # 10% chance of wrong info
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
        
    # Retroactive cap fix just in case they hold more than the max limit
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

    
#--------------invite event---------------------
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

    announce = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")

    if action == "start":
        if invite_event_active:
            return await i.response.send_message("Invite event is already running!", ephemeral=True)
        invite_event_active = True
        invite_counts.clear()
        invite_map.clear()
        # Cache fresh invites
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

        # Sort by invites
        sorted_inv = sorted(invite_counts.items(), key=lambda x: x[1], reverse=True)
        prizes = {0: "$10", 1: "$5", 2: "$2", 3: "$2", 4: "$1"}

        # Give 20 Aura per invite
        for uid, count in sorted_inv:
            if count > 0:
                balance[uid] += count * 20
        save_data()

        # Build results embed
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
    category = i.guild.get_channel(get_config(i.guild.id, 'PAYMENT_TICKET_CATEGORY_ID'))
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



# ================== STAFF SETUP & UTILITY COMMANDS ==================
@bot.tree.command(name="add", description="Staff: Add a user to this current channel")
async def add_user_to_current_channel(i: discord.Interaction, user: discord.Member):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)

    try:
        # i.channel automatically targets the channel the command was typed in
        await i.channel.set_permissions(
            user, 
            view_channel=True, 
            read_messages=True, 
            send_messages=True, 
            attach_files=True, 
            embed_links=True
        )
        await i.response.send_message(f"✅ Granted {user.mention} access to {i.channel.mention}.", ephemeral=True)
    except discord.Forbidden:
        await i.response.send_message("❌ I don't have permission to edit this channel's permissions. Check my role hierarchy.", ephemeral=True)
    except Exception as e:
        await i.response.send_message(f"❌ Failed: {e}", ephemeral=True)
        

@bot.tree.command(name="roast", description="Roast someone (or yourself)")
async def roast(i: discord.Interaction, user: discord.Member):
    await i.response.defer()
    
    target_bal = balance.get(user.id, 0)
    target_streak = daily_streak.get(user.id, 0)
    caller_bal = balance.get(i.user.id, 0)
    
    if user.id == bot.user.id:
        reply = await quick_ai(f"{i.user.display_name} tried to roast me, the bot. Roast them back harder. Their balance is {caller_bal} Aura. Make it funny, savage, short. 1-2 sentences. ALWAYS finish the sentence completely.", max_tokens=150)
        await i.followup.send(f"{i.user.mention} {reply if reply else 'Nice try 😂'}")
    elif user.id == i.user.id:
        reply = await quick_ai(f"Write a funny self-roast for someone named {i.user.display_name}. Their server balance is {target_bal} Aura and their daily streak is {target_streak}. Short, savage but fun. 1-2 sentences. ALWAYS finish the sentence completely.", max_tokens=150)
        await i.followup.send(f"{i.user.mention} {reply if reply else roast_bag.get_next()}")
    else:
        reply = await quick_ai(f"Roast a Discord user named {user.display_name}. Requested by {i.user.display_name}. The target's balance is {target_bal} Aura and daily streak is {target_streak}. The requester's balance is {caller_bal} Aura. Make it funny, creative, not offensive. 1-2 sentences. ALWAYS finish the sentence completely.", max_tokens=150)
        await i.followup.send(f"{user.mention} {reply if reply else roast_bag.get_next()}")

@bot.tree.command(name="hype", description="Hype someone up based on their stats")
async def hype_cmd(i: discord.Interaction, user: discord.Member):
    await i.response.defer()
    bal = balance.get(user.id, 0)
    streak = daily_streak.get(user.id, 0)
    reply = await quick_ai(f"Write a highly energetic, over-the-top hype message for a Discord user named {user.display_name}. Their server balance is {bal} Aura and their daily streak is {streak}. Make them sound like an absolute legend. 2 sentences max.", max_tokens=200)
    await i.followup.send(f"{user.mention} {reply if reply else 'You are awesome!'}")

@bot.tree.command(name="fortune", description="Get someone's daily Aura fortune")
async def fortune_cmd(i: discord.Interaction, user: discord.Member = None):
    await i.response.defer()
    target_user = user if user else i.user
    bal = balance.get(target_user.id, 0)
    reply = await quick_ai(f"Write a funny, sarcastic daily horoscope fortune for {target_user.display_name}. Their balance is {bal} Aura. Make up something absurd about their financial future in the server today. 2 sentences max.", max_tokens=200)
    await i.followup.send(f"🔮 **{target_user.display_name}'s Fortune:**\n{reply if reply else 'The stars are silent today.'}")

@bot.tree.command(name="meme", description="Generate an AI image/meme")
async def meme_cmd(i: discord.Interaction, prompt: str):
    await i.response.defer()
    import io
    from google.genai import types
    
    enhanced = await quick_ai(f"The user wants an image of '{prompt}'. Enhance this into a highly detailed, descriptive 1-sentence prompt for an AI image generator. Do not include any intro/outro text, just the prompt.", max_tokens=150)
    
    try:
        response = await vertex_client.aio.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=enhanced or prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1"
            )
        )
        
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            file = discord.File(io.BytesIO(image_bytes), filename="meme.jpeg")
            
            embed = discord.Embed(title=f"🎨 {prompt}", description=f"*Generated Prompt: {enhanced}*" if enhanced else "", color=discord.Color.purple())
            embed.set_image(url="attachment://meme.jpeg")
            embed.set_footer(text=f"Requested by {i.user.display_name}")
            
            await i.followup.send(embed=embed, file=file)
        else:
            await i.followup.send("❌ The image generator returned no image. Please try a different prompt.")
    except Exception as e:
        await i.followup.send(f"❌ Error generating image: {e}")

@bot.tree.command(name="confess", description="Submit an anonymous confession")
async def confess(i: discord.Interaction, message: str):
    channel = bot.get_channel(get_config(i.guild.id, "CONFESSION_CHANNEL_ID"))
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

    # Pick the one ending soonest
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

    log_ch = bot.get_channel(get_config(i.guild.id, "GIVE_LOG_CHANNEL_ID"))
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

    log_ch = bot.get_channel(get_config(i.guild.id, "GIVE_LOG_CHANNEL_ID"))
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
        await user.ban(reason=f"Banned by {i.user.display_name} - {reason}", delete_message_seconds=delete_history * 86400)
        await i.response.send_message(embed=discord.Embed(title="🔨 User Banned", description=f"**User:** {user.mention}\n**Reason:** {reason}\n**Deleted Msgs:** {delete_history} days", color=discord.Color.red()))
    except discord.Forbidden: 
        await i.response.send_message("❌ I do not have permission to ban this user.", ephemeral=True)
        


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
    
    await i.response.send_message(f"✅ Custom AI Prompt set successfully! The bot will now act like this:\n\n`{prompt_text}`", ephemeral=True)

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
        return await i.response.send_message("💎 **Premium Servers:**\n" + "\n".join(servers), ephemeral=True)
        
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

@bot.tree.command(name="force_market", description="Admin Only: Secretly nudge a coin's price towards a target over time")
@app_commands.choices(coin=[app_commands.Choice(name=c, value=c) for c in DEFAULT_STOCKS.keys()])
@app_commands.default_permissions(administrator=True) # Hides it from regular users in the menu
async def force_market(i: discord.Interaction, coin: str, target_price: float):
    # 1. Strict Role Check (Only this exact Role ID can pass)
    ADMIN_ROLE_ID = 1448719741756768308
    has_admin_role = any(role.id == get_config(i.guild.id, "ADMIN_ROLE_ID") for role in i.user.roles)
    
    if not has_admin_role:
        return await i.response.send_message("🛑 You do not have the required Admin role to use this command.", ephemeral=True)
        
    if target_price < 0:
        return await i.response.send_message("Target price cannot be negative.", ephemeral=True)
        
    # 2. Inject target into the background loop
    force_market_targets[coin] = target_price
    
    # 3. Secret confirmation
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
    
    chat_channel = GlobalChannelProxy("CHAT_CHANNEL_ID")
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
        
    channel = GlobalChannelProxy("BIRTHDAY_CHANNEL_ID")
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

    

#-------------------tickets-------------------------------


@bot.tree.command(name="setup_config", description="Staff: Configure server specific channels and roles")
@app_commands.describe(
    chat_channel="Main chat channel",
    payout_channel="Channel for payouts",
    announce_channel="Channel for daily announcements",
    public_log_channel="Public logging channel",
    help_channel="Support/Help channel",
    confession_channel="Confession channel",
    birthday_channel="Birthday announcements channel",
    admin_role="Admin role for full bot access",
    master_sheet_url="Link to the Master Pay Sheet"
)
async def setup_config(
    i: discord.Interaction, 
    chat_channel: discord.TextChannel = None,
    payout_channel: discord.TextChannel = None,
    announce_channel: discord.TextChannel = None,
    public_log_channel: discord.TextChannel = None,
    help_channel: discord.TextChannel = None,
    confession_channel: discord.TextChannel = None,
    birthday_channel: discord.TextChannel = None,
    admin_role: discord.Role = None,
    master_sheet_url: str = None
):
    if not is_staff(i.user):
        return await i.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
    
    guild_id = str(i.guild.id)
    if guild_id not in server_configs:
        server_configs[guild_id] = {}
        
    updated = False
    if chat_channel: server_configs[guild_id]["CHAT_CHANNEL_ID"] = chat_channel.id; updated = True
    if payout_channel: server_configs[guild_id]["PAYOUT_CHANNEL_ID"] = payout_channel.id; updated = True
    if announce_channel: server_configs[guild_id]["DAILY_ANNOUNCE_CHANNEL_ID"] = announce_channel.id; updated = True
    if public_log_channel: server_configs[guild_id]["PUBLIC_LOG_CHANNEL_ID"] = public_log_channel.id; updated = True
    if help_channel: server_configs[guild_id]["HELP_CHANNEL_ID"] = help_channel.id; updated = True
    if confession_channel: server_configs[guild_id]["CONFESSION_CHANNEL_ID"] = confession_channel.id; updated = True
    if birthday_channel: server_configs[guild_id]["BIRTHDAY_CHANNEL_ID"] = birthday_channel.id; updated = True
    if admin_role: server_configs[guild_id]["ADMIN_ROLE_ID"] = admin_role.id; updated = True
    if master_sheet_url: server_configs[guild_id]["MASTER_SHEET_URL"] = master_sheet_url; updated = True
    
    if updated:
        save_data()
        await i.response.send_message("✅ General configuration has been updated for this server. For ticket verification, use `/setup_verify`.", ephemeral=True)
    else:
        await i.response.send_message("ℹ️ No configuration options were provided to update.", ephemeral=True)

@bot.tree.command(name="setup_verify", description="Staff: Configure the roles and categories for ticket verification on this server")
@app_commands.describe(
    payment_category="Category for payment tickets",
    aged_role="Role for 1+ year old Reddit accounts",
    karma_role="Role for 1000+ Karma Reddit accounts",
    cqs_highest="Role for Highest CQS",
    cqs_high="Role for High CQS",
    cqs_mod="Role for Moderate CQS",
    cqs_low="Role for Low CQS"
)
async def setup_verify(
    i: discord.Interaction, 
    payment_category: discord.CategoryChannel = None,
    aged_role: discord.Role = None,
    karma_role: discord.Role = None,
    cqs_highest: discord.Role = None,
    cqs_high: discord.Role = None,
    cqs_mod: discord.Role = None,
    cqs_low: discord.Role = None
):
    if not is_staff(i.user):
        return await i.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
    
    guild_id = str(i.guild.id)
    if guild_id not in server_configs:
        server_configs[guild_id] = {}
        
    updated = False
    if payment_category: server_configs[guild_id]["PAYMENT_TICKET_CATEGORY_ID"] = payment_category.id; updated = True
    if aged_role: server_configs[guild_id]["AGED_ACC_ROLE_ID"] = aged_role.id; updated = True
    if karma_role: server_configs[guild_id]["HIGH_KARMA_ROLE_ID"] = karma_role.id; updated = True
    if cqs_highest: server_configs[guild_id]["CQS_HIGHEST_ROLE_ID"] = cqs_highest.id; updated = True
    if cqs_high: server_configs[guild_id]["CQS_HIGH_ROLE_ID"] = cqs_high.id; updated = True
    if cqs_mod: server_configs[guild_id]["CQS_MOD_ROLE_ID"] = cqs_mod.id; updated = True
    if cqs_low: server_configs[guild_id]["CQS_LOW_ROLE_ID"] = cqs_low.id; updated = True
    
    if updated:
        save_data()
        await i.response.send_message("✅ Verification configuration has been updated for this server.", ephemeral=True)
    else:
        await i.response.send_message("ℹ️ No configuration options were provided to update.", ephemeral=True)


@bot.tree.command(name="verify", description="Staff: Verify ticket")
async def verify(i: discord.Interaction, user: discord.Member, role1: Optional[discord.Role]=None, role2: Optional[discord.Role]=None, role3: Optional[discord.Role]=None):
    if not is_staff(i.user) or not is_ticket_channel(i.channel): 
        return await i.response.send_message("Staff/Ticket channel only.", ephemeral=True)

    await i.response.defer()

    try:
        new_name = user.display_name[:100]
        await i.channel.edit(name=new_name)
        
        for rid in get_config(i.guild.id, "REMOVE_ROLE_IDS"):
            r = i.guild.get_role(rid)
            if r and r in user.roles: 
                await user.remove_roles(r)
                
        roles_to_add = [i.guild.get_role(rid) for rid in get_config(member.guild.id if "member" in locals() and hasattr(member, "guild") and member.guild else 0, "AUTO_ROLE_IDS") if isinstance(rid, int) and i.guild.get_role(rid)]
        
        if role1: roles_to_add.append(role1)
        if role2: roles_to_add.append(role2)
        if role3: roles_to_add.append(role3)
            
        if roles_to_add: 
            await user.add_roles(*roles_to_add)
        
        formatted_ticket_name = new_name.lower().replace(" ", "-")
        desc = (f"**Welcome!** {user.mention}\nTo claim tasks, please send your ticket as soon as tasks are available.\n\n**📍 Where to send your ticket:**\n<#1518207367941193972>\n<#1518207420487172156>\n<#1518207461650202755>\n\n**Important points:**\n- Your ticket name is **#{formatted_ticket_name}**\n- Task channels are opened only when tasks are available\n\n{E_VIBE} **Time to earn!!!**")
        
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
    msg_content = (
        f"{user.mention}\n"
        f"If you were rejected for low karma, please read <#1449052486668255262>.\n"
        f"If you have any doubts, go to the help channel <#1448787031810642010>."
    )
    await i.response.send_message(content=msg_content, embed=discord.Embed(title=f"{E_WARN} Application Update", description=desc, color=discord.Color.red()))

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
        # Clear guild-specific copies that cause duplicates
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
    ch = GlobalChannelProxy("DAILY_ANNOUNCE_CHANNEL_ID")
    if not ch:
        return await i.followup.send("Announce channel not found.", ephemeral=True)

    # Top earner
    top_earner_id = max(weekly_aura_earned, key=weekly_aura_earned.get) if weekly_aura_earned else None
    top_earner_name = ""
    if top_earner_id:
        for g in bot.guilds:
            m = g.get_member(top_earner_id)
            if m:
                top_earner_name = m.display_name
                break
        top_earner_name = top_earner_name or f"<@{top_earner_id}>"

    # Biggest casino loser
    top_loser_id = max(weekly_casino_lost, key=weekly_casino_lost.get) if weekly_casino_lost else None
    top_loser_name = ""
    if top_loser_id:
        for g in bot.guilds:
            m = g.get_member(top_loser_id)
            if m:
                top_loser_name = m.display_name
                break
        top_loser_name = top_loser_name or f"<@{top_loser_id}>"

    # Biggest stock move
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
    # Giving it 600 tokens so it never gets cut off
    recap = await quick_ai(prompt, max_tokens=2000)
    if recap and len(recap) > 4000:
        recap = recap[:4000] + "..."

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
        
    channel = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
    if not channel:
        return await i.response.send_message("Chat channel not found.", ephemeral=True)
        
    # Pick a puzzle
    available = [p for p in PUZZLES if p["a"] not in used_puzzles]
    if not available:
        used_puzzles.clear()
        available = list(PUZZLES)
        
    puzzle = random.choice(available)
    used_puzzles.append(puzzle["a"])
    
    # Activate it
    active_puzzle["question"] = puzzle["q"]
    active_puzzle["answer"] = puzzle["a"]
    active_puzzle["type"] = puzzle.get("type", "riddle")
    active_puzzle["solved"] = False
    save_data()
    
    # Build the embed
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
    
@bot.tree.command(name="add_role_to_tickets", description="Staff: Grant a role access to all current ticket channels")
async def add_role_to_tickets(i: discord.Interaction, role: discord.Role):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)
        
    # Defer the response because updating many channels can take a few seconds
    await i.response.defer(ephemeral=True)
    
    # Combine both your standard ticket categories and the payment category
    all_ticket_categories = TICKET_CATEGORY_IDS | {get_config(i.guild.id if hasattr(i, "guild") and i.guild else None, "PAYMENT_TICKET_CATEGORY_ID")}
    updated_count = 0
    
    for channel in i.guild.text_channels:
        if channel.category and channel.category.id in all_ticket_categories:
            try:
                # Grant the role permission to view and send messages in the ticket
                await channel.set_permissions(role, view_channel=True, read_messages=True, send_messages=True)
                updated_count += 1
            except Exception as e:
                import logging
                logging.error(f"Failed to update permissions for {channel.name}: {e}")
                
    await i.followup.send(f"✅ Successfully granted {role.mention} access to **{updated_count}** ticket channels.", ephemeral=True)
    
# --- GLOBAL LOCK VARIABLE ---
# Place this at the top of your file with your other configuration variables
is_verifying_locked = False

# ==========================================
# VERIFY SHEET COMMAND
# ==========================================
@bot.tree.command(name="verify_sheet", description="Grade your task sheet and push to the Master Pay Sheet")
@app_commands.describe(sheet_url="Link to the Google Sheet")
async def verify_sheet(i: discord.Interaction, sheet_url: str):
    global is_verifying_locked
    
    # 0. Check Concurrency Lock
    if is_verifying_locked:
        return await i.response.send_message(
            "⏳ **Hold up!** Someone else is currently verifying a sheet. Please wait for them to finish, then try again.", 
            ephemeral=True
        )
        
    is_verifying_locked = True
    await i.response.defer()
    
    MASTER_SHEET_URL = get_config(i.guild.id, "MASTER_SHEET_URL")
    
    try:
        reddit_token = await get_reddit_token()
        if not reddit_token:
            return await i.followup.send("❌ Failed to authenticate with Reddit API.")

        if gc is None:
            return await i.followup.send("❌ Google Sheets API is disconnected.")

        user_sheet = gc.open_by_url(sheet_url).sheet1
        
        # --- ANTI-SPAM STAMP CHECK ---
        stamp = user_sheet.acell('A1').value
        if "VERIFIED" in str(stamp).upper():
            is_verifying_locked = False 
            return await i.followup.send("❌ **Already Verified!** This sheet has already been processed.")

        # --- MANDATORY NAME CHECK (Moved to top so it fails fast) ---
        target_name_raw = user_sheet.acell('B2').value
        if not target_name_raw or str(target_name_raw).strip() == "":
            is_verifying_locked = False
            return await i.followup.send("❌ **Error:** Cell B2 in the user's sheet is empty. Please enter the member's name.")
        
        target_name = str(target_name_raw).strip()

        payment_address = user_sheet.acell('B3').value or "NO ADDRESS PROVIDED"
        profile_link = user_sheet.acell('C5').value or ""
        
        display_rows = user_sheet.get_all_values()
        try:
            formula_rows = user_sheet.get("A1:Z200", value_render_option='FORMULA')
        except:
            formula_rows = []

        # 1.5 INITIALIZE LISTS OUTSIDE THE LOOP (Fixes the "None" embed issue)
        stats = {"active": 0, "mod_removed": 0, "filtered": 0, "failed": 0}
        mod_rows, filtered_rows, failed_rows = [], [], []
        updates = [] 
        
        total_row_idx = None
        total_col_idx = None
        
        # 1. Find the "Total Earnings" row dynamically
        for r_idx, r in enumerate(display_rows[:25]): 
            row_text = [str(cell).lower().strip() for cell in r]
            if "total earnings:" in row_text or "total earnings" in row_text:
                for c_idx, cell in reversed(list(enumerate(r))):
                    if str(cell).strip() != "" and "total" not in str(cell).lower() and str(cell) != "FALSE":
                        total_row_idx = r_idx + 1 
                        total_col_idx = c_idx + 1
                        break

        # 2. Loop through all rows to find and verify Reddit/Image links
        for row_idx, row in enumerate(display_rows):
            sheet_row = row_idx + 1
            
            # Skip everything above and including the Total Earnings row
            if total_row_idx and sheet_row <= total_row_idx + 1:
                continue
                
            # --- THE RESET --- 
            # Clear G (Filtered) and H (Mod Removed) by setting them to False (Unchecked)
            updates.append({'range': f'G{sheet_row}:H{sheet_row}', 'values': [[False, False]]})
                
            url = None
            col_found_in = -1
            
            for c_idx, cell in enumerate(row):
                # STRICT FILTER: We ONLY care about Column C (index 2) and Column D (index 3)
                if c_idx not in [2, 3]:
                    continue
                    
                display_val = str(cell).strip()
                text_to_check = display_val
                
                if len(formula_rows) > row_idx and len(formula_rows[row_idx]) > c_idx:
                    formula_val = str(formula_rows[row_idx][c_idx]).strip()
                    if "hyperlink" in formula_val.lower():
                        text_to_check = formula_val

                if "http" in text_to_check.lower() or "reddit" in text_to_check.lower():
                    url_match = re.search(r'(https?://[^\s"]+)', text_to_check)
                    if url_match:
                        url = url_match.group(1)
                        col_found_in = c_idx
                        break # Found a link in either C or D, stop scanning this row
            
            if url:
                # Ignore Reddit user profile links completely
                if "/user/" in url.lower() or "/u/" in url.lower():
                    continue

                # --- NEW COLUMN-BASED LOGIC ---
                # 1. If the link was found in Column D, it's ALWAYS a screenshot/proof!
                if col_found_in == 3:
                    status = "Screenshot"
                # 2. If it's a Reddit link in Column C, grade it!
                elif "reddit.com" in url.lower() or "redd.it" in url.lower():
                    status = await verify_reddit_post(url, reddit_token)
                # 3. Anything else in Column C is an invalid task link
                else:
                    status = "Invalid Link"
                
                # Apply Status Logic, Colors, Checkboxes, and Collect Rows
                if status == "Active": 
                    stats["active"] += 1
                elif status == "Mod Removed":
                    stats["mod_removed"] += 1
                    mod_rows.append(str(sheet_row))
                    updates.append({'range': f'H{sheet_row}', 'values': [[True]]}) # TICK MOD REMOVED
                    user_sheet.format(f'A{sheet_row}:H{sheet_row}', {'backgroundColor': {'red': 1.0, 'green': 0.6, 'blue': 0.0}})
                elif status in ["Filtered", "Deleted"]:
                    stats["filtered"] += 1
                    filtered_rows.append(str(sheet_row))
                    updates.append({'range': f'G{sheet_row}', 'values': [[True]]}) # TICK FILTERED
                    user_sheet.format(f'A{sheet_row}:H{sheet_row}', {'backgroundColor': {'red': 1.0, 'green': 0.0, 'blue': 0.0}})
                elif status == "Invalid Link":
                    stats["failed"] += 1
                    failed_rows.append(str(sheet_row))
                    updates.append({'range': f'G{sheet_row}', 'values': [[True]]}) # TICK FILTERED (Penalty)
                    user_sheet.format(f'A{sheet_row}:H{sheet_row}', {'backgroundColor': {'red': 1.0, 'green': 1.0, 'blue': 0.0}})
                elif status == "Screenshot":
                    # Paint Column D links light blue for manual review
                    user_sheet.format(f'A{sheet_row}:H{sheet_row}', {'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0}})
                else:
                    stats["failed"] += 1 
                    
                await asyncio.sleep(1.2)
            else:
                # No URL found in C or D. Check if amount is listed.
                # Only check columns E (4) and F (5) to avoid triggering on G/H checkboxes.
                has_amount = False
                for c_idx in range(4, min(6, len(row))):
                    val = str(row[c_idx]).strip().upper()
                    # Ignore empty, checkboxes, or zero amounts
                    if val and val not in ["FALSE", "TRUE", "-", "0", "0.00", "$0", "$0.00"]:
                        if not re.match(r'^[\$€£₹]?\s*0([.,]0+)?$', val):
                            has_amount = True
                            break
                
                if has_amount:
                    stats["filtered"] += 1
                    filtered_rows.append(str(sheet_row))
                    updates.append({'range': f'G{sheet_row}', 'values': [[True]]}) # TICK FILTERED
                    user_sheet.format(f'A{sheet_row}:H{sheet_row}', {'backgroundColor': {'red': 1.0, 'green': 0.0, 'blue': 0.0}})
                    await asyncio.sleep(1.2)

        if updates:
            user_sheet.batch_update(updates)
            
        await asyncio.sleep(2.0) 
        
        # 3. Calculate Payout (Clean Number for SUM function)
        final_amount_str = "0,00"
        if total_row_idx and total_col_idx:
            raw_val = str(user_sheet.cell(total_row_idx, total_col_idx).value)
            # Remove $ and spaces, convert dot to comma
            final_amount_str = raw_val.replace('$', '').replace(' ', '').replace('.', ',')

        # 4. Update Master Sheet 
        master_sheet = gc.open_by_url(MASTER_SHEET_URL).get_worksheet(0)
        all_master_rows = master_sheet.get_all_values()
        
        row_to_update = -1
        empty_row_idx = -1
        
        for idx, row in enumerate(all_master_rows):
            # Ensure row has enough columns
            while len(row) < 6: row.append("")
                
            # Compare against the name found in the sheet
            if row[1].strip().lower() == target_name.lower():
                row_to_update = idx + 1
                break
                
            if row[1].strip() == "" and empty_row_idx == -1 and idx > 0:
                empty_row_idx = idx + 1
        
        if row_to_update != -1:
            master_sheet.update(range_name=f'C{row_to_update}', values=[[final_amount_str]], value_input_option='USER_ENTERED')
            master_sheet.update(range_name=f'F{row_to_update}', values=[[profile_link]], value_input_option='USER_ENTERED')
        else:
            # Use the target_name taken from the sheet
            new_row_data = ["FALSE", target_name, final_amount_str, payment_address, "", profile_link]
            if empty_row_idx != -1:
                master_sheet.update(range_name=f'A{empty_row_idx}:F{empty_row_idx}', values=[new_row_data], value_input_option='USER_ENTERED')
            else:
                master_sheet.append_row(new_row_data, value_input_option='USER_ENTERED')
                
        # --- STAMP THE SHEET AS COMPLETED (Fixed for IST) ---
        from datetime import datetime, timezone, timedelta
        
        # Create IST timezone object (UTC+5:30)
        ist = timezone(timedelta(hours=5, minutes=30))
        ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M')
        
        try:
            user_sheet.update(range_name='A1', values=[[f"VERIFIED - {ist_time}"]], value_input_option='USER_ENTERED')
        except:
            pass
        
        # 5. Final Embed
        embed = discord.Embed(title="🧾 Task Sheet Graded & Logged", color=0x00FF00)
        embed.description = f"Graded for **{target_name}**."
        
        embed.add_field(name="✅ Active", value=str(stats['active']), inline=True)
        
        # Display Mod Removed rows
        mod_val = f"{stats['mod_removed']} (Rows: {', '.join(mod_rows)})" if mod_rows else "0"
        embed.add_field(name="⚠️ Mod Removed", value=mod_val, inline=False)
        
        # Display Filtered rows
        filt_val = f"{stats['filtered']} (Rows: {', '.join(filtered_rows)})" if filtered_rows else "0"
        embed.add_field(name="❌ Filtered", value=filt_val, inline=False)
        
        if stats['failed'] > 0:
            embed.add_field(name="🚨 Invalid Links", value=f"**{stats['failed']}** (Rows: {', '.join(failed_rows)})", inline=False)
            
        embed.add_field(name="📸 Upvotes/Screenshots", value="Highlighted **LIGHT BLUE** for manual review.", inline=False)
        embed.add_field(name="💰 Final Payout", value=f"**{final_amount_str}**", inline=False)
        await i.followup.send(embed=embed)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        await i.followup.send(f"❌ **Fatal error.** Check console: \n`{e}`")
    
    finally:
        is_verifying_locked = False
        
# ==========================================
# REMINDER COMMANDS
# ==========================================
@bot.tree.command(name="set_reminder", description="Set a repeating reminder in this channel")
@app_commands.choices(frequency=[
    app_commands.Choice(name="Weekly (e.g. thursday)", value="weekly"),
    app_commands.Choice(name="Monthly (e.g. 1)", value="monthly")
])
async def set_reminder(i: discord.Interaction, frequency: app_commands.Choice[str], day_or_date: str, time_ist: str, message: str):
    
    # Validation checks
    if frequency.value == "weekly" and day_or_date.lower() not in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        return await i.response.send_message("❌ For weekly reminders, type a full day name (e.g., 'thursday').", ephemeral=True)
    if frequency.value == "monthly" and not day_or_date.isdigit():
        return await i.response.send_message("❌ For monthly reminders, type a number from 1 to 31.", ephemeral=True)
        
    rem_id = str(uuid.uuid4().hex)[:6] 
    
    reminders_db[rem_id] = {
        "channel": i.channel.id,
        "freq": frequency.value,
        "day_or_date": day_or_date.lower(),
        "time": time_ist, # Now saves whatever 24h IST time you type
        "message": message,
        "author": i.user.id
    }
    save_reminders(reminders_db)
    
    await i.response.send_message(
        f"✅ **Reminder Set!** (ID: `{rem_id}`)\n"
        f"I will send this message here every **{day_or_date.capitalize()}** at **{time_ist} IST**."
    )

@bot.tree.command(name="cancel_reminder", description="Cancel a reminder using its ID")
async def cancel_reminder(i: discord.Interaction, reminder_id: str):
    if reminder_id in reminders_db:
        del reminders_db[reminder_id]
        save_reminders(reminders_db)
        await i.response.send_message(f"🗑️ Deleted reminder `{reminder_id}`.")
    else:
        # If they type the wrong ID, show them the active ones in that channel to help them out
        active = "\n".join([f"`{k}`: {v['freq']} on {v['day_or_date']} at {v['time']}" for k, v in reminders_db.items() if v['channel'] == i.channel.id])
        if not active:
            active = "There are no active reminders in this channel."
        await i.response.send_message(f"❌ Reminder ID not found. Active reminders here:\n{active}", ephemeral=True)
        
# --- UPVOTEMAX CONFIGURATION ---
UPVOTEMAX_API_KEY = os.getenv("UPVOTEMAX_API_KEY")
UPVOTEMAX_URL = "https://upvotemax.com/api/public/v1/orders"
ALLOWED_UPVOTE_ROLES = [1448719741756768308, 1449035039072452800]  # Allowed roles for upvoting

UPVOTE_ORDERS_FILE = "upvote_orders.json"

def load_upvote_orders():
    import os, json
    if os.path.exists(UPVOTE_ORDERS_FILE):
        with open(UPVOTE_ORDERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_upvote_orders(data):
    import json
    with open(UPVOTE_ORDERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

upvote_orders_db = load_upvote_orders()

from discord.ext import tasks

@tasks.loop(minutes=5)
async def check_upvote_orders():
    if not upvote_orders_db:
        return
        
    order_ids = list(upvote_orders_db.keys())
    for i in range(0, len(order_ids), 100):
        batch = order_ids[i:i+100]
        payload = {"orders": batch}
        headers = {"x-api-key": UPVOTEMAX_API_KEY, "Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://upvotemax.com/api/public/v1/status", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        orders_res = data.get("orders", {})
                        
                        items = []
                        if isinstance(orders_res, dict):
                            items = orders_res.items()
                        elif isinstance(orders_res, list):
                            items = [(str(o.get("order", o.get("id"))), o) for o in orders_res]
                            
                        changed = False
                        for oid, details in items:
                            status = str(details.get("status", "")).lower()
                            if status in ["completed", "failed", "partial", "canceled"]:
                                order_info = upvote_orders_db.get(oid)
                                if order_info:
                                    channel = bot.get_channel(order_info["channel_id"])
                                    if channel:
                                        color = discord.Color.green() if status == "completed" else discord.Color.red()
                                        embed = discord.Embed(
                                            title=f"✅ Order {status.title()}",
                                            description=f"Your `{order_info['action']}` order for `{order_info['quantity']}` votes has finished.",
                                            color=color
                                        )
                                        embed.add_field(name="Order ID", value=f"`{oid}`")
                                        embed.add_field(name="Target Link", value=f"[Open Link]({order_info['target_url']})")
                                        await channel.send(content=f"<@{order_info['user_id']}>", embed=embed)
                                    del upvote_orders_db[oid]
                                    changed = True
                        if changed:
                            save_upvote_orders(upvote_orders_db)
        except Exception as e:
            logging.error(f"Error checking provider orders: {e}")

@bot.tree.command(
    name="reddit_vote", 
    description="Admin Only: Deploy Reddit upvotes/downvotes"
)
@app_commands.describe(
    target_url="Link to the Reddit post or comment", 
    action="Type of action",
    quantity="How many votes to send (minimum usually 10)",
    speed="Speed of delivery per hour (Optional, 10-5000)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Post Upvote", value="post_upvote"),
    app_commands.Choice(name="Post Downvote", value="post_downvote"),
    app_commands.Choice(name="Comment Upvote", value="comment_upvote"),
    app_commands.Choice(name="Comment Downvote", value="comment_downvote"),
])
async def reddit_vote(
    i: discord.Interaction, 
    target_url: str, 
    action: app_commands.Choice[str], 
    quantity: int,
    speed: int = 50
):
    # 1. Strict Admin Role Verification
    has_role = any(role.id in ALLOWED_UPVOTE_ROLES for role in i.user.roles)
    if not has_role:
        return await i.response.send_message(
            "❌ **Access Denied:** This command is strictly restricted to authorized administrators.", 
            ephemeral=True
        )

    if quantity < 10:
        return await i.response.send_message(
            "❌ **Order Rejected:** Minimum quantity is usually 10.", 
            ephemeral=True
        )

    await i.response.defer(ephemeral=False)

    payload = {
        "service": action.value,
        "link": target_url,
        "quantity": quantity,
        "speed": speed
    }
    
    headers = {
        "x-api-key": UPVOTEMAX_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(UPVOTEMAX_URL, json=payload, headers=headers) as resp:
                data = {}
                try:
                    data = await resp.json()
                except:
                    text = await resp.text()
                    return await i.followup.send(f"❌ **API Error Code {resp.status}:** Could not connect to provider. Response: `{text[:200]}`")

                if resp.status not in [200, 201]:
                    error_msg = data.get("message") or data.get("error") or str(data)
                    return await i.followup.send(f"❌ **API Error Code {resp.status}:** `{error_msg}`")

        # Process Output
        if data.get("status") in ["success", "ok", "Created"] or "order" in data or "id" in data or "orderId" in data:
            order_id = data.get("order") or data.get("id") or data.get("orderId") or "Unknown"

            embed = discord.Embed(
                title="⚡ Campaign Deployed Successfully",
                description=f"Your order has been routed successfully.",
                color=discord.Color.red()
            )
            embed.add_field(name="Target Link", value=f"[Open Link]({target_url})", inline=False)
            embed.add_field(name="Action", value=f"📈 **{action.name}**", inline=True)
            embed.add_field(name="Quantity", value=f"🎯 **{quantity}**", inline=True)
            embed.add_field(name="Speed", value=f"⏱️ **{speed}/hr**", inline=True)
            embed.add_field(name="Order ID", value=f"`{order_id}`", inline=False)
            embed.set_footer(text=f"Executed by Admin: {i.user.display_name}")
            
            await i.followup.send(embed=embed)
            
            upvote_orders_db[str(order_id)] = {
                "user_id": i.user.id,
                "channel_id": i.channel.id,
                "action": action.name,
                "quantity": quantity,
                "target_url": target_url
            }
            save_upvote_orders(upvote_orders_db)
            
        else:
            error_msg = data.get("error") or data.get("message") or "Unknown API Error"
            await i.followup.send(f"❌ **Panel API Error:** `{error_msg}`\nDetails: `{data}`")

    except Exception as e:
        await i.followup.send(f"❌ **Network Exception:** Connection failed. `{e}`")
        
@bot.tree.command(name="delete_inactive_tickets", description="Staff: Delete inactive tickets across ALL ticket categories at once")
@app_commands.describe(
    days="Days since last message to consider inactive (Default: 14)",
    hours="Hours since last message (Default: 0)",
    minutes="Minutes since last message (Default: 0)"
)
@app_commands.default_permissions(manage_channels=True)
async def delete_inactive_tickets(
    i: discord.Interaction,
    days: int = 14,
    hours: int = 0,
    minutes: int = 0
):
    if not is_staff(i.user):
        return await i.response.send_message("Staff only.", ephemeral=True)

    await i.response.defer()

    # All ticket category IDs (standard + payment)
    all_ticket_category_ids = TICKET_CATEGORY_IDS | {get_config(message.guild.id if hasattr(message, "guild") and message.guild else None, "PAYMENT_TICKET_CATEGORY_ID")}

    cutoff_date = discord.utils.utcnow() - datetime.timedelta(days=days, hours=hours, minutes=minutes)
    time_desc = f"{days}d {hours}h {minutes}m"

    total_deleted = 0
    total_kept = 0
    total_errored = 0
    category_results = []

    for cat_id in all_ticket_category_ids:
        category = i.guild.get_channel(cat_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            continue

        deleted_count = 0
        kept_count = 0

        for channel in category.text_channels:
            try:
                messages = [msg async for msg in channel.history(limit=1)]
                last_activity = messages[0].created_at if messages else channel.created_at

                if last_activity <= cutoff_date:
                    await channel.delete(reason=f"Auto-cleanup: Inactive for {time_desc} by {i.user.display_name}")
                    deleted_count += 1
                    total_deleted += 1
                else:
                    kept_count += 1
                    total_kept += 1

            except Exception as e:
                logging.error(f"Skipped {channel.name} in {category.name}: {e}")
                total_errored += 1
                kept_count += 1

        if deleted_count > 0 or kept_count > 0:
            category_results.append(f"**{category.name}** — 🗑️ {deleted_count} deleted, ✅ {kept_count} kept")

    embed = discord.Embed(
        title="🗑️ Inactive Ticket Cleanup Complete",
        description=f"Threshold: **{time_desc}** of inactivity",
        color=0xFF4444,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="📊 Overall Results",
        value=f"🗑️ **Deleted:** {total_deleted}\n✅ **Kept:** {total_kept}\n⚠️ **Errors:** {total_errored}",
        inline=False
    )
    if category_results:
        # Split into chunks to avoid embed field limit
        chunk_size = 10
        for idx in range(0, len(category_results), chunk_size):
            chunk = category_results[idx:idx + chunk_size]
            embed.add_field(
                name=f"📁 Categories ({idx + 1}–{idx + len(chunk)})",
                value="\n".join(chunk),
                inline=False
            )
    embed.set_footer(text=f"Run by {i.user.display_name}")

    await i.followup.send(embed=embed)

@bot.tree.command(name="add_puzzle", description="Staff: Add a custom puzzle")
@app_commands.choices(ptype=[
    app_commands.Choice(name="Riddle", value="riddle"),
    app_commands.Choice(name="Word Scramble", value="scramble"),
    app_commands.Choice(name="Math", value="math"),
    app_commands.Choice(name="Emoji", value="emoji"),
    app_commands.Choice(name="Fill in the Blank", value="fillblank")
])
async def add_puzzle(i: discord.Interaction, ptype: app_commands.Choice[str], question: str, answer: str):
    if not is_staff(i.user):
        return await i.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
    
    new_puzzle = {"type": ptype.value, "q": question, "a": answer}
    
    custom_puzzles = data.get("custom_puzzles", [])
    custom_puzzles.append(new_puzzle)
    data["custom_puzzles"] = custom_puzzles
    save_data()
    
    PUZZLES.append(new_puzzle)
    
    global active_puzzle
    active_puzzle["question"] = question
    active_puzzle["answer"] = answer
    active_puzzle["type"] = ptype.value
    active_puzzle["solved"] = False
    save_data()

    channel = bot.get_channel(get_config(guild.id, "CHAT_CHANNEL_ID")) if "guild" in locals() and guild else GlobalChannelProxy("CHAT_CHANNEL_ID")
    if channel:
        type_config = {
            "riddle":    ("🧩", "Riddle",            discord.Color.purple(),  "Think carefully and type your answer!"),
            "scramble":  ("🔀", "Word Scramble",      discord.Color.orange(),  "Unscramble the letters to find the word!"),
            "math":      ("🔢", "Math Challenge",     discord.Color.blue(),    "Type just the number as your answer!"),
            "trivia":    ("🎯", "Trivia Question",    discord.Color.gold(),    "Type your answer in chat!"),
            "emoji":     ("🎭", "Emoji Puzzle",       discord.Color.fuchsia(), "Decode the emojis and type what it represents!"),
            "fillblank": ("✏️", "Fill in the Blank",  discord.Color.green(),   "Type the missing word to complete the phrase!"),
        }
        emoji_icon, type_name, color, hint = type_config.get(ptype.value, ("🧩", "Puzzle", discord.Color.purple(), "Type your answer!"))
        
        embed = discord.Embed(
            title=f"{emoji_icon} {type_name} — First to answer wins 50 Aura!",
            description=f"**{question}**\n\n*{hint}*",
            color=color
        )
        embed.set_footer(text=f"⚙️ Added by Staff  •  Type: {type_name}")
        
        await channel.send(embed=embed)
        await i.response.send_message(f"✅ Successfully added and forced puzzle into chat: **{question}** (Answer: {answer})", ephemeral=True)
    else:
        await i.response.send_message(f"✅ Successfully added puzzle: **{question}** (Answer: {answer}), but couldn't find chat channel to drop it.", ephemeral=True)

bot.run(TOKEN)
