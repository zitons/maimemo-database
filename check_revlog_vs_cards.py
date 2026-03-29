#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查revlog和cards表的一致性
"""

import sqlite3
import os

def check_revlog_vs_cards(anki_profile='账户 1'):
    """检查revlog记录和cards状态是否一致"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("检查Revlog和Cards表的一致性")
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

    print(f"牌组IDs: {deck_ids}")

    # 1. 有revlog记录的卡片
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT DISTINCT cid
        FROM revlog
        WHERE cid IN (SELECT id FROM cards WHERE did IN ({placeholders}))
    """, deck_ids)

    cards_with_revlog = set(row[0] for row in cursor.fetchall())
    print(f"\n有revlog记录的卡片数: {len(cards_with_revlog)}")

    # 2. 所有卡片
    cursor.execute(f"""
        SELECT id, type, queue, reps, lapses
        FROM cards
        WHERE did IN ({placeholders})
    """, deck_ids)

    all_cards = cursor.fetchall()
    print(f"总卡片数: {len(all_cards)}")

    # 3. 检查有revlog记录但仍是new状态的卡片
    cursor.execute(f"""
        SELECT c.id, n.flds, c.type, c.queue, c.reps, c.lapses, c.ivl, c.factor
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.id IN ({','.join(['?' for _ in cards_with_revlog])})
        AND c.type = 0
        LIMIT 10
    """, list(cards_with_revlog))

    mismatched = cursor.fetchall()
    print(f"\n有revlog记录但仍是new状态的卡片（前10张）:")
    for card_id, fields, ctype, queue, reps, lapses, ivl, factor in mismatched:
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        print(f"  {word}: type={ctype}, queue={queue}, reps={reps}, lapses={lapses}, ivl={ivl}, factor={factor}")

        # 检查这张卡片的revlog
        cursor.execute("""
            SELECT COUNT(*) FROM revlog WHERE cid = ?
        """, (card_id,))
        revlog_count = cursor.fetchone()[0]
        print(f"    revlog记录数: {revlog_count}")

    # 4. 统计有revlog记录的卡片的type分布
    cursor.execute(f"""
        SELECT c.type, COUNT(*)
        FROM cards c
        WHERE c.id IN ({','.join(['?' for _ in cards_with_revlog])})
        GROUP BY c.type
    """, list(cards_with_revlog))

    print("\n有revlog记录的卡片的type分布:")
    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}
    for ctype, count in cursor.fetchall():
        print(f"  {type_names.get(ctype, ctype)}: {count} 张")

    # 5. 检查几条具体的revlog记录
    print("\n检查示例卡片的完整信息:")
    for card_id, fields, ctype, queue, reps, lapses, ivl, factor in mismatched[:3]:
        word = fields.split('\x1f')[3].strip() if len(fields.split('\x1f')) > 3 else 'Unknown'
        print(f"\n  单词: {word} (ID: {card_id})")
        print(f"    Cards表: type={type_names.get(ctype, ctype)}, queue={queue}, reps={reps}, lapses={lapses}")
        print(f"    Revlog记录:")

        cursor.execute("""
            SELECT id, ease, ivl, lastIvl, factor, type
            FROM revlog
            WHERE cid = ?
            ORDER BY id
        """, (card_id,))

        for i, (rid, ease, rivl, lastIvl, rfact, rtype) in enumerate(cursor.fetchall(), 1):
            from datetime import datetime
            ts = datetime.fromtimestamp(rid / 1000)
            print(f"      #{i}: {ts.strftime('%Y-%m-%d %H:%M')}, ease={ease}, ivl={rivl}, factor={rfact}, type={type_names.get(rtype, rtype)}")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    check_revlog_vs_cards()
