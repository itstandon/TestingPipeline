import requests
try:
    r = requests.post('http://localhost:11434/api/generate', json={
        'model': 'gemma3:4b',
        'prompt': 'Hello, identify yourself briefly.',
        'stream': False
    }, timeout=120)
    print("STATUS CODE:", r.status_code)
    print("RESPONSE JSON:", r.json())
except Exception as e:
    print("ERROR:", e)
