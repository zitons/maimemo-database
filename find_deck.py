#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找Anki中的牌组"""

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

# 获取所有牌组
decks = invoke('deckNames')
print("Anki中的所有牌组：")
print("="*60)
for i, deck in enumerate(decks, 1):
    print(f"{i}. {deck}")
