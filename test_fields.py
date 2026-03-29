#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接查看字段原始数据"""

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

# 获取一张卡片
deck_name = "2021 红宝书"
query = f'deck:"{deck_name}"'
card_ids = invoke('findCards', query=query)
cards_info = invoke('cardsInfo', cards=card_ids[:1])

if cards_info:
    card = cards_info[0]
    fields = card.get('fields', {})

    print("字段列表：", list(fields.keys()))
    print()

    for field_name, field_data in fields.items():
        value = field_data.get('value', '')
        # 只显示前50个字符
        display = value[:50] if len(value) > 50 else value
        print(f"{field_name}: '{display}'")
