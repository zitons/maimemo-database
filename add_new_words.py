#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加墨墨新单词到2021红宝书牌组
"""

import sqlite3
import os
import json
import time
import shutil
from datetime import datetime

def add_new_words(momo_db='momo.v5_5_65.db', anki_profile='账户 1'):
    """添加墨墨中有但红宝书没有的单词"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("添加墨墨新单词到2021红宝书牌组")
    print("=" * 60)

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        try:
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except:
            print("\n[错误] Anki似乎还在运行！")
            return False

    print(f"\nAnki数据库: {anki_db}")

    # 备份
    backup_file = anki_db + f'.backup_add_words_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 连接数据库
    momo_conn = sqlite3.connect(momo_db)
    momo_cursor = momo_conn.cursor()

    anki_conn = sqlite3.connect(anki_db)
    anki_cursor = anki_conn.cursor()

    # 步骤1：获取墨墨单词
    print("\n步骤1：获取墨墨单词...")
    momo_cursor.execute('''
        SELECT v.id, v.spelling, l.lsr_fm
        FROM VOC_TB v
        INNER JOIN LSR_TB l ON v.id = l.lsr_new_voc_id
        WHERE v.spelling IS NOT NULL AND v.spelling != ''
    ''')

    momo_words = {}
    fm_map = {}
    for voc_id, spelling, fm in momo_cursor.fetchall():
        word = spelling.lower().strip()
        momo_words[word] = voc_id
        fm_map[word] = fm

    print(f"墨墨单词: {len(momo_words)} 个")

    # 步骤2：获取红宝书现有单词
    print("\n步骤2：获取红宝书现有单词...")
    anki_cursor.execute("SELECT id, name FROM decks")
    deck_ids = []
    target_deck_id = None
    for did, name in anki_cursor.fetchall():
        try:
            if '2021' in name and '红宝书' in name:
                deck_ids.append(did)
                if '核心词汇' in name:
                    target_deck_id = did
        except:
            pass

    if not target_deck_id:
        target_deck_id = deck_ids[0] if deck_ids else None

    if not target_deck_id:
        print("[错误] 找不到目标牌组")
        momo_conn.close()
        anki_conn.close()
        return False

    print(f"目标牌组ID: {target_deck_id}")

    placeholders = ','.join(['?' for _ in deck_ids])
    anki_cursor.execute(f'''
        SELECT n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    ''', deck_ids)

    existing_words = set()
    for (fields,) in anki_cursor.fetchall():
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()
            if word:
                existing_words.add(word)

    print(f"红宝书现有单词: {len(existing_words)} 个")

    # 步骤3：找出需要添加的单词
    print("\n步骤3：找出需要添加的单词...")
    new_words = set(momo_words.keys()) - existing_words
    print(f"需要添加: {len(new_words)} 个")

    if len(new_words) == 0:
        print("没有需要添加的单词")
        momo_conn.close()
        anki_conn.close()
        return False

    # 步骤4：获取模板信息
    print("\n步骤4：获取note模板...")
    anki_cursor.execute(f'''
        SELECT n.mid
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
        LIMIT 1
    ''', deck_ids)

    model_id = anki_cursor.fetchone()[0]
    print(f"Model ID: {model_id}")

    # 获取USN
    anki_cursor.execute("SELECT usn FROM col")
    usn = anki_cursor.fetchone()[0]

    # 步骤5：创建notes和cards
    print("\n步骤5：创建notes和cards...")
    created_notes = 0
    created_cards = 0
    current_time = int(time.time() * 1000)

    for word in new_words:
        try:
            # 创建note ID
            note_id = current_time + created_notes
            card_id = current_time + created_notes

            # 创建note fields (不添加释义，只添加单词)
            # 假设字段顺序：音标、词性、释义、单词、例句等
            fields = f"\x1f\x1f\x1f{word}\x1f\x1f"  # 空字段+单词+空字段

            # 创建note
            anki_cursor.execute("""
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note_id,
                "",  # guid
                model_id,
                int(current_time / 1000),
                usn,
                "",
                fields,
                word,  # sfld (sort field)
                0,  # csum
                0,  # flags
                ""
            ))

            # 创建card
            anki_cursor.execute("""
                INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card_id,
                note_id,
                target_deck_id,
                0,  # ord
                int(current_time / 1000),
                usn,
                0,  # type (new)
                0,  # queue (new)
                0,  # due
                0,  # ivl
                0,  # factor
                0,  # reps
                0,  # lapses
                0,  # left
                0,  # odue
                0,  # odid
                0,  # flags
                ""  # data
            ))

            created_notes += 1
            created_cards += 1

            if created_notes % 50 == 0:
                print(f"进度: {created_notes}/{len(new_words)}")

        except Exception as e:
            print(f"错误({word}): {e}")

    anki_conn.commit()

    print(f"\n创建 {created_notes} 个notes")
    print(f"创建 {created_cards} 个cards")

    # 步骤6：导入记忆数据
    print("\n步骤6：准备导入记忆数据...")
    print("提示：需要运行 import_memory_4level.py 来导入记忆数据")
    print("提示：需要运行 update_fsrs_difficulty.py 来设置难度")

    momo_conn.close()
    anki_conn.close()

    print(f"\n{'='*60}")
    print("添加完成！")
    print(f"新增单词: {created_notes} 个")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将添加墨墨中有的但红宝书没有的单词。\n")

    success = add_new_words()

    if success:
        print("\n[完成] 新单词已添加！")
        print("接下来请：")
        print("1. 运行 python import_memory_4level.py 导入记忆数据")
        print("2. 运行 python update_fsrs_difficulty.py 设置难度")
