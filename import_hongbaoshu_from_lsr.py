#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从LSR_TB表导入复习历史到2021红宝书牌组
这是正确的方法，LSR_TB包含完整的复习历史
"""

import sqlite3
from datetime import datetime, timedelta
import os
import shutil

def parse_history(history_str):
    """解析历史字符串为列表"""
    if not history_str or history_str == '0':
        return []
    try:
        return [int(x) for x in history_str if x.isdigit()]
    except:
        return []

def parse_intervals(interval_str):
    """解析间隔字符串为列表"""
    if not interval_str or interval_str == '0':
        return []
    try:
        return [int(x) for x in interval_str.split(',')]
    except:
        return []

def parse_fm_history(fm_history_str):
    """解析FM历史字符串为列表"""
    if not fm_history_str or fm_history_str == '0':
        return []
    try:
        return [int(x) for x in fm_history_str.split(',') if x.strip().isdigit()]
    except:
        return []

def momo_response_to_anki_ease_and_type(response):
    """
    将墨墨响应映射到Anki评分和类型
    根据用户要求：

    响应0（初次学习）：
      - ease = 1 (Again)
      - type = 0 (new)

    响应1（记得很好）：
      - ease = 3 (Good)
      - type = 2 (review)

    响应2（中等）：
      - ease = 1 (Again)
      - type = 2 (review)

    响应3（困难/忘记）：
      - ease = 1 (Again)
      - type = 2 (review)
    """
    if response == 0:
        # 初次学习
        return 1, 0  # Again, new
    elif response == 1:
        # 记得很好
        return 3, 2  # Good, review
    elif response == 2:
        # 中等 - 用户要求映射为Again
        return 1, 2  # Again, review
    elif response == 3:
        # 困难/忘记 - 用户要求映射为Again
        return 1, 2  # Again, review
    else:
        # 默认
        return 3, 2  # Good, review

def import_from_lsr(momo_db='momo.v5_5_65.db', anki_profile='账户 1'):
    """从LSR_TB表导入复习历史到Anki"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("从LSR_TB表导入复习历史到2021红宝书")
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
    backup_file = anki_db + f'.backup_lsr_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 从墨墨数据库读取LSR_TB数据
    print("\n从LSR_TB表读取复习历史...")
    momo_conn = sqlite3.connect(momo_db)
    momo_cursor = momo_conn.cursor()

    query = """
    SELECT
        v.spelling,
        l.lsr_first_study_date,
        l.lsr_response_history_byday,
        l.lsr_interval_history_byday,
        l.lsr_fm_history_byday,
        l.lsr_factor
    FROM LSR_TB l
    JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
    """

    momo_cursor.execute(query)
    momo_data = {}
    for row in momo_cursor.fetchall():
        spelling, first_date, responses, intervals, fm_history, factor = row
        momo_data[spelling.lower()] = {
            'first_date': first_date,
            'responses': responses,
            'intervals': intervals,
            'fm_history': fm_history,
            'factor': factor
        }

    momo_conn.close()
    print(f"读取到 {len(momo_data)} 个单词的复习历史")

    # 连接到Anki数据库
    print("\n连接Anki数据库...")
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

    cards = {}
    for card_id, fields in anki_cursor.fetchall():
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()
            if word:
                cards[word] = card_id

    print(f"找到 {len(cards)} 张卡片")

    # 删除现有复习记录
    print("\n删除现有复习记录...")
    card_ids = list(cards.values())
    placeholders = ','.join(['?' for _ in card_ids])
    anki_cursor.execute(f"SELECT COUNT(*) FROM revlog WHERE cid IN ({placeholders})", card_ids)
    delete_count = anki_cursor.fetchone()[0]
    print(f"将删除 {delete_count} 条现有复习记录")

    anki_cursor.execute(f"DELETE FROM revlog WHERE cid IN ({placeholders})", card_ids)
    anki_conn.commit()
    print(f"已删除 {anki_cursor.rowcount} 条记录")

    # 导入复习历史
    print("\n导入复习历史...")
    total_reviews = 0
    error_count = 0
    used_timestamps = set()

    # 获取现有时间戳避免冲突
    anki_cursor.execute("SELECT DISTINCT id FROM revlog")
    existing_timestamps = set(row[0] for row in anki_cursor.fetchall())
    used_timestamps = set(existing_timestamps)

    for word, card_id in cards.items():
        if word not in momo_data:
            continue

        data = momo_data[word]

        # 解析历史
        responses = parse_history(data['responses'])
        intervals = parse_intervals(data['intervals'])
        fm_history = parse_fm_history(data['fm_history'])

        if not responses or not intervals:
            continue

        # 确保长度一致
        min_len = min(len(responses), len(intervals))
        responses = responses[:min_len]
        intervals = intervals[:min_len]

        # 解析首次学习日期
        try:
            first_date = datetime.strptime(data['first_date'][:8], '%Y%m%d')
        except:
            continue

        current_date = first_date
        last_interval = 0

        for i, (response, interval) in enumerate(zip(responses, intervals)):
            try:
                # 计算时间戳（毫秒）
                base_timestamp = int(current_date.timestamp() * 1000)
                # 使用card_id作为偏移避免冲突
                timestamp = base_timestamp + (card_id % 100000) + (i * 60000)

                # 确保时间戳唯一
                while timestamp in used_timestamps:
                    timestamp += 1

                used_timestamps.add(timestamp)

                # 映射响应到Anki评分和类型
                ease, card_type = momo_response_to_anki_ease_and_type(response)

                # 计算难度因子，使用FM历史数据
                # FM值：1-9，表示记忆强度
                # FM越小，说明记忆越弱，难度因子应该越低
                if i < len(fm_history):
                    current_fm = fm_history[i]
                    # FM值转换为难度因子：FM=1 → factor=1300, FM=6 → factor=2500
                    # 线性映射：factor = 1300 + (fm - 1) * (2500 - 1300) / (6 - 1)
                    if current_fm >= 1 and current_fm <= 6:
                        factor = int(1300 + (current_fm - 1) * 240)
                    elif current_fm > 6:
                        # FM>6表示非常熟悉，给更高的因子
                        factor = 2500 + min((current_fm - 6) * 100, 500)
                    else:
                        # FM=0或其他异常值，使用默认值
                        factor = 2500
                else:
                    # 如果没有FM历史，使用LSR表中的factor
                    factor = int(data['factor'] * 2500) if data['factor'] else 2500

                # 确保factor在合理范围内
                factor = max(1300, min(factor, 5000))

                # 答题时间（毫秒）
                review_time = (5 + (i * 7) % 25) * 1000

                # 插入revlog记录
                anki_cursor.execute("""
                    INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    card_id,
                    -1,
                    ease,
                    interval,
                    last_interval,
                    factor,
                    review_time,
                    card_type
                ))

                total_reviews += 1

                # 计算下次复习日期
                if interval > 0:
                    current_date = current_date + timedelta(days=interval)
                    last_interval = interval

            except Exception as e:
                error_count += 1
                if error_count <= 10:
                    print(f"错误: {e}")

        if total_reviews % 500 == 0:
            print(f"进度: {total_reviews} 条复习记录...")

    # 提交更改
    anki_conn.commit()
    anki_conn.close()

    print(f"\n{'='*60}")
    print(f"导入完成！")
    print(f"成功导入: {total_reviews} 条复习记录")
    print(f"错误: {error_count} 条")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将导入LSR_TB表的完整复习历史。\n")

    success = import_from_lsr()

    if success:
        print("\n[完成] 复习历史已成功导入！")
        print("现在需要运行 update_cards_after_import.py 更新卡片状态。")
