import requests
import json
import os

UPVOTEMAX_API_KEY = os.getenv("UPVOTEMAX_API_KEY")
UPVOTEMAX_URL = "https://upvotemax.com/api/public/v1/orders"

payload = {
    "service": "post_upvote",
    "link": "https://www.reddit.com/r/test/comments/testpost",
    "quantity": 10,
    "speed": 50
}

headers = {
    "x-api-key": UPVOTEMAX_API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "curl/7.68.0"
}

try:
    resp = requests.post(UPVOTEMAX_URL, json=payload, headers=headers)
    print("STATUS:", resp.status_code)
    print("RESPONSE:", resp.text)
except Exception as e:
    print("ERROR:", e)
