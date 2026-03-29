#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查Anki cards表的当前状态
"""

import sqlite3
import os

def check_cards_status(anki_profile='账户 1'):
    """检查cards表中type和queue字段的分布"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查Cards表的当前状态")
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

    # 统计cards表的type分布
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT type, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders})
        GROUP BY type
        ORDER BY type
    """, deck_ids)

    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}
    print("\n=== Cards表的type字段（卡片当前类型）===")
    for rtype, count in cursor.fetchall():
        print(f"  {type_names.get(rtype, f'未知({rtype})')}: {count} 张卡片")

    # 统计cards表的queue分布
    cursor.execute(f"""
        SELECT queue, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders})
        GROUP BY queue
        ORDER BY queue
    """, deck_ids)

    queue_names = {
        -3: 'user buried',
        -2: 'sched buried',
        -1: 'suspended',
        0: 'new',
        1: 'learning',
        2: 'review',
        3: 'in learning',
        4: 'preview'
    }
    print("\n=== Cards表的queue字段（卡片当前队列）===")
    for queue, count in cursor.fetchall():
        print(f"  {queue_names.get(queue, f'未知({queue})')}: {count} 张卡片")

    # 统计reps和lapses
    cursor.execute(f"""
        SELECT
            COUNT(*) as total,
            AVG(reps) as avg_reps,
            AVG(lapses) as avg_lapses,
            MIN(reps) as min_reps,
            MAX(reps) as max_reps
        FROM cards
        WHERE did IN ({placeholders})
    """, deck_ids)

    total, avg_reps, avg_lapses, min_reps, max_reps = cursor.fetchone()
    print("\n=== Cards表的reps和lapses统计 ===")
    print(f"  总卡片数: {total}")
    print(f"  平均复习次数: {avg_reps:.1f}")
    print(f"  平均遗忘次数: {avg_lapses:.1f}")
    print(f"  最小复习次数: {min_reps}")
    print(f"  最大复习次数: {max_reps}")

    # 显示一些示例卡片
    print("\n=== 示例卡片详情（前10张）===")
    cursor.execute(f"""
        SELECT
            n.flds,
            c.type,
            c.queue,
            c.reps,
            c.lapses,
            c.ivl,
            c.factor
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
        LIMIT 10
    """, deck_ids)

    for fields, ctype, queue, reps, lapses, ivl, factor in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        print(f"\n  {word}:")
        print(f"    type: {type_names.get(ctype, ctype)}, queue: {queue_names.get(queue, queue)}")
        print(f"    reps: {reps}, lapses: {lapses}, ivl: {ivl}天, factor: {factor}")

    conn.close()

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)


if __name__ == '__main__':
    check_cards_status()
