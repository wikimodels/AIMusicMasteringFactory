import sys
print('Step 1', flush=True)
sys.path.insert(0, '.')
print('Step 2', flush=True)
from catalog_similarity_v4 import load_config
print('Step 3', flush=True)
config = load_config()
print('Step 4: config loaded', flush=True)
print('Step 5: importing dashboard...', flush=True)
from dashboard import app
print('Step 6: dashboard imported', flush=True)
client = app.test_client()
print('Step 7: test client created', flush=True)
resp = client.get('/api/paths')
print('Step 8: response', resp.status_code, resp.get_json(), flush=True)