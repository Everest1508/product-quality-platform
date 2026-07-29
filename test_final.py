import http.client, json

key = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
conn = http.client.HTTPConnection('localhost', 8000)
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}

# Try to reproduce EXACTLY 45 bytes
# The likely scenario is a field that is "required" and has a field name whose length
# makes the total 45 bytes: field_name + message + 9 = 45
# So field_name + message = 36
# If message is "This field is required." (25), field_name must be 11
# Fields with length 11: description, ticket_type, external_id

# But none of these are required! Unless there's a bug.

# What if pq sends the data in a way that the serializer treats ALL fields as required?
# This could happen if pq sends a list of field names, or some unusual format.

# Let me try sending data with extra empty keys
body = b'title=Bug+report&description=Login+fails+on+mobile&ticket_type=bug&'
conn2 = http.client.HTTPConnection('localhost', 8000)
conn2.request('POST', '/api/v1/tickets/', body=body, 
    headers={'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Bearer {key}'})
resp = conn2.getresponse()
raw = resp.read()
print(f'Form trailing &: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if the request body is truly empty (not even JSON)?
conn3 = http.client.HTTPConnection('localhost', 8000)
conn3.request('POST', '/api/v1/tickets/', body=b'', 
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
resp = conn3.getresponse()
raw = resp.read()
print(f'Empty body with JSON Content-Type: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

# What if the Content-Length is wrong? Send a body that's different from Content-Length
conn4 = http.client.HTTPConnection('localhost', 8000)
# This sends 5 bytes but says Content-Length is 100
conn4.request('POST', '/api/v1/tickets/', body=b'[]', 
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}', 'Content-Length': '100'})
resp = conn4.getresponse()
raw = resp.read()
print(f'Wrong content length: Status {resp.status}, Body ({len(raw)} bytes): {raw}')

conn.close()
