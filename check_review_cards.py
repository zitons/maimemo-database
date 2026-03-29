#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查review状态卡片的详细信息
"""

import sqlite3
import os

def check_review_cards(anki_profile='账户 1'):
    """检查review状态卡片的lapses分布"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查Review状态卡片的详细信息")
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
        except:
            pass

    if not deck_ids:
        print("[错误] 找不到'2021红宝书'牌组")
        conn.close()
        return

    # 1. 查看review状态卡片的lapses分布
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT lapses, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders}) AND type = 2
        GROUP BY lapses
        ORDER BY lapses
    """, deck_ids)

    print("\n=== Review卡片的lapses分布 ===")
    total_review = 0
    for lapses, count in cursor.fetchall():
        print(f"  遗忘{lapses}次: {count} 张")
        total_review += count
    print(f"  总计: {total_review} 张review卡片")

    # 2. 查看reps分布
    cursor.execute(f"""
        SELECT reps, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders}) AND type = 2
        GROUP BY reps
        ORDER BY reps
    """, deck_ids)

    print("\n=== Review卡片的reps分布 ===")
    for reps, count in cursor.fetchall():
        print(f"  复习{reps}次: {count} 张")

    # 3. 显示lapses较高的卡片示例
    cursor.execute(f"""
        SELECT n.flds, c.reps, c.lapses, c.ivl, c.factor
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders}) AND c.type = 2 AND c.lapses > 0
        ORDER BY c.lapses DESC
        LIMIT 20
    """, deck_ids)

    print("\n=== 遗忘次数最多的20张卡片 ===")
    for fields, reps, lapses, ivl, factor in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        print(f"  {word}: reps={reps}, lapses={lapses}, ivl={ivl}天, factor={factor}")

    # 4. 统计type和queue
    cursor.execute(f"""
        SELECT type, queue, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders})
        GROUP BY type, queue
        ORDER BY type, queue
    """, deck_ids)

    print("\n=== 所有卡片的type和queue分布 ===")
    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}
    queue_names = {-3: 'user buried', -2: 'sched buried', -1: 'suspended', 0: 'new', 1: 'learning', 2: 'review', 3: 'in learning', 4: 'preview'}

    for ctype, queue, count in cursor.fetchall():
        print(f"  type={type_names.get(ctype, ctype)}, queue={queue_names.get(queue, queue)}: {count} 张")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    check_review_cards()
