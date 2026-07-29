import http.client, json

# Let me try to get a 45-byte response from the server
# by sending requests with various bodies

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

# Try sending just {"description": "Login fails on mobile"} without title
body = json.dumps({"description": "Login fails on mobile", "ticket_type": "bug"}).encode()
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Test A: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Try sending title + description but no ticket_type
# (should use default and succeed)
body2 = json.dumps({"title": "Bug report", "description": "Login fails on mobile"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body2, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Test B: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if the description is sent as a very long string?
body3 = json.dumps({"title": "Bug report", "description": "Login fails on mobile -- " * 50, "ticket_type": "bug"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body3, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Test C (long desc): Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if ticket_type is sent as a number?
body4 = json.dumps({"title": "Bug report", "description": "Login fails on mobile", "ticket_type": 0}).encode()
conn.request('POST', '/api/v1/tickets/', body=body4, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Test D (int 0): Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if ticket_type is sent as the display value?
body5 = json.dumps({"title": "Bug report", "description": "Login fails on mobile", "ticket_type": "Bug"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body5, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Test E (Bug): Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
