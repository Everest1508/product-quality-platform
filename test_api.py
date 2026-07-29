import urllib.request, json

KEY = '3e142eab7529d0dc9d83982cf8949953748a71d41638bb552adbad9e1de285d1'
URL = 'http://localhost:8000/api/v1/tickets/'

def test(description, data, content_type='application/json'):
    payload = json.dumps(data).encode()
    req = urllib.request.Request(URL, data=payload, method='POST')
    req.add_header('Content-Type', content_type)
    req.add_header('Authorization', f'Bearer {KEY}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()
        print(f'{description} - Status: {resp.status}, Body length: {len(body)}, Body: {body}')
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'{description} - Status: {e.code}, Body length: {len(body)}, Body: {body}')

# Various test cases
test('title null', {'title': None, 'description': 'x', 'ticket_type': 'bug'})
test('empty body', {})
test('XML content type', {'title': 'Test', 'ticket_type': 'bug'}, 'application/xml')
test('garbage content type', {'title': 'Test'}, 'text/plain')
test('no content-type', {'title': 'Test'}, None)

# Test for no content-type
if True:
    payload = json.dumps({'title': 'Test'}).encode()
    req = urllib.request.Request(URL, data=payload, method='POST')
    req.add_header('Authorization', f'Bearer {KEY}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()
        print(f'no content-type header - Status: {resp.status}, Body length: {len(body)}, Body: {body}')
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'no content-type header - Status: {e.code}, Body length: {len(body)}, Body: {body}')
