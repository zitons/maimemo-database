#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新Anki数据库中的调度参数
必须在Anki关闭时运行
"""

import sqlite3
import json
from datetime import datetime
import os
import shutil

def parse_response_history(history_str):
    """解析响应历史，返回(总次数, 忘记次数)"""
    if not history_str or history_str == '0':
        return 0, 0

    try:
        # 历史格式是连续数字，如 "0131123221"，不是逗号分隔
        responses = [int(x) for x in history_str if x.isdigit()]
        total = len(responses)
        # 响应3表示忘记
        lapses = sum(1 for r in responses if r == 3)
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
        # Anki内部使用相对于集合创建时间的毫秒数
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


def update_anki_scheduling(momo_db='momo.v5_5_65.db', anki_profile='账户 1'):
    """更新Anki调度参数"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("Anki Scheduling Update Script")
    print("=" * 60)

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        # 检查WAL文件是否还在使用
        try:
            # 尝试删除WAL文件，如果Anki还在运行会失败
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except Exception as e:
            print("\n[ERROR] Anki appears to be still running!")
            print("Please close Anki completely and run this script again.")
            print(f"Error: {e}")
            return False

    print(f"\nAnki database: {anki_db}")

    # 备份数据库
    backup_file = anki_db + f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"Creating backup: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 获取集合创建时间
    collection_crt = get_collection_creation_time(anki_db)
    print(f"Collection creation time: {datetime.fromtimestamp(collection_crt)}")

    # 从墨墨数据库读取调度数据
    print("\nLoading scheduling data from Momo database...")
    momo_conn = sqlite3.connect(momo_db)
    momo_cursor = momo_conn.cursor()

    query = """
    SELECT
        v.spelling,
        l.lsr_next_study_date,
        l.lsr_last_interval,
        l.lsr_factor,
        l.lsr_response_history_byday
    FROM LSR_TB l
    JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
    """

    momo_cursor.execute(query)
    scheduling_data = {}
    for row in momo_cursor.fetchall():
        spelling, next_date, interval, factor, history = row
        reps, lapses = parse_response_history(history)
        scheduling_data[spelling] = {
            'next_date': next_date,
            'interval': interval,
            'factor': factor,
            'reps': reps,
            'lapses': lapses
        }

    momo_conn.close()
    print(f"Loaded {len(scheduling_data)} words")

    # 连接到Anki数据库
    print("\nUpdating Anki database...")
    anki_conn = sqlite3.connect(anki_db)
    anki_cursor = anki_conn.cursor()

    # 查找"墨墨背单词"牌组的ID
    anki_cursor.execute("SELECT id, name FROM decks")
    deck_id = None
    for did, name in anki_cursor.fetchall():
        # 处理可能的编码问题
        try:
            if '墨墨' in name or 'momo' in name.lower() or 'Momo' in name:
                deck_id = did
                print(f"Found deck: {name} (ID: {did})")
                break
        except:
            pass

    if not deck_id:
        print("[ERROR] Cannot find '墨墨背单词' deck")
        anki_conn.close()
        return False

    # 查找该牌组的所有卡片
    anki_cursor.execute(f"""
        SELECT c.id, c.nid, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did = ?
    """, (deck_id,))

    cards = anki_cursor.fetchall()
    print(f"Found {len(cards)} cards in deck")

    updated_count = 0
    error_count = 0

    for card_id, note_id, fields_blob in cards:
        try:
            # 解析笔记字段（字段用\x1f分隔）
            fields = fields_blob.split('\x1f')
            word = fields[0] if len(fields) > 0 else ''

            if word not in scheduling_data:
                continue

            sched = scheduling_data[word]

            # 计算due天数
            due_days = date_to_anki_days(sched['next_date'], collection_crt)

            # 转换难度因子 (墨墨: 0.44-1.0 -> Anki: 1300-2500+)
            anki_factor = int(sched['factor'] * 2500)
            anki_factor = max(1300, min(anki_factor, 5000))

            # 准备更新SQL
            # Anki cards表的type字段: 0=new, 1=learning, 2=review, 3=relearning
            # queue字段: -3=user buried, -2=sched buried, -1=suspended,
            #            0=new, 1=learning, 2=review, 3=in learning
            # due字段: 对于review卡片是天数，对于new卡片是order

            # 判断卡片类型
            if sched['interval'] == 0:
                # 新卡片
                card_type = 0
                queue = 0
                due = due_days  # 新卡片的due是order
                ivl = 0
            else:
                # 复习卡片
                card_type = 2
                queue = 2
                due = due_days
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
                due,
                ivl,
                anki_factor,
                sched['reps'],
                sched['lapses'],
                int(datetime.now().timestamp() * 1000),  # mod时间戳
                card_id
            ))

            updated_count += 1

            if updated_count % 100 == 0:
                print(f"Progress: {updated_count}/{len(cards)}")

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"Error updating card {card_id}: {e}")

    # 提交更改
    anki_conn.commit()
    anki_conn.close()

    print(f"\n{'='*60}")
    print(f"Update completed!")
    print(f"Updated: {updated_count}/{len(cards)} cards")
    if error_count > 0:
        print(f"Errors: {error_count}")
    print(f"Backup saved to: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\nIMPORTANT: Make sure Anki is completely closed!")
    print("Starting update process...\n")

    success = update_anki_scheduling()

    if success:
        print("\n[OK] Scheduling data has been updated!")
        print("You can now open Anki and review your cards.")
    else:
        print("\n[ERROR] Update failed. Please check the error messages above.")
