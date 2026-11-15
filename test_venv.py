import os
path = r'D:\GitHub\AIMusicMasteringFactory\Felt Piano Jazz'
print('Testing:', path)
print('Exists:', os.path.exists(path))
try:
    items = os.listdir(path)
    print('Items:', items)
except Exception as e:
    print('ERROR:', type(e).__name__, e)