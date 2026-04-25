import requests
import random
import time

URL = "http://127.0.0.1:8000/telemetry"

while True:
    payload = {
        "cpu_usage": random.randint(10, 100),
        "memory_usage": random.randint(20, 100)
    }

    try:
        r = requests.post(URL, json=payload)
        print("Sent:", payload, "Response:", r.json())
    except Exception as e:
        print("Error:", e)

    time.sleep(1)
