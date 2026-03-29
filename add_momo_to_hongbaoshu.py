#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的导入流程：
1. 为2021红宝书添加墨墨释义
2. 导入记忆数据（uncertain → Again）
"""

import urllib.request
import json
import sqlite3
from datetime import datetime
import os
import shutil

# AnkiConnect API
def invoke(action, **params):
    url = 'http://localhost:8765'
    payload = {'action': action, 'version': 6, 'params': params}
    req = urllib.request.Request(url, json.dumps(payload).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    response = urllib.request.urlopen(req, timeout=30)
    result = json.loads(response.read().decode('utf-8'))
    if result.get('error') is not None:
        raise Exception(f"Error: {result['error']}")
    return result.get('result')

# 从墨墨数据库获取数据
def get_momo_data(momo_db='momo.v5_5_65.db'):
    print("从墨墨数据库获取数据...")
    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # 获取单词和释义
    cursor.execute("""
        SELECT
            LOWER(v.spelling) as spelling,
            v.phonetic_us,
            i.content
        FROM LSR_TB l
        JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
        LEFT JOIN INA_TB i ON v.id = i.voc_id
    """)

    momo_data = {}
    for row in cursor.fetchall():
        spelling, phonetic, content = row
        if spelling not in momo_data:
            momo_data[spelling] = {
                'phonetic': phonetic,
                'definitions': []
            }

        if content:
            try:
                def_data = json.loads(content)
                if 'content' in def_data:
                    momo_data[spelling]['definitions'].append(def_data['content'])
            except:
                pass

    conn.close()
    print(f"获取到 {len(momo_data)} 个单词的数据")
    return momo_data

# 主函数：添加释义
def add_momo_definitions(momo_data):
    print("\n获取2021红宝书牌组卡片...")
    deck_name = "2021 红宝书"

    # 分批获取卡片（AnkiConnect限制每批1000个）
    all_card_ids = invoke('findCards', query=f'deck:"{deck_name}"')
    total_cards = len(all_card_ids)
    print(f"找到 {total_cards} 张卡片")

    matched_count = 0
    updated_count = 0
    batch_size = 1000

    for i in range(0, total_cards, batch_size):
        batch_ids = all_card_ids[i:i+batch_size]
        cards_info = invoke('cardsInfo', cards=batch_ids)

        for card in cards_info:
            try:
                fields = card.get('fields', {})
                note_id = card['note']

                # 获取单词（字段名是"查询单词"）
                word = None
                for field_name in ['查询单词', '查询词', '提示词', '单词', 'Word']:
                    if field_name in fields:
                        word = fields[field_name].get('value', '').strip().lower()
                        if word:
                            break

                if not word or word not in momo_data:
                    continue

                matched_count += 1
                data = momo_data[word]

                # 构建释义
                if data['definitions']:
                    def_text = '\n'.join([f'{i+1}. {d}' for i, d in enumerate(data['definitions'][:3])])
                else:
                    def_text = '[无释义]'

                # 添加音标
                if data['phonetic']:
                    def_text += f"\n[{data['phonetic']}]"

                # 获取当前笔记内容
                note_field = fields.get('笔记', {})
                original_note = note_field.get('value', '')

                # 添加墨墨释义到笔记字段
                new_note = f"{original_note}\n\n【墨墨释义】\n{def_text}" if original_note else f"【墨墨释义】\n{def_text}"

                # 更新卡片
                invoke('updateNoteFields', note={
                    'id': note_id,
                    'fields': {
                        '笔记': new_note
                    }
                })

                updated_count += 1

                if updated_count % 50 == 0:
                    print(f"进度: {updated_count}/{matched_count}")

            except Exception as e:
                if updated_count == 0 or updated_count % 100 == 0:
                    print(f"处理卡片时出错: {e}")

        print(f"批次 {i//batch_size + 1}/{(total_cards + batch_size - 1)//batch_size} 完成")

    print(f"\n{'='*60}")
    print(f"释义添加完成！")
    print(f"匹配单词: {matched_count}/{total_cards}")
    print(f"更新释义: {updated_count}")
    print(f"{'='*60}")

    return matched_count

if __name__ == '__main__':
    print("="*60)
    print("Step 1: 为2021红宝书添加墨墨释义")
    print("="*60)

    # 获取墨墨数据
    momo_data = get_momo_data()

    # 添加释义
    matched = add_momo_definitions(momo_data)

    print("\n下一步：关闭Anki后运行导入记忆数据的脚本")
