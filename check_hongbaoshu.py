#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查2021红宝书的卡片结构"""

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

# 获取2021红宝书的卡片
deck_name = "2021 红宝书"
query = f'deck:"{deck_name}"'
card_ids = invoke('findCards', query=query)
print(f"找到 {len(card_ids)} 张卡片")

# 获取前5张卡片的详细信息
cards_info = invoke('cardsInfo', cards=card_ids[:5])

for i, card in enumerate(cards_info, 1):
    print(f"\n{'='*60}")
    print(f"卡片 {i}:")
    print(f"{'='*60}")

    fields = card.get('fields', {})
    for field_name, field_data in fields.items():
        value = field_data.get('value', '')
        # 只显示前100个字符
        display_value = value[:100] if len(value) > 100 else value
        print(f"{field_name}: {display_value}")

    # 获取笔记ID和模型
    note_id = card.get('note')
    print(f"\nNote ID: {note_id}")

# 获取模型信息
if cards_info:
    model_name = cards_info[0].get('modelName')
    print(f"\n{'='*60}")
    print(f"模型名称: {model_name}")
    print(f"{'='*60}")

    # 获取模型的字段定义
    model_fields = invoke('modelFieldNames', modelName=model_name)
    print(f"字段列表: {model_fields}")
