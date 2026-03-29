#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨数据库INA_TB表提取释义
"""

import json
import sqlite3
import time

MAIMEMO_DB = "momo.v5_5_65.db"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def get_interpretation_from_db(word, cursor):
    """从墨墨数据库INA_TB表获取单词释义"""

    # 查询单词ID
    cursor.execute("SELECT id FROM VOC_TB WHERE spelling = ?", (word,))
    result = cursor.fetchone()

    if not result:
        return None

    voc_id = result[0]

    # 从INA_TB表查询释义
    cursor.execute("""
        SELECT content FROM INA_TB
        WHERE voc_id = ?
        ORDER BY json_extract(content, '$.term_index'), json_extract(content, '$.pos_index')
    """, (voc_id,))

    rows = cursor.fetchall()

    if not rows:
        return None

    # 解析JSON并提取释义
    interpretations = []
    for (content_json,) in rows:
        try:
            data = json.loads(content_json)
            content = data.get('content', '').strip()
            pos = data.get('pos', '').strip()

            if content:
                if pos:
                    interpretations.append(f"{pos} {content}")
                else:
                    interpretations.append(content)
        except:
            continue

    if interpretations:
        return "; ".join(interpretations)

    return None


def fetch_interpretations():
    """从墨墨数据库获取释义"""

    print("=" * 60)
    print("从墨墨数据库INA_TB表提取释义")
    print("=" * 60)

    # 加载单词列表
    if not hasattr(fetch_interpretations, 'words_data'):
        with open(WORDS_FILE, 'r', encoding='utf-8') as f:
            words_data = json.load(f)
        print(f"已加载 {len(words_data)} 个单词")
    else:
        words_data = fetch_interpretations.words_data

    # 加载已有结果
    results = {}
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"已加载 {len(results)} 个已有结果")
    except:
        pass

    # 连接墨墨数据库
    conn = sqlite3.connect(MAIMEMO_DB)
    cursor = conn.cursor()

    # 统计
    success_count = 0
    not_found_count = 0
    already_exists = len(results)

    print(f"\n开始处理...")

    for i, item in enumerate(words_data, 1):
        word = item['word']

        # 跳过已处理的
        if word in results:
            continue

        # 获取释义
        interpretation = get_interpretation_from_db(word, cursor)

        if interpretation:
            results[word] = {
                'word': word,
                'interpretation': interpretation,
                'note_id': item['note_id'],
                'note_field': item['note_field'],
                'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
            }
            success_count += 1

            if success_count % 10 == 0:
                print(f"成功: {success_count} 个")
        else:
            not_found_count += 1

        # 进度显示
        if i % 100 == 0:
            print(f"进度: {i}/{len(words_data)} (成功:{success_count}, 未找到:{not_found_count})")

        # 保存结果（每100个保存一次）
        if i % 100 == 0:
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    # 关闭数据库
    conn.close()

    # 最终保存
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计信息
    total_processed = success_count + not_found_count

    print(f"\n{'='*60}")
    print("完成！")
    print(f"本次处理: {total_processed} 个")
    print(f"成功: {success_count} 个")
    print(f"未找到: {not_found_count} 个")
    print(f"已有结果: {already_exists} 个")
    print(f"总结果: {len(results)} 个")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    fetch_interpretations()
