import http.client, json

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}

# Send metadata as a string
body = json.dumps({"title": "Test", "metadata": "not-a-json"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'metadata as string: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Send metadata as an invalid object
body2 = json.dumps({"title": "Test", "metadata": {"key": set()}}).encode()
# This won't work because set() is not JSON serializable
# Let me try with a circular reference or something that fails JSONField validation

# Send null metadata
body3 = json.dumps({"title": "Test", "metadata": None}).encode()
conn.request('POST', '/api/v1/tickets/', body=body3, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'metadata null: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Send metadata as int
body4 = json.dumps({"title": "Test", "metadata": 42}).encode()
conn.request('POST', '/api/v1/tickets/', body=body4, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'metadata int 42: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Send metadata as array
body5 = json.dumps({"title": "Test", "metadata": [1,2,3]}).encode()
conn.request('POST', '/api/v1/tickets/', body=body5, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'metadata array: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
