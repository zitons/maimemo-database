#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查Anki模型"""

import urllib.request
import json

def invoke(action, **params):
    url = 'http://localhost:8765'
    payload = {
        'action': action,
        'version': 6,
        'params': params
    }
    req = urllib.request.Request(url, json.dumps(payload).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    response = urllib.request.urlopen(req, timeout=30)
    result = json.loads(response.read().decode('utf-8'))
    if result.get('error') is not None:
        raise Exception(f"Error: {result['error']}")
    return result.get('result')

# 获取模型列表
models = invoke('modelNames')
print("Available models:", models)

# 获取Basic模型的字段
if 'Basic' in models:
    fields = invoke('modelFieldNames', modelName='Basic')
    print("\nBasic model fields:", fields)
