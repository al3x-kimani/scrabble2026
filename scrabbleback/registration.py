import json
import urllib.request
import urllib.error

url = "http://127.0.0.1:5000/api/players"

player = {
    "full_name": "Test Player",
    "email": "testplayer@example.com",
    "level": "Intermediate"
}

data = json.dumps(player).encode("utf-8")

request = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POSpy -3.9 app.pyT"
)

try:
    with urllib.request.urlopen(request) as response:
        print("Status:", response.status)
        print(response.read().decode("utf-8"))

except urllib.error.HTTPError as error:
    print("Status:", error.code)
    print(error.read().decode("utf-8"))