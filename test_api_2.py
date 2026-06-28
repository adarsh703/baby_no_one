import requests
import json
import os

url = "https://upvotemax.com/api/public/v1/orders"

headers = {
    "x-api-key": "fake_key_to_bypass_cloudflare_or_get_401",
    "Content-Type": "application/json"
}

payload_json = {
    "serviceKey": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10,
    "speed": 50
}
r1 = requests.post(url, json=payload_json, headers=headers)
print("JSON format with headers:", r1.status_code, r1.text)

payload_json2 = {
    "serviceId": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10,
    "speed": 50
}
r2 = requests.post(url, json=payload_json2, headers=headers)
print("JSON format with serviceId:", r2.status_code, r2.text)

payload_json3 = {
    "service": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10,
    "speed": 50
}
r3 = requests.post(url, json=payload_json3, headers=headers)
print("JSON format with service:", r3.status_code, r3.text)

payload_form = {
    "service": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10,
    "speed": 50
}
headers_form = {
    "x-api-key": "fake_key_to_bypass_cloudflare_or_get_401",
}
r4 = requests.post(url, data=payload_form, headers=headers_form)
print("FORM format:", r4.status_code, r4.text)
