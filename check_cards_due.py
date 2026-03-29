#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查cards表的due字段（到期日）
"""

import sqlite3
import os
from datetime import datetime

def check_cards_due(anki_profile='账户 1'):
    """检查cards表的due字段"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查Cards表的Due字段")
    print("=" * 60)

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 获取collection创建时间
    cursor.execute("SELECT crt FROM col")
    crt = cursor.fetchone()[0]
    collection_date = datetime.fromtimestamp(crt)
    print(f"\nCollection创建时间: {collection_date}")

    # 计算今天的due天数
    today = datetime.now()
    days_since_creation = int((today.timestamp() - crt) / 86400)
    print(f"今天距离创建: {days_since_creation} 天")

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

    # 1. 检查review卡片的due分布
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT
            CASE
                WHEN due < ? THEN 'overdue'
                WHEN due = ? THEN 'today'
                WHEN due > ? THEN 'future'
                ELSE 'unknown'
            END as due_status,
            COUNT(*) as count
        FROM cards
        WHERE did IN ({placeholders}) AND type = 2
        GROUP BY due_status
    """, [days_since_creation, days_since_creation, days_since_creation] + deck_ids)

    print("\n=== Review卡片的due状态 ===")
    for due_status, count in cursor.fetchall():
        print(f"  {due_status}: {count} 张")

    # 2. 显示overdue卡片的due范围
    cursor.execute(f"""
        SELECT MIN(due), MAX(due), AVG(due)
        FROM cards
        WHERE did IN ({placeholders}) AND type = 2
    """, deck_ids)

    min_due, max_due, avg_due = cursor.fetchone()

    print(f"\n=== Review卡片的due范围 ===")
    print(f"  最小due: {min_due} ({collection_date + __import__('datetime').timedelta(days=min_due)})")
    print(f"  最大due: {max_due} ({collection_date + __import__('datetime').timedelta(days=max_due)})")
    print(f"  平均due: {avg_due:.1f}")

    # 3. 显示几条具体的review卡片
    cursor.execute(f"""
        SELECT n.flds, c.type, c.queue, c.due, c.ivl, c.reps, c.lapses
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders}) AND c.type = 2
        ORDER BY c.due
        LIMIT 10
    """, deck_ids)

    print("\n=== Due最早的10张review卡片 ===")
    from datetime import timedelta
    for fields, ctype, queue, due, ivl, reps, lapses in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        due_date = collection_date + timedelta(days=due)
        overdue_days = days_since_creation - due
        print(f"  {word}: due={due} ({due_date.strftime('%Y-%m-%d')}, {overdue_days}天前到期), ivl={ivl}天, reps={reps}, lapses={lapses}")

    # 4. 显示最新的10张review卡片
    cursor.execute(f"""
        SELECT n.flds, c.type, c.queue, c.due, c.ivl, c.reps, c.lapses
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders}) AND c.type = 2
        ORDER BY c.due DESC
        LIMIT 10
    """, deck_ids)

    print("\n=== Due最晚的10张review卡片 ===")
    for fields, ctype, queue, due, ivl, reps, lapses in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        due_date = collection_date + timedelta(days=due)
        future_days = due - days_since_creation
        print(f"  {word}: due={due} ({due_date.strftime('%Y-%m-%d')}, {future_days}天后到期), ivl={ivl}天, reps={reps}, lapses={lapses}")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    check_cards_due()
