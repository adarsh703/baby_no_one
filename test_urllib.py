import urllib.request, urllib.parse, json, base64, os

client_id = os.getenv("REDDIT_CLIENT_ID", "v1IoFSfO66C7vg5R99xVuA")
client_secret = os.getenv("REDDIT_CLIENT_SECRET")

auth_str = f"{client_id}:{client_secret}".encode()
b64_auth = base64.b64encode(auth_str).decode()

req = urllib.request.Request("https://www.reddit.com/api/v1/access_token")
req.add_header("Authorization", f"Basic {b64_auth}")
req.add_header("User-Agent", "Mozilla/5.0 (compatible; DiscordBot/1.0)")
data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()

try:
    with urllib.request.urlopen(req, data=data) as resp:
        res = json.loads(resp.read())
        token = res.get("access_token")
        print(f"Token: {token}")
        
        req2 = urllib.request.Request("https://oauth.reddit.com/comments/1txpsg2?limit=50&depth=5")
        req2.add_header("Authorization", f"Bearer {token}")
        req2.add_header("User-Agent", "Mozilla/5.0 (compatible; DiscordBot/1.0)")
        with urllib.request.urlopen(req2) as resp2:
            comments = json.loads(resp2.read())
            # Dump all body texts
            def walk(listing):
                if not isinstance(listing, dict): return
                children = listing.get("data", {}).get("children", [])
                for child in children:
                    body = child.get("data", {}).get("body", "")
                    print("BODY:", body)
                    replies = child.get("data", {}).get("replies", {})
                    walk(replies)
            if isinstance(comments, list) and len(comments) >= 2:
                walk(comments[1])
except Exception as e:
    print(e)
    if hasattr(e, "read"):
        print(e.read().decode())
