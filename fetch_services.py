import requests

url = "https://upvotemax.com/api/public/v1/services"
headers = {
    "x-api-key": "2601ca3e3caecadb1ee6919a71cd6c52",
    "Content-Type": "application/json"
}

r = requests.get(url, headers=headers)
print("Status Code:", r.status_code)
try:
    print(r.json())
except:
    print(r.text)
