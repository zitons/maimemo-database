#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据墨墨的FM值设置FSRS难度
FM值映射：
  FM=1 (最难) → FSRS难度=9.0
  FM=2 → FSRS难度=8.0
  FM=3 → FSRS难度=7.0
  FM=4 → FSRS难度=6.0
  FM=5 → FSRS难度=5.0
  FM=6 → FSRS难度=4.0
  FM=7-9 (最易) → FSRS难度=3.0
"""

import sqlite3
import os
import json
import shutil
from datetime import datetime

def update_fsrs_difficulty(momo_db='momo.v5_5_65.db', anki_profile='账户 1'):
    """根据墨墨FM值更新FSRS难度"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("根据墨墨FM值更新FSRS难度")
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
    backup_file = anki_db + f'.backup_fsrs_difficulty_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 从墨墨读取FM值
    print("\n步骤1：从墨墨数据库读取FM值...")
    momo_conn = sqlite3.connect(momo_db)
    momo_cursor = momo_conn.cursor()

    momo_cursor.execute("""
        SELECT v.spelling, l.lsr_fm
        FROM LSR_TB l
        JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
    """)

    fm_map = {}
    for spelling, fm in momo_cursor.fetchall():
        fm_map[spelling.lower()] = fm

    momo_conn.close()
    print(f"读取到 {len(fm_map)} 个单词的FM值")

    # FM到FSRS难度的映射
    def fm_to_difficulty(fm):
        if fm == 1:
            return 9.0
        elif fm == 2:
            return 8.0
        elif fm == 3:
            return 7.0
        elif fm == 4:
            return 6.0
        elif fm == 5:
            return 5.0
        elif fm == 6:
            return 4.0
        elif fm >= 7:
            return 3.0
        else:
            return 7.0  # 默认

    # 连接Anki数据库
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
        return False

    # 查找所有卡片
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT c.id, n.flds, c.data
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    cards = cursor.fetchall()
    print(f"找到 {len(cards)} 张卡片")

    # 统计
    updated_count = 0
    no_fm_count = 0
    no_data_count = 0
    fm_stats = {}

    print("\n步骤2：更新FSRS难度...")

    for card_id, fields, data_str in cards:
        # 提取单词
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()
        else:
            continue

        # 查找FM值
        if word not in fm_map:
            no_fm_count += 1
            continue

        fm = fm_map[word]

        # 计算FSRS难度
        difficulty = fm_to_difficulty(fm)

        # 记录统计
        fm_stats[fm] = fm_stats.get(fm, 0) + 1

        # 更新data字段
        if data_str and data_str != '{}':
            try:
                data = json.loads(data_str)
                data['d'] = difficulty
            except:
                data = {'d': difficulty}
        else:
            data = {'d': difficulty}

        # 计算factor (FSRS公式: factor = d * 100 + 1000)
        factor = int(difficulty * 100 + 1000)

        # 更新数据库
        cursor.execute("""
            UPDATE cards
            SET data = ?, factor = ?
            WHERE id = ?
        """, (json.dumps(data), factor, card_id))

        updated_count += 1

        if updated_count % 100 == 0:
            print(f"进度: {updated_count}/{len(cards)}")

    conn.commit()
    conn.close()

    # 打印统计
    print(f"\n{'='*60}")
    print("更新完成！")
    print(f"成功更新: {updated_count} 张卡片")
    print(f"无FM值: {no_fm_count} 张卡片")
    print(f"{'='*60}")

    print("\nFM值分布:")
    for fm in sorted(fm_stats.keys()):
        count = fm_stats[fm]
        difficulty = fm_to_difficulty(fm)
        print(f"  FM={fm}: {count} 张 → FSRS难度={difficulty}")

    print(f"\n备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将根据墨墨的FM值设置FSRS难度参数。\n")

    success = update_fsrs_difficulty()

    if success:
        print("\n[完成] FSRS难度已更新！")
        print("建议：")
        print("1. 打开Anki")
        print("2. 牌组选项 → FSRS → 重新优化参数")
        print("3. FSRS会基于新的难度参数重新计算")
