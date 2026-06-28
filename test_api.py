import requests
import json

url = "https://upvotemax.com/api/public/v1/orders"

payload_json = {
    "serviceKey": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10
}
r1 = requests.post(url, json=payload_json)
print("JSON format:", r1.status_code, r1.text)

payload_form = {
    "serviceKey": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10
}
r2 = requests.post(url, data=payload_form)
print("FORM format:", r2.status_code, r2.text)

payload_json2 = {
    "serviceId": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10
}
r3 = requests.post(url, json=payload_json2)
print("JSON with serviceId:", r3.status_code, r3.text)

payload_json3 = {
    "service": "post_upvote",
    "link": "https://reddit.com/r/test",
    "quantity": 10
}
r4 = requests.post(url, json=payload_json3)
print("JSON with service:", r4.status_code, r4.text)
