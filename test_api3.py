import http.client, json

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

# Test without Content-Type header
body = b'{"title": "Bug report", "description": "Login fails on mobile", "ticket_type": "bug"}'
headers = {'Authorization': f'Bearer {key}'}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'No Content-Type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Test with malformed JSON
conn.request('POST', '/api/v1/tickets/', body=b'{"title": "Bug report",}', headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
resp = conn.getresponse()
raw = resp.read()
print(f'Malformed JSON: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Test with array instead of object
conn.request('POST', '/api/v1/tickets/', body=b'["title", "desc"]', headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
resp = conn.getresponse()
raw = resp.read()
print(f'Array body: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Test with string body
conn.request('POST', '/api/v1/tickets/', body=b'"hello"', headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
resp = conn.getresponse()
raw = resp.read()
print(f'String body: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Test with integer body
conn.request('POST', '/api/v1/tickets/', body=b'42', headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
resp = conn.getresponse()
raw = resp.read()
print(f'Int body: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if pq sends the ticket_type value as the CHOICE LABEL instead of the value?
body = json.dumps({"title": "Bug report", "description": "Login fails", "ticket_type": "Bug"}).encode()
conn.request('POST', '/api/v1/tickets/', body=body, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
resp = conn.getresponse()
raw = resp.read()
print(f'Label Bug: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
