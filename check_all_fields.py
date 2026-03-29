#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查cards表的所有重要字段
"""

import sqlite3
import os
from datetime import datetime

def check_all_fields(anki_profile='账户 1'):
    """检查cards表的所有字段状态"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查Cards表的所有重要字段")
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

    # 显示cards表的完整结构
    cursor.execute("PRAGMA table_info(cards)")
    columns = cursor.fetchall()
    print("\n=== Cards表结构 ===")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

    # 检查review卡片的完整字段
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT
            n.flds,
            c.type,
            c.queue,
            c.due,
            c.ivl,
            c.factor,
            c.reps,
            c.lapses,
            c.left,
            c.odue,
            c.mod,
            c.usn
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders}) AND c.type = 2
        LIMIT 10
    """, deck_ids)

    print("\n=== Review卡片的完整字段示例（前10张）===")
    for fields, ctype, queue, due, ivl, factor, reps, lapses, left, odue, mod, usn in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        print(f"\n  {word}:")
        print(f"    type: {ctype}, queue: {queue}, due: {due}, ivl: {ivl}")
        print(f"    factor: {factor}, reps: {reps}, lapses: {lapses}")
        print(f"    left: {left}, odue: {odue}")
        print(f"    mod: {mod} ({datetime.fromtimestamp(mod/1000).strftime('%Y-%m-%d %H:%M:%S') if mod else 'None'})")
        print(f"    usn: {usn}")

    # 检查left和odue字段
    cursor.execute(f"""
        SELECT left, odue, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders}) AND type = 2
        GROUP BY left, odue
        ORDER BY count DESC
        LIMIT 10
    """, deck_ids)

    print("\n=== Review卡片的left和odue分布 ===")
    for left, odue, count in cursor.fetchall():
        print(f"  left={left}, odue={odue}: {count} 张")

    # 检查mod字段
    cursor.execute(f"""
        SELECT MIN(mod), MAX(mod)
        FROM cards
        WHERE did IN ({placeholders}) AND type = 2
    """, deck_ids)

    min_mod, max_mod = cursor.fetchone()
    print("\n=== Review卡片的mod时间戳范围 ===")
    if min_mod and max_mod:
        print(f"  最早: {datetime.fromtimestamp(min_mod/1000).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  最晚: {datetime.fromtimestamp(max_mod/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("  无mod数据")

    # 检查usn字段
    cursor.execute(f"""
        SELECT usn, COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders})
        GROUP BY usn
    """, deck_ids)

    print("\n=== 所有卡片的usn分布 ===")
    for usn, count in cursor.fetchall():
        print(f"  usn={usn}: {count} 张")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    check_all_fields()
