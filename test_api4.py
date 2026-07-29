import http.client, json

# Test: does sending request without ticket_type cause "This field is required" error?
key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

body = json.dumps({"title": "Test ticket", "description": "desc"}).encode()
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Missing ticket_type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Also test what happens with ticket_type="" (empty string)
body2 = json.dumps({"title": "Test", "ticket_type": ""}).encode()
conn.request('POST', '/api/v1/tickets/', body=body2, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Empty ticket_type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
