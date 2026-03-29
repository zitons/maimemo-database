#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查Anki revlog中的type字段分布
"""

import sqlite3
import os

def check_revlog_types(anki_profile='账户 1'):
    """检查revlog中type字段的分布"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查Revlog中type字段的分布")
    print("=" * 60)

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找2021红宝书牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_ids = []
    for did, name in cursor.fetchall():
        try:
            if '2021' in name and '红宝书' in name:
                deck_ids.append(did)
                print(f"找到牌组: {name} (ID: {did})")
        except:
            pass

    if not deck_ids:
        print("[错误] 找不到'2021红宝书'牌组")
        conn.close()
        return

    # 获取所有卡片ID
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT c.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    cards = {}
    for card_id, fields in cursor.fetchall():
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()
            if word:
                cards[card_id] = word

    print(f"\n找到 {len(cards)} 张卡片")

    # 统计每张卡片的复习次数和type分布
    card_ids = list(cards.keys())
    placeholders = ','.join(['?' for _ in card_ids])

    cursor.execute(f"""
        SELECT cid, type, COUNT(*) as count
        FROM revlog
        WHERE cid IN ({placeholders})
        GROUP BY cid, type
        ORDER BY cid, type
    """, card_ids)

    # 统计type分布
    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}
    type_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    card_review_counts = {}  # card_id -> review_count

    for cid, rtype, count in cursor.fetchall():
        type_counts[rtype] = type_counts.get(rtype, 0) + count

        if cid not in card_review_counts:
            card_review_counts[cid] = 0
        card_review_counts[cid] += count

    print("\n=== Type字段统计 ===")
    for rtype, count in type_counts.items():
        print(f"  {type_names[rtype]} (type={rtype}): {count} 条")

    # 统计每张卡片的复习次数分布
    review_count_distribution = {}
    for cid, count in card_review_counts.items():
        if count not in review_count_distribution:
            review_count_distribution[count] = 0
        review_count_distribution[count] += 1

    print("\n=== 卡片复习次数分布 ===")
    for count in sorted(review_count_distribution.keys()):
        num_cards = review_count_distribution[count]
        print(f"  复习{count}次: {num_cards} 张卡片")

    # 显示几张示例卡片的详细信息
    print("\n=== 示例卡片详情（前5张有复习记录的卡片）===")
    sample_count = 0
    for cid in card_review_counts.keys():
        if sample_count >= 5:
            break

        word = cards.get(cid, 'Unknown')
        cursor.execute(f"""
            SELECT id, type, ease, ivl, time
            FROM revlog
            WHERE cid = ?
            ORDER BY id
        """, (cid,))

        records = cursor.fetchall()
        if records:
            print(f"\n单词: {word} (卡片ID: {cid})")
            print(f"  复习次数: {len(records)}")
            for i, (rid, rtype, ease, ivl, time) in enumerate(records, 1):
                print(f"    #{i}: type={type_names[rtype]}, ease={ease}, ivl={ivl}天, time={time}ms")

            sample_count += 1

    conn.close()

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)


if __name__ == '__main__':
    check_revlog_types()
