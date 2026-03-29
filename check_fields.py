#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详细检查2021红宝书的卡片字段"""

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

# 获取第一张卡片的详细信息
cards_info = invoke('cardsInfo', cards=card_ids[:1])

if cards_info:
    card = cards_info[0]
    print("字段详情：")
    print(json.dumps(card.get('fields', {}), ensure_ascii=False, indent=2))
