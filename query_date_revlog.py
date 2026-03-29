#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询特定日期的Revlog统计
"""

import sqlite3
import os
from datetime import datetime, timedelta

def query_date_revlog(date_str, anki_profile='账户 1'):
    """查询特定日期的revlog统计"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    # 解析日期
    target_date = datetime.strptime(date_str, '%Y-%m-%d')
    start_ts = int(target_date.timestamp() * 1000)
    end_ts = int((target_date + timedelta(days=1)).timestamp() * 1000)

    print("=" * 60)
    print(f"查询 {date_str} 的Revlog统计")
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

    placeholders = ','.join(['?' for _ in deck_ids])

    # 获取该日期的所有revlog记录
    cursor.execute(f"""
        SELECT r.ease, r.type, COUNT(*) as count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        AND r.id >= ? AND r.id < ?
        GROUP BY r.ease, r.type
        ORDER BY r.ease, r.type
    """, deck_ids + [start_ts, end_ts])

    ease_names = {1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy'}
    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}

    print(f"\n=== 按评分和类型统计 ===")
    total = 0
    ease_stats = {1: 0, 2: 0, 3: 0, 4: 0}

    for ease, rtype, count in cursor.fetchall():
        print(f"  {ease_names.get(ease, ease)} + {type_names.get(rtype, rtype)}: {count} 条")
        total += count
        ease_stats[ease] = ease_stats.get(ease, 0) + count

    print(f"\n=== 按评分统计 ===")
    for ease in [1, 2, 3, 4]:
        if ease_stats[ease] > 0:
            print(f"  {ease_names[ease]}: {ease_stats[ease]} 条 ({ease_stats[ease]*100/total:.1f}%)")

    print(f"\n总计: {total} 条复习记录")

    # 显示具体的复习记录示例
    cursor.execute(f"""
        SELECT r.id, n.flds, r.ease, r.type, r.ivl, r.time
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
        AND r.id >= ? AND r.id < ?
        ORDER BY r.id
        LIMIT 20
    """, deck_ids + [start_ts, end_ts])

    print(f"\n=== 前20条记录 ===")
    for rid, fields, ease, rtype, ivl, time in cursor.fetchall():
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        dt = datetime.fromtimestamp(rid / 1000)
        print(f"  {dt.strftime('%H:%M:%S')} {word}: {ease_names.get(ease, ease)}, {type_names.get(rtype, rtype)}, ivl={ivl}天, time={time}ms")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = '2026-03-22'

    query_date_revlog(date_str)
