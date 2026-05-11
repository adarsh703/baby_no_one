```markdown
# 🤖 baby_no_one - Advanced Discord Economy & AI Bot

A highly advanced, feature-rich Discord bot combining a complex simulated economy, dynamic stock market, PvP casino games, and intelligent AI conversations powered by Google's Vertex AI (Gemini 2.5 Flash). 

Designed to feel like a real, slightly witty server member rather than a robotic assistant, **baby_no_one** drives community engagement through constant background events, hidden easter eggs, and high-stakes gambling.

---

## ✨ Core Features

### 🧠 Intelligent AI Integration (Vertex AI)
* **Conversational AI:** Responds naturally to pings, tracks conversation history, and adapts to the language used (English/Hinglish).
* **Persistent Memory:** Uses AI to extract and remember key facts about users over time.
* **Background Personalities:** Automatically drops science facts, daily market hot takes, and server mood checks based on chat activity.
* **Smart Parsing:** AI determines if users are asking for money, requesting tasks, or just chatting, and reacts accordingly.

### 📈 Dynamic Stock Market
* **Live Mod Coins:** A fully simulated stock market with coins like `$No_ONe`, `$MUFFIN`, and `$DJ_hunks`.
* **Market Physics:** Features realistic market movements including bubble bursts, gravity mechanics, random shock events, and "rugpulls".
* **Visual Charts:** Generates in-text sparklines, line graphs, area charts, and candlestick charts for live price tracking (`/coin_chart`).
* **Insider Trading:** Users can bribe the bot for insider tips on coin movements (with a 20% chance of fake info).
* **Delistings:** Coins that crash to 0 are temporarily delisted, wiping portfolios and paying out a 10% liquidation fee.

### 🎰 Casino & PvP Games
* **Single Player:** Blackjack (`/bj`), French Roulette (`/french_roulette`), and basic Coinflips (`/gamble`).
* **PvP Duels:** Challenge other users (or the bot itself) to:
  * ✂️ Rock Paper Scissors (`/duel`)
  * 🎲 High Roller Dice (`/dice_duel`)
  * 🔫 Russian Roulette (`/roulette`)
  * ⚡ Quick Draw (`/draw`)
* **Custom Escrow:** Lock in custom wagers with other players where the loser must concede the pot (`/escrow`).

### 💰 Economy & Engagement
* **Aura Currency:** The core server currency.
* **Active Earning:** Earn Aura by chatting, staying in Voice Channels (tracked by the minute), and claiming daily streaks.
* **Daily Wheel:** A visual spinning wheel for daily rewards with a 2% chance for a massive jackpot (`/daily`).
* **Easter Eggs:** Hidden trigger words in chat automatically award users with bounty payouts.
* **Puzzles:** Automatically drops random riddles, math questions, and word scrambles into chat for Aura bounties.

### 🛠️ Server Utilities & Moderation
* **Ticket System Verification:** Automated role assignment and verification workflows (`/verify`, `/notfit`).
* **Auto-Kicker:** Enforces strict time-limits for users to complete onboarding tasks (`/autokick_setup`).
* **Giveaways & Polls:** Robust interactive UI views for hosting server giveaways and community polls.
* **Confession Booth:** 100% anonymous confession system with threaded, anonymous replies.
* **Invite Tracking:** Built-in event system to track valid invites and reward users when the event ends.

---

## 🚀 Setup & Installation

### Prerequisites
* Python 3.9+
* A Discord Bot Token (with Message Content Intent enabled).
* Google Cloud Platform account with Vertex AI enabled.

### 1. Clone the Repository
```bash
git clone [https://github.com/yourusername/baby_no_one.git](https://github.com/yourusername/baby_no_one.git)
cd baby_no_one

```

### 2. Install Dependencies

```bash
pip install discord.py google-genai aiohttp python-dotenv

```

### 3. Environment Variables

Create a `.env` file in the root directory and add your API keys:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GROQ_API_KEY=your_groq_key_here
OPENROUTER_API_KEY=your_openrouter_key_here

```

*(Note: Vertex AI authentication requires your Google Cloud credentials to be configured in your environment, typically via `gcloud auth application-default login` or setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable).*

### 4. Configuration

Before running the bot, open `app.py` (or `bot.py`) and update the **Configuration** section with your specific server's channel IDs:

```python
CHAT_CHANNEL_ID = 1234567890
PAYOUT_CHANNEL_ID = 1234567890
DAILY_ANNOUNCE_CHANNEL_ID = 1234567890
# Update remaining IDs for tickets, logs, and categories...

```

### 5. Run the Bot

```bash
python app.py

```

---

## 💾 Data Storage

Currently, the bot uses a local `data.json` file for lightweight, fast prototyping and state management. The data automatically saves on a background loop to prevent race conditions during high server traffic.

## 🤝 Contributing

Pull requests are welcome! If you're adding new AI interactions or economy features, please ensure they hook into the existing `save_data()` loop to prevent data loss.

## 📄 License

This project is licensed under the MIT License.

```

```
