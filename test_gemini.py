import asyncio
import os
import json
import datetime
import re
from google import genai
from google.genai import types

async def main():
    vertex_client = genai.Client(vertexai=True, project="gemini-coder-dev", location="us-central1")
    now_dt = datetime.datetime.now()
    message = "ping me at 4pm to post"
    prompt = f"""
    You are a reminder extraction bot. The user wants to set a reminder.
    Current time: {now_dt.strftime('%Y-%m-%d %I:%M %p')} IST
    User message: "{message}"

    Extract the reminder and return ONLY a JSON object (no markdown, no backticks, no other text) with two keys:
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
                temperature=0.1
            )
        )
        print("RAW RESPONSE:")
        print(repr(response.text))
        
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            text_resp = match.group(0)
        else:
            text_resp = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            
        data = json.loads(text_resp)
        print("JSON PARSED:")
        print(data)
    except Exception as e:
        print("EXCEPTION:", e)

asyncio.run(main())
