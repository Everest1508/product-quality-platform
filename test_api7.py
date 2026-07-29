import http.client

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

# Send URL-encoded body with application/json content type (mismatch)
body = b'title=Bug+report&description=Login+fails+on+mobile&ticket_type=bug'
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {key}',
}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'URL-encoded body with JSON Content-Type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Send JSON body with form-encoded content type (reverse mismatch)
import json
body2 = json.dumps({"title": "Bug report", "description": "Login fails on mobile", "ticket_type": "bug"}).encode()
headers2 = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Bearer {key}',
}
conn.request('POST', '/api/v1/tickets/', body=body2, headers=headers2)
resp = conn.getresponse()
raw = resp.read()
print(f'JSON body with form Content-Type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Send form-encoded with ALL fields including missing ticket_type with just empty
body3 = b'title=Bug+report&description=Login+fails+on+mobile&ticket_type='
headers3 = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Bearer {key}',
}
conn.request('POST', '/api/v1/tickets/', body=body3, headers=headers3)
resp = conn.getresponse()
raw = resp.read()
print(f'Form with empty ticket_type=: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if pq sends the data with all fields as strings but with the key "type" instead of "ticket_type"?
# And also doesn't include ALL the required fields?
body4 = b'title=Bug+report&type=bug'
conn.request('POST', '/api/v1/tickets/', body=body4, headers=headers3)
resp = conn.getresponse()
raw = resp.read()
print(f'Form with "type" instead of "ticket_type" and no description: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
