#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查Anki卡片的调度信息"""

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

# 查找墨墨背单词牌组中的卡片
print("Querying cards from Anki...")
query = 'deck:"墨墨背单词" tag:momo_import'
card_ids = invoke('findCards', query=query)
print(f"Found {len(card_ids)} cards")

# 获取卡片信息
if len(card_ids) > 0:
    # 取前10张卡片检查
    sample_ids = card_ids[:10]
    cards_info = invoke('cardsInfo', cards=sample_ids)

    print("\n" + "="*80)
    print("Sample Cards Information:")
    print("="*80)

    for i, card in enumerate(cards_info, 1):
        note_id = card['note']
        card_id = card['cardId']

        # 获取字段
        fields = card.get('fields', {})
        front = fields.get('Front', {}).get('value', 'N/A')

        # 获取调度信息
        interval = card.get('interval', 'N/A')
        factor = card.get('factor', 'N/A')
        reps = card.get('reps', 'N/A')
        lapses = card.get('lapses', 'N/A')
        due = card.get('due', 'N/A')
        card_type = card.get('type', 'N/A')
        queue = card.get('queue', 'N/A')

        print(f"\n[{i}] Word: {front}")
        print(f"    Card ID: {card_id}")
        print(f"    Type: {card_type} (0=new, 1=learning, 2=review)")
        print(f"    Queue: {queue}")
        print(f"    Due: {due}")
        print(f"    Interval: {interval} days")
        print(f"    Factor: {factor}")
        print(f"    Reps: {reps}")
        print(f"    Lapses: {lapses}")

    # 统计卡片状态
    print("\n" + "="*80)
    print("Card Statistics:")
    print("="*80)

    all_cards = invoke('cardsInfo', cards=card_ids[:100])  # 检查前100张

    new_count = sum(1 for c in all_cards if c.get('type') == 0)
    learning_count = sum(1 for c in all_cards if c.get('type') == 1)
    review_count = sum(1 for c in all_cards if c.get('type') == 2)

    print(f"New cards (type=0): {new_count}")
    print(f"Learning cards (type=1): {learning_count}")
    print(f"Review cards (type=2): {review_count}")

    # 检查interval分布
    intervals = [c.get('interval', 0) for c in all_cards]
    zero_interval = sum(1 for i in intervals if i == 0)
    positive_interval = sum(1 for i in intervals if i > 0)

    print(f"\nCards with interval=0: {zero_interval}")
    print(f"Cards with interval>0: {positive_interval}")
