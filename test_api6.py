import http.client

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

# Test with Accept: text/html
body = b'{"description": "test"}'
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {key}',
    'Accept': 'text/html',
}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Accept text/html: Status {resp.status}, Body ({len(raw)} bytes): {raw[:200]}')

# Test without Accept header
headers2 = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {key}',
}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers2)
resp = conn.getresponse()
raw = resp.read()
print(f'No Accept: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Test with Accept: */*
headers3 = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {key}',
    'Accept': '*/*',
}
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers3)
resp = conn.getresponse()
raw = resp.read()
print(f'Accept */*: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
