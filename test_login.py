import requests
import json

url = 'http://localhost:5000/api/auth/login'
data = {'username': 'admin', 'password': 'Admin@123'}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
