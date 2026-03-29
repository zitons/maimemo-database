#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试不同的模型"""

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

# 获取所有模型
models = invoke('modelNames')
print("All models:")
for m in models:
    print(f"  - {m}")

# 获取几个模型的字段
test_models = ['Basic', 'Basic-b4178', 'BasicCamCard']
for model_name in test_models:
    if model_name in models:
        try:
            fields = invoke('modelFieldNames', modelName=model_name)
            print(f"\n{model_name} fields:")
            for f in fields:
                print(f"  - {f}")
        except Exception as e:
            print(f"\n{model_name} error: {e}")

# 尝试使用Basic-b4178
deck_name = 'MomoTest'
if 'Basic-b4178' in models:
    try:
        fields = invoke('modelFieldNames', modelName='Basic-b4178')
        print(f"\n\nTrying Basic-b4178 with fields: {fields}")

        note = {
            'deckName': deck_name,
            'modelName': 'Basic-b4178',
            'fields': {
                fields[0]: 'test_word',
                fields[1]: 'test_definition'
            },
            'options': {
                'allowDuplicate': False
            },
            'tags': ['test']
        }
        result = invoke('addNote', note=note)
        print(f"Success! Note created with ID: {result}")
    except Exception as e:
        print(f"Basic-b4178 error: {e}")

# 尝试创建新的笔记类型
print("\n\nCreating custom model...")
model_name = 'MomoCard'
try:
    result = invoke('createModel',
        modelName=model_name,
        inOrderFields=['单词', '音标'],
        css='',
        cardTemplates=[{
            'Name': 'Card 1',
            'Front': '{{单词}}',
            'Back': '{{单词}}<br>{{音标}}'
        }]
    )
    print(f"Model created: {model_name}")
except Exception as e:
    print(f"Model creation error (may already exist): {e}")

# 使用自定义模型创建笔记
try:
    note = {
        'deckName': deck_name,
        'modelName': model_name,
        'fields': {
            '单词': 'prospect',
            '音标': '[ˈprɑːspekt]'
        },
        'options': {
            'allowDuplicate': False
        },
        'tags': ['test']
    }
    result = invoke('addNote', note=note)
    print(f"Success! Note created with MomoCard: {result}")
except Exception as e:
    print(f"MomoCard error: {e}")
