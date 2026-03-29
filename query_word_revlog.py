#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询单词的revlog详细记录
"""

import sqlite3
import os
from datetime import datetime

def query_word_revlog(word, anki_profile='账户 1'):
    """查询单词在revlog表中的所有记录"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print(f"查询单词 '{word}' 的Revlog记录")
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

    # 查找单词对应的卡片
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT c.id, n.flds, c.type, c.queue, c.due, c.ivl, c.factor, c.reps, c.lapses
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    card_id = None
    card_info = None
    for cid, fields, ctype, queue, due, ivl, factor, reps, lapses in cursor.fetchall():
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word_in_card = field_list[3].strip().lower()
            if word_in_card == word.lower():
                card_id = cid
                card_info = {
                    'type': ctype,
                    'queue': queue,
                    'due': due,
                    'ivl': ivl,
                    'factor': factor,
                    'reps': reps,
                    'lapses': lapses
                }
                break

    if not card_id:
        print(f"\n[错误] 找不到单词 '{word}'")
        conn.close()
        return

    print(f"\n找到卡片ID: {card_id}")

    # 显示卡片当前状态
    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}
    queue_names = {-3: 'user buried', -2: 'sched buried', -1: 'suspended', 0: 'new', 1: 'learning', 2: 'review', 3: 'in learning', 4: 'preview'}

    print(f"\n=== 卡片当前状态 ===")
    print(f"  type: {type_names.get(card_info['type'], card_info['type'])}")
    print(f"  queue: {queue_names.get(card_info['queue'], card_info['queue'])}")
    print(f"  due: {card_info['due']}")
    print(f"  ivl: {card_info['ivl']}天")
    print(f"  factor: {card_info['factor']}")
    print(f"  reps: {card_info['reps']}")
    print(f"  lapses: {card_info['lapses']}")

    # 查询revlog记录
    cursor.execute("""
        SELECT id, ease, ivl, lastIvl, factor, time, type
        FROM revlog
        WHERE cid = ?
        ORDER BY id ASC
    """, (card_id,))

    revlogs = cursor.fetchall()

    if not revlogs:
        print(f"\n没有找到revlog记录")
        conn.close()
        return

    print(f"\n=== Revlog历史记录 (共{len(revlogs)}条) ===")

    # 获取collection创建时间
    cursor.execute("SELECT crt FROM col")
    crt = cursor.fetchone()[0]

    ease_names = {1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy'}
    type_names_revlog = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}

    for i, (rid, ease, ivl, lastIvl, factor, time, rtype) in enumerate(revlogs, 1):
        # 时间戳转换
        timestamp = rid / 1000  # 毫秒转秒
        dt = datetime.fromtimestamp(timestamp)

        # 计算due日期
        due_days = int((timestamp - crt) / 86400) + ivl
        due_date = datetime.fromtimestamp(crt + due_days * 86400)

        print(f"\n  第{i}次复习:")
        print(f"    时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    评分: {ease_names.get(ease, ease)} (ease={ease})")
        print(f"    类型: {type_names_revlog.get(rtype, rtype)}")
        print(f"    间隔: {ivl}天 (上次间隔: {lastIvl}天)")
        print(f"    因子: {factor}")
        print(f"    耗时: {time}ms ({time/1000:.1f}秒)")
        print(f"    预计下次复习: {due_date.strftime('%Y-%m-%d')}")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        word = sys.argv[1]
    else:
        word = 'dim'

    query_word_revlog(word)
