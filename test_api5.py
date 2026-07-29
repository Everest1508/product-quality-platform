import http.client

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

# Test with multipart/form-data
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="title"\r\n\r\n'
    f'Bug report\r\n'
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="description"\r\n\r\n'
    f'Login fails on mobile\r\n'
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="ticket_type"\r\n\r\n'
    f'bug\r\n'
    f'--{boundary}--\r\n'
)
headers = {
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'Authorization': f'Bearer {key}',
}
conn.request('POST', '/api/v1/tickets/', body=body.encode(), headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Multipart: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Test with field name mismatch - e.g., "type" instead of "ticket_type"
import json
body2 = json.dumps({"title": "Bug report", "description": "x", "type": "bug"}).encode()
headers2 = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}
conn.request('POST', '/api/v1/tickets/', body=body2, headers=headers2)
resp = conn.getresponse()
raw = resp.read()
print(f'Field name "type": Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if pq sends "category" instead of "ticket_type"?
body3 = json.dumps({"title": "Bug report", "description": "x", "category": "bug"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body3, headers=headers2)
resp = conn.getresponse()
raw = resp.read()
print(f'Field name "category": Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if pq adds an extra field like "status"?
body4 = json.dumps({"title": "Bug report", "description": "x", "ticket_type": "bug", "status": "open"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body4, headers=headers2)
resp = conn.getresponse()
raw = resp.read()
print(f'Extra status field: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
