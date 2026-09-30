import urllib.request
import urllib.parse
import json
import time
import sys

# Login via Cognito
url = 'http://ministack:4566'
data = {
    'AuthFlow': 'USER_PASSWORD_AUTH',
    'ClientId': 'toO7EomqBDFzifGDjJlSTjgp7v',
    'AuthParameters': {'USERNAME': 'alice@acme.com', 'PASSWORD': 'Password123!'}
}
headers = {
    'Content-Type': 'application/x-amz-json-1.1',
    'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'
}
req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='POST')
with urllib.request.urlopen(req) as response:
    result = json.loads(response.read().decode())
token = result['AuthenticationResult']['AccessToken']
print('Token:', token[:50] + '...')

auth_header = f'Bearer {token}'

def make_request(url, method='GET', data=None, headers=None):
    req_headers = {'Authorization': auth_header}
    if headers:
        req_headers.update(headers)
    if data:
        req_headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode(), response.read().decode(), response.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers

# Get conversations
code, body, _ = make_request('http://backend:8000/api/conversations/')
print('Conversations:', code)
convs = json.loads(body)
print('Conversations:', len(convs))
conv_id = convs[0]['id']
print('First conv:', conv_id)

# Request export
code, body, _ = make_request(f'http://backend:8000/api/conversations/{conv_id}/export/', method='POST')
print('Export request:', code, body)
export = json.loads(body)
task_id = export['id']
print('Task ID:', task_id)

# Wait for task
for i in range(10):
    time.sleep(1)
    code, body, headers = make_request(f'http://backend:8000/api/exports/{task_id}/download/')
    print(f'Attempt {i+1}: HTTP {code}')
    if code == 200:
        print('SUCCESS: File downloaded!')
        print('Content-Type:', headers.get('Content-Type'))
        print('Content-Disposition:', headers.get('Content-Disposition'))
        print('Content-Length:', headers.get('Content-Length'))
        print('First 200 chars:', body[:200])
        break
    elif code == 302:
        location = headers.get('Location', '')
        print('Redirect to:', location[:80] + '...')
        break
    elif code == 400:
        print('Not ready:', body)
    else:
        print('Error:', code, body)