#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从LSR_TB更新Anki的调度参数（due, interval, factor, reps, lapses）
参考update_anki_schedule.py的实现
"""

import sqlite3
from datetime import datetime
import os
import shutil

def parse_response_history(history_str):
    """解析响应历史，返回(总次数, 忘记次数)

    LSR响应值：
    - 0: 初次学习
    - 1: 认识 (familiar)
    - 2: 不确定/模糊 (uncertain) -> 映射为Again，计入lapses
    - 3: 忘记 (forget) -> 映射为Again，计入lapses

    lapses应包括响应值2和3（对应SSR表的uncertain和forget）
    """
    if not history_str or history_str == '0':
        return 0, 0

    try:
        responses = [int(x) for x in history_str if x.isdigit()]
        total = len(responses)
        # 响应2(uncertain)和3(forget)都算作lapse
        # 因为它们都映射为Anki的Again评分
        lapses = sum(1 for r in responses if r in [2, 3])
        return total, lapses
    except:
        return 0, 0

def date_to_anki_days(date_str, collection_creation_ts):
    """将日期转换为Anki的天数格式"""
    if not date_str or date_str == '00000000000000':
        return 0

    try:
        dt = datetime.strptime(date_str[:8], '%Y%m%d')
        note_ts = dt.timestamp()
        # Anki内部使用相对于集合创建时间的天数
        days = int((note_ts - collection_creation_ts) / 86400)
        return days
    except:
        return 0

def get_collection_creation_time(db_path):
    """从Anki数据库获取集合创建时间"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT crt FROM col")
    crt = cursor.fetchone()[0]
    conn.close()
    return crt

def update_schedule_from_lsr(momo_db='momo.v5_5_65.db', anki_profile='账户 1'):
    """从LSR_TB更新调度参数"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("从LSR_TB更新调度参数")
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

    # 备份数据库
    backup_file = anki_db + f'.backup_schedule_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 获取集合创建时间
    collection_crt = get_collection_creation_time(anki_db)
    print(f"Collection创建时间: {datetime.fromtimestamp(collection_crt)}")

    # 从墨墨数据库读取调度数据
    print("\n从LSR_TB读取调度数据...")
    momo_conn = sqlite3.connect(momo_db)
    momo_cursor = momo_conn.cursor()

    query = """
    SELECT
        v.spelling,
        l.lsr_next_study_date,
        l.lsr_last_interval,
        l.lsr_factor,
        l.lsr_response_history_byday,
        l.lsr_fm
    FROM LSR_TB l
    JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
    """

    momo_cursor.execute(query)
    scheduling_data = {}
    for row in momo_cursor.fetchall():
        spelling, next_date, interval, factor, history, fm = row
        reps, lapses = parse_response_history(history)
        scheduling_data[spelling.lower()] = {
            'next_date': next_date,
            'interval': interval if interval else 0,
            'factor': factor if factor else 1.0,
            'fm': fm if fm else 3,
            'reps': reps,
            'lapses': lapses
        }

    momo_conn.close()
    print(f"读取到 {len(scheduling_data)} 个单词的调度数据")

    # 连接到Anki数据库
    print("\n更新Anki数据库...")
    anki_conn = sqlite3.connect(anki_db)
    anki_cursor = anki_conn.cursor()

    # 查找2021红宝书牌组
    anki_cursor.execute("SELECT id, name FROM decks")
    deck_ids = []
    for did, name in anki_cursor.fetchall():
        try:
            if '2021' in name and '红宝书' in name:
                deck_ids.append(did)
                print(f"找到牌组: {name} (ID: {did})")
        except:
            pass

    if not deck_ids:
        print("[错误] 找不到'2021红宝书'牌组")
        anki_conn.close()
        return False

    # 查找所有卡片
    placeholders = ','.join(['?' for _ in deck_ids])
    anki_cursor.execute(f"""
        SELECT c.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    cards = []
    for card_id, fields in anki_cursor.fetchall():
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()
            if word:
                cards.append((card_id, word))

    print(f"找到 {len(cards)} 张卡片")

    # 更新调度参数
    updated_count = 0
    not_matched_count = 0

    for card_id, word in cards:
        if word not in scheduling_data:
            not_matched_count += 1
            continue

        sched = scheduling_data[word]

        # 计算due天数
        due_days = date_to_anki_days(sched['next_date'], collection_crt)

        # 计算难度因子（使用FM值）
        fm = sched['fm']
        if 1 <= fm <= 6:
            anki_factor = int(1300 + (fm - 1) * 240)
        elif fm > 6:
            anki_factor = min(2500 + (fm - 6) * 100, 3000)
        else:
            # 使用LSR的factor作为备选
            anki_factor = int(sched['factor'] * 2500) if sched['factor'] else 2500

        anki_factor = max(1300, min(anki_factor, 5000))

        # 判断卡片类型
        if sched['interval'] == 0:
            # 新卡片
            card_type = 0
            queue = 0
            ivl = 0
        else:
            # 复习卡片
            card_type = 2
            queue = 2
            ivl = sched['interval']

        # 更新卡片
        anki_cursor.execute("""
            UPDATE cards
            SET type = ?,
                queue = ?,
                due = ?,
                ivl = ?,
                factor = ?,
                reps = ?,
                lapses = ?,
                mod = ?
            WHERE id = ?
        """, (
            card_type,
            queue,
            due_days,
            ivl,
            anki_factor,
            sched['reps'],
            sched['lapses'],
            int(datetime.now().timestamp() * 1000),
            card_id
        ))

        updated_count += 1

        if updated_count % 100 == 0:
            print(f"进度: {updated_count}/{len(cards)}")

    # 提交更改
    anki_conn.commit()
    anki_conn.close()

    print(f"\n{'='*60}")
    print(f"更新完成！")
    print(f"匹配单词: {updated_count}")
    print(f"未匹配: {not_matched_count}")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将更新调度参数（due, interval, factor, reps, lapses）。\n")

    success = update_schedule_from_lsr()

    if success:
        print("\n[完成] 调度参数已更新！")
        print("现在可以打开Anki进行复习。")
