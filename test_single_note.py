#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试创建单个笔记"""

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

# 测试1：创建牌组
deck_name = 'MomoTest'
try:
    result = invoke('createDeck', deck=deck_name)
    print(f"Deck created: {result}")
except Exception as e:
    print(f"Deck error: {e}")

# 测试2：创建简单笔记
try:
    note = {
        'deckName': deck_name,
        'modelName': 'Basic',
        'fields': {
            '正面': 'test',
            '背面': 'test back'
        },
        'options': {
            'allowDuplicate': False
        },
        'tags': ['test']
    }
    result = invoke('addNote', note=note)
    print(f"Note created: {result}")
except Exception as e:
    print(f"Note error: {e}")

# 测试3：带音标的笔记
try:
    note = {
        'deckName': deck_name,
        'modelName': 'Basic',
        'fields': {
            '正面': 'prospect',
            '背面': '[ˈprɑːspekt]'
        },
        'options': {
            'allowDuplicate': False
        },
        'tags': ['test']
    }
    result = invoke('addNote', note=note)
    print(f"Note with phonetic created: {result}")
except Exception as e:
    print(f"Note with phonetic error: {e}")
