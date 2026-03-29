#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查left和mod字段的异常
"""

import sqlite3
import os
from datetime import datetime

def check_issues(anki_profile='账户 1'):
    """检查异常字段"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查异常字段")
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

    # 1. 检查left=1001的卡片
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT n.flds, c.type, c.queue, c.left, c.due, c.ivl, c.reps
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders}) AND c.left = 1001
    """, deck_ids)

    print("\n=== left=1001的卡片（应该全部为0）===")
    for fields, ctype, queue, left, due, ivl, reps in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        print(f"  {word}: type={ctype}, queue={queue}, left={left}, due={due}, ivl={ivl}, reps={reps}")

    # 2. 检查mod时间戳异常的卡片（小于2020年的）
    cursor.execute(f"""
        SELECT n.flds, c.mod, c.type, c.queue
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders}) AND c.mod < 1577836800000
    """, deck_ids)

    print("\n=== mod时间戳异常的卡片（早于2020年）===")
    abnormal_mod_count = 0
    for fields, mod, ctype, queue in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        mod_time = datetime.fromtimestamp(mod/1000).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {word}: mod={mod_time}, type={ctype}, queue={queue}")
        abnormal_mod_count += 1

    if abnormal_mod_count == 0:
        print("  无异常")
    else:
        print(f"  共{abnormal_mod_count}张")

    # 3. 检查new卡片是否有reps或lapses
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM cards
        WHERE did IN ({placeholders}) AND type = 0 AND (reps > 0 OR lapses > 0)
    """, deck_ids)

    new_with_reps = cursor.fetchone()[0]
    print(f"\n=== new卡片中有reps或lapses的 ===")
    print(f"  {new_with_reps} 张")

    # 4. 检查所有卡片的data字段
    cursor.execute(f"""
        SELECT data, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders})
        GROUP BY data
    """, deck_ids)

    print("\n=== data字段分布 ===")
    for data, count in cursor.fetchall():
        print(f"  data='{data}': {count} 张")

    # 5. 检查flags字段
    cursor.execute(f"""
        SELECT flags, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders})
        GROUP BY flags
        ORDER BY flags
    """, deck_ids)

    print("\n=== flags字段分布 ===")
    for flags, count in cursor.fetchall():
        print(f"  flags={flags}: {count} 张")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    check_issues()
