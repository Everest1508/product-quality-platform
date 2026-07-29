import http.client

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)

# Normal request
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {key}',
}
body = b'{"title": "Bug report", "description": "Login fails on mobile", "ticket_type": "bug"}'
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Normal: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# With trailing newline
body2 = b'{"title": "Bug report", "description": "Login fails on mobile", "ticket_type": "bug"}\n'
conn.request('POST', '/api/v1/tickets/', body=body2, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Trailing newline: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Form-encoded with empty ticket_type
body3 = b'title=Bug+report&description=Login+fails+on+mobile&ticket_type='
form_headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Bearer {key}',
}
conn.request('POST', '/api/v1/tickets/', body=body3, headers=form_headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Form empty type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Form-encoded with missing ticket_type
body4 = b'title=Bug+report&description=Login+fails+on+mobile'
conn.request('POST', '/api/v1/tickets/', body=body4, headers=form_headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Form missing type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Missing title
body5 = b'{"description": "Login fails", "ticket_type": "bug"}'
conn.request('POST', '/api/v1/tickets/', body=body5, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Missing title: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Empty JSON object
body6 = b'{}'
conn.request('POST', '/api/v1/tickets/', body=body6, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Empty JSON: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# title as "Bug report" with different field order
body7 = b'{"ticket_type": "bug", "description": "Login fails on mobile", "title": "Bug report"}'
conn.request('POST', '/api/v1/tickets/', body=body7, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Reordered: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
