#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将墨墨背单词的释义和记忆数据导入到2021红宝书牌组
uncertain (模糊) → Again
"""

import sqlite3
import urllib.request
import json
from datetime import datetime

# AnkiConnect API
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

# 从墨墨数据库获取释义和记忆数据
def get_momo_data(momo_db='momo.v5_5_65.db'):
    print("从墨墨数据库获取释义和记忆数据...")

    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # 获取单词、释义和记忆数据
    query = """
    SELECT
        v.spelling,
        v.phonetic_us,
        i.content,
        l.lsr_first_study_date,
        l.lsr_last_study_date,
        l.lsr_next_study_date,
        l.lsr_last_interval,
        l.lsr_factor,
        l.lsr_fm,
        l.lsr_response_history_byday
    FROM LSR_TB l
    JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
    LEFT JOIN INA_TB i ON v.id = i.voc_id
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    # 构建单词到数据的映射
    momo_data = {}
    for row in results:
        spelling, phonetic, content, first_study, last_study, next_study, interval, factor, fm, response_history = row

        if spelling not in momo_data:
            momo_data[spelling] = {
                'phonetic': phonetic,
                'definitions': [],
                'first_study': first_study,
                'last_study': last_study,
                'next_study': next_study,
                'interval': interval if interval else 0,
                'factor': factor if factor else 1.0,
                'fm': fm,
                'response_history': response_history
            }

        # 添加释义
        if content:
            try:
                def_data = json.loads(content)
                if 'content' in def_data:
                    momo_data[spelling]['definitions'].append(def_data['content'])
            except:
                pass

    print(f"获取到 {len(momo_data)} 个单词的数据")
    return momo_data

# 解析响应历史，计算reps和lapses
def parse_response_history(history_str):
    if not history_str or history_str == '0':
        return 0, 0

    try:
        responses = [int(x) for x in history_str if x.isdigit()]
        total = len(responses)
        # 响应3 = forget, 响应0 = 初次学习也算forget
        lapses = sum(1 for r in responses if r == 3 or r == 0)
        return total, lapses
    except:
        return 0, 0

# 从每日统计获取复习历史
def get_review_history_from_stats(momo_db='momo.v5_5_65.db'):
    print("从每日统计表获取复习历史...")

    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # 获取单词ID映射
    cursor.execute("SELECT id, spelling FROM VOC_TB")
    voc_id_to_spelling = {row[0]: row[1] for row in cursor.fetchall()}

    # 从SSR表获取
    cursor.execute("""
        SELECT
            ssr_date,
            ssr_new_vocs_today_well_familiar,
            ssr_new_vocs_today_familiar,
            ssr_new_vocs_today_uncertain,
            ssr_new_vocs_today_forget
        FROM SSR_TB
        ORDER BY ssr_date
    """)

    word_reviews = {}

    for row in cursor.fetchall():
        date_str, well_familiar, familiar, uncertain, forget = row
        date = datetime.strptime(date_str[:8], '%Y%m%d')

        def parse_voc_list(voc_list_str, response):
            if voc_list_str and voc_list_str != '[]':
                voc_ids = json.loads(voc_list_str)
                for voc_id in voc_ids:
                    if voc_id not in word_reviews:
                        word_reviews[voc_id] = []
                    word_reviews[voc_id].append({
                        'date': date,
                        'response': response
                    })

        # forget → Again (1)
        parse_voc_list(forget, 1)
        # uncertain → Again (1)  # 重要调整！
        parse_voc_list(uncertain, 1)
        # familiar → Good (3)
        parse_voc_list(familiar, 3)
        # well_familiar → Easy (4)
        parse_voc_list(well_familiar, 4)

    conn.close()

    # 转换为单词映射
    word_review_by_spelling = {}
    for voc_id, reviews in word_reviews.items():
        if voc_id in voc_id_to_spelling:
            spelling = voc_id_to_spelling[voc_id]
            word_review_by_spelling[spelling] = reviews

    print(f"获取到 {len(word_review_by_spelling)} 个单词的复习历史")
    return word_review_by_spelling

# 主函数
def main():
    print("="*60)
    print("将墨墨数据导入2021红宝书")
    print("="*60)

    # 获取墨墨数据
    momo_data = get_momo_data()
    review_history = get_review_history_from_stats()

    # 获取2021红宝书牌组中的所有卡片
    print("\n获取2021红宝书牌组的卡片...")
    deck_name = "2021 红宝书"

    # 查找卡片
    query = f'deck:"{deck_name}"'
    card_ids = invoke('findCards', query=query)
    print(f"找到 {len(card_ids)} 张卡片")

    # 获取卡片信息
    cards_info = invoke('cardsInfo', cards=card_ids[:100])  # 先处理前100张

    print(f"\n开始处理前100张卡片...")
    updated_count = 0
    matched_count = 0

    # 打印调试信息（前10个单词）
    print("\n检查前10个单词的匹配情况...")
    for i, card in enumerate(cards_info[:10]):
        fields = card.get('fields', {})
        # 尝试所有可能的字段名（包括"单词"）
        word = None
        for field_name in ['单词', '查询词', '提示词', 'Front', 'Word', 'word', 'front']:
            if field_name in fields:
                word = fields[field_name].get('value', '').strip().lower()
                if word:
                    print(f"{i+1}. 单词: '{word}' -> 匹配: {'是' if word in momo_data else '否'}")
                    break

        if not word:
            print(f"{i+1}. 未找到单词字段，可用字段: {list(fields.keys())}")

    print("\n开始处理所有卡片...")
    matched_words = []  # 记录匹配到的单词

    for card in cards_info:
        note_id = card['note']
        fields = card.get('fields', {})

        # 尝试多个可能的字段名（包括"单词"）
        word = None
        for field_name in ['单词', '查询词', '提示词', 'Front', 'Word', 'word', 'front']:
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
            definition_text = '\n'.join([f'{i+1}. {defi}' for i, defi in enumerate(data['definitions'][:3])])  # 最多3个释义
        else:
            definition_text = '[无释义]'

        # 更新卡片背面
        back_field = fields.get('Back', {})
        original_back = back_field.get('value', '')

        # 添加墨墨释义
        new_back = f"{original_back}\n\n【墨墨释义】\n{definition_text}"
        if data['phonetic']:
            new_back += f"\n音标: [{data['phonetic']}]"

        # 更新笔记
        try:
            invoke('updateNoteFields', note={
                'id': note_id,
                'fields': {
                    'Back': new_back
                }
            })
            updated_count += 1

            if updated_count % 10 == 0:
                print(f"进度: {updated_count}/{matched_count}")

        except Exception as e:
            print(f"更新 {word} 时出错: {e}")

    print(f"\n{'='*60}")
    print(f"处理完成！")
    print(f"匹配单词: {matched_count}/{len(cards_info)}")
    print(f"更新释义: {updated_count}")
    print(f"{'='*60}")

    print("\n接下来需要导入记忆数据到Anki数据库...")
    print("请关闭Anki后运行导入记忆数据的脚本")

if __name__ == '__main__':
    main()
