#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建墨墨背单词的复习历史并导入到Anki的revlog表
这样FSRS就能使用完整的历史数据
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
        # 历史格式是连续数字，如 "0131123221"
        return [int(x) for x in history_str if x.isdigit()]
    except:
        return []

def parse_intervals(interval_str):
    """解析间隔字符串为列表"""
    if not interval_str or interval_str == '0':
        return []

    try:
        # 间隔格式是逗号分隔，如 "0,11,2,9,3,1,4"
        return [int(x) for x in interval_str.split(',')]
    except:
        return []

def momo_response_to_anki_ease(response, fm=None):
    """
    将墨墨响应映射到Anki评分

    根据分析：
    - 响应0: 初次学习/忘记 → Again (1)
    - 响应1: 记得很好 → Easy (4)
    - 响应2: 中等 → Good (3)
    - 响应3: 困难/忘记 → Hard (2) 或 Again (1)

    参考3月21日后的数据：
    - 响应1 → familiar（记得）
    - 响应3 → forget（忘记）
    """
    if response == 0:
        return 1  # Again - 初次或忘记
    elif response == 1:
        return 4  # Easy - 记得很好
    elif response == 2:
        return 3  # Good - 中等
    elif response == 3:
        return 2  # Hard - 困难
    else:
        return 3  # 默认Good

def reconstruct_review_history(first_study_date, responses, intervals):
    """
    重建复习历史

    返回: [(date, response, interval, last_interval), ...]
    """
    if not responses or not intervals:
        return []

    if len(responses) != len(intervals):
        print(f"Warning: responses length {len(responses)} != intervals length {len(intervals)}")
        # 使用较短的长度
        min_len = min(len(responses), len(intervals))
        responses = responses[:min_len]
        intervals = intervals[:min_len]

    history = []

    # 解析首次学习日期
    try:
        first_date = datetime.strptime(first_study_date[:8], '%Y%m%d')
    except:
        return []

    current_date = first_date
    last_interval = 0

    for i, (response, interval) in enumerate(zip(responses, intervals)):
        history.append({
            'date': current_date,
            'response': response,
            'interval': interval,
            'last_interval': last_interval
        })

        # 计算下次复习日期
        if interval > 0:
            current_date = current_date + timedelta(days=interval)
            last_interval = interval

    return history

def import_review_history(momo_db='momo.v5_5_65.db', anki_profile='账户 1'):
    """导入复习历史到Anki"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("Review History Import Script for FSRS")
    print("=" * 60)

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        try:
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except Exception as e:
            print("\n[ERROR] Anki appears to be still running!")
            print("Please close Anki completely and run this script again.")
            return False

    print(f"\nAnki database: {anki_db}")

    # 备份数据库
    backup_file = anki_db + f'.backup_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"Creating backup: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 从墨墨数据库读取数据
    print("\nLoading review history from Momo database...")
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
        momo_data[spelling] = {
            'first_date': first_date,
            'responses': responses,
            'intervals': intervals,
            'fm_history': fm_history,
            'factor': factor
        }

    momo_conn.close()
    print(f"Loaded {len(momo_data)} words")

    # 连接到Anki数据库
    print("\nConnecting to Anki database...")
    anki_conn = sqlite3.connect(anki_db)
    anki_cursor = anki_conn.cursor()

    # 查找墨墨背单词牌组
    anki_cursor.execute("SELECT id, name FROM decks")
    deck_id = None
    for did, name in anki_cursor.fetchall():
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

    # 查找所有卡片
    anki_cursor.execute(f"""
        SELECT c.id, c.nid, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did = ?
    """, (deck_id,))

    cards = anki_cursor.fetchall()
    print(f"Found {len(cards)} cards in deck")

    # 重建并插入复习历史
    print("\nReconstructing review history...")
    total_reviews = 0
    error_count = 0

    for card_id, note_id, fields_blob in cards:
        try:
            # 解析字段获取单词
            fields = fields_blob.split('\x1f')
            word = fields[0] if len(fields) > 0 else ''

            if word not in momo_data:
                continue

            data = momo_data[word]

            # 解析历史
            responses = parse_history(data['responses'])
            intervals = parse_intervals(data['intervals'])

            if not responses or not intervals:
                continue

            # 重建复习历史
            history = reconstruct_review_history(
                data['first_date'],
                responses,
                intervals
            )

            # 插入到revlog表
            for i, review in enumerate(history):
                # 计算时间戳（毫秒）
                # 为了避免冲突，使用card_id作为基础偏移，并加上复习序号
                # 每个卡片的起始时间戳 = 基础时间 + card_id的偏移
                base_timestamp = int(review['date'].timestamp() * 1000)
                # 使用card_id的低6位作为偏移（最大64秒偏移）
                card_offset = card_id % 100000
                # 每次复习间隔1分钟
                timestamp = base_timestamp + card_offset + (i * 60000)

                # 映射响应到Anki评分
                ease = momo_response_to_anki_ease(review['response'])

                # 计算难度因子
                factor = int(data['factor'] * 2500) if data['factor'] else 2500
                factor = max(1300, min(factor, 5000))

                # 答题时间（随机生成合理值：5-30秒）
                review_time = (5 + (i * 7) % 25) * 1000

                # 卡片类型
                if i == 0:
                    card_type = 0  # new
                elif review['interval'] == 0:
                    card_type = 0  # new
                else:
                    card_type = 2  # review

                # 插入revlog记录
                anki_cursor.execute("""
                    INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,          # id: 时间戳
                    card_id,            # cid: 卡片ID
                    -1,                 # usn: 未同步
                    ease,               # ease: 评分
                    review['interval'], # ivl: 间隔
                    review['last_interval'], # lastIvl: 上次间隔
                    factor,             # factor: 难度因子
                    review_time,        # time: 答题时间（毫秒）
                    card_type           # type: 卡片类型
                ))

                total_reviews += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"Error processing card {card_id}: {e}")

        if total_reviews % 500 == 0:
            print(f"Progress: {total_reviews} reviews inserted...")

    # 提交更改
    anki_conn.commit()
    anki_conn.close()

    print(f"\n{'='*60}")
    print(f"Import completed!")
    print(f"Total reviews inserted: {total_reviews}")
    print(f"Cards processed: {len(cards)}")
    if error_count > 0:
        print(f"Errors: {error_count}")
    print(f"Backup saved to: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\nIMPORTANT: Make sure Anki is completely closed!")
    print("This script will import review history for FSRS.\n")

    success = import_review_history()

    if success:
        print("\n[OK] Review history has been imported!")
        print("FSRS can now use this history data.")
        print("\nNext steps:")
        print("1. Open Anki")
        print("2. Go to deck options and enable FSRS")
        print("3. FSRS will use the imported history for optimization")
    else:
        print("\n[ERROR] Import failed. Please check the error messages above.")
