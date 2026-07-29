import http.client, json

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)
headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Bearer {key}'}

# Send body as CSV-like format (invalid form encoding)
body = b'title,Bug report,description,Login fails on mobile,ticket_type,bug'
conn.request('POST', '/api/v1/tickets/', body=body, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'CSV-like form: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if pq sends just the JSON string as the entire form value?
body2 = b'data={"title":"Bug report","ticket_type":"bug"}'
conn.request('POST', '/api/v1/tickets/', body=body2, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'JSON-in-form: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if pq sends one field per line? (Unlikely but testing)
body3 = b'title=Bug+report%0Adescription=Login+fails+on+mobile%0Aticket_type=bug'
conn.request('POST', '/api/v1/tickets/', body=body3, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Line-separated: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# Send as QueryDict with comma-separated values  
body4 = b'title=Bug+report&description=Login+fails+on+mobile&ticket_type=bug&ticket_type=feature'
conn.request('POST', '/api/v1/tickets/', body=body4, headers=headers)
resp = conn.getresponse()
raw = resp.read()
print(f'Duplicate ticket_type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
