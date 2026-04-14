import urllib.request
import json

data = {
    "name": "Test Python",
    "description": "Desc",
    "shotgun_date": "2026-05-01T20:00",
    "total_spots": 40
}
req = urllib.request.Request('http://localhost:8000/api/admin/events', data=json.dumps(data).encode('utf-8'))
req.add_header('Content-Type', 'application/json')
try:
    response = urllib.request.urlopen(req)
    print("Code:", response.getcode())
    print("Body:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode('utf-8'))
