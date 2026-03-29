#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入墨墨记忆数据到2021红宝书牌组
- uncertain (模糊) → Again (重做)
- forget (忘记) → Again
- familiar (熟悉) → Good
- well_familiar (非常熟悉) → Easy
"""

import sqlite3
import json
from datetime import datetime
import os
import shutil
from collections import defaultdict

def get_review_history_combined(momo_db='momo.v5_5_65.db'):
    """结合SSR表和DSR表获取完整的复习历史"""
    print("从SSR表和DSR表获取复习历史...")

    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # 获取单词ID映射
    cursor.execute("SELECT id, spelling FROM VOC_TB")
    voc_id_to_spelling = {row[0]: row[1].lower() for row in cursor.fetchall()}

    # 步骤1：从DSR表获取精确时间
    print("  步骤1：从DSR表获取精确时间...")
    cursor.execute("""
        SELECT
            dsr_new_voc_id,
            dsr_record_time,
            dsr_last_response,
            dsr_recall_time
        FROM DSR_TB
        WHERE dsr_record_time IS NOT NULL
        AND dsr_record_time != '00000000000000'
        ORDER BY dsr_record_time
    """)

    dsr_records = {}  # {voc_id: {date: [records]}}
    for row in cursor.fetchall():
        voc_id, record_time, last_response, recall_time = row
        if voc_id not in voc_id_to_spelling:
            continue

        try:
            timestamp = datetime.strptime(record_time[:14], '%Y%m%d%H%M%S')
            date = timestamp.date()

            if voc_id not in dsr_records:
                dsr_records[voc_id] = {}
            if date not in dsr_records[voc_id]:
                dsr_records[voc_id][date] = []

            # 映射响应
            # 墨墨DSR表：0=初次/忘记, 1=记得很好, 2=中等, 3=困难
            # Anki：1=Again, 2=Hard, 3=Good, 4=Easy
            if last_response == 0:
                ease = 1  # Again - 初次/忘记
            elif last_response == 1:
                ease = 4  # Easy - 记得很好
            elif last_response == 2:
                ease = 3  # Good - 中等
            elif last_response == 3:
                ease = 2  # Hard - 困难
            else:
                ease = 3  # 默认Good

            dsr_records[voc_id][date].append({
                'timestamp': timestamp,
                'response': ease,
                'recall_time': recall_time if recall_time else 20000
            })
        except:
            continue

    print(f"    DSR表：{len(dsr_records)} 个单词有记录")

    # 步骤2：从SSR表获取每日复习状态
    print("  步骤2：从SSR表获取每日复习状态...")
    cursor.execute("""
        SELECT
            ssr_date,
            ssr_new_vocs_today_well_familiar,
            ssr_new_vocs_today_familiar,
            ssr_new_vocs_today_uncertain,
            ssr_new_vocs_today_forget
        FROM SSR_TB
        ORDER BY ssr_date
    """)

    word_reviews = defaultdict(list)

    for row in cursor.fetchall():
        date_str, well_familiar, familiar, uncertain, forget = row
        date = datetime.strptime(date_str[:8], '%Y%m%d').date()

        def parse_voc_list(voc_list_str, response):
            if voc_list_str and voc_list_str != '[]':
                voc_ids = json.loads(voc_list_str)
                for voc_id in voc_ids:
                    if voc_id not in voc_id_to_spelling:
                        continue

                    spelling = voc_id_to_spelling[voc_id]

                    # 如果DSR表中有这一天的精确时间，使用DSR的数据
                    if voc_id in dsr_records and date in dsr_records[voc_id]:
                        for dsr_rec in dsr_records[voc_id][date]:
                            word_reviews[spelling].append({
                                'timestamp': dsr_rec['timestamp'],
                                'response': dsr_rec['response'],
                                'recall_time': dsr_rec['recall_time']
                            })
                    else:
                        # 否则使用日期的零点时间
                        timestamp = datetime(date.year, date.month, date.day, 12, 0, 0)
                        word_reviews[spelling].append({
                            'timestamp': timestamp,
                            'response': response,
                            'recall_time': 20000
                        })

        # forget → Again (1)
        parse_voc_list(forget, 1)
        # uncertain → Again (1)
        parse_voc_list(uncertain, 1)
        # familiar → Good (3)
        parse_voc_list(familiar, 3)
        # well_familiar → Good (3)
        parse_voc_list(well_familiar, 3)

    conn.close()

    # 按时间排序并去重
    for spelling in word_reviews:
        # 按时间戳排序
        word_reviews[spelling].sort(key=lambda x: x['timestamp'])
        # 去重（相同时间戳只保留第一个）
        seen = set()
        unique_reviews = []
        for review in word_reviews[spelling]:
            ts = review['timestamp']
            if ts not in seen:
                seen.add(ts)
                unique_reviews.append(review)
        word_reviews[spelling] = unique_reviews

    print(f"  总计：{len(word_reviews)} 个单词的复习历史")

    total_reviews = sum(len(reviews) for reviews in word_reviews.values())
    print(f"  总复习记录数：{total_reviews} 条")

    return dict(word_reviews)

def import_review_history_to_anki(word_reviews, anki_profile='账户 1'):
    """导入复习历史到Anki的revlog表"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("\n" + "="*60)
    print("导入复习历史到Anki")
    print("="*60)

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        try:
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except:
            print("\n[错误] Anki似乎还在运行！")
            print("请完全关闭Anki后再运行此脚本。")
            return False

    print(f"\nAnki数据库: {anki_db}")

    # 备份数据库
    backup_file = anki_db + f'.backup_hongbaoshu_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 连接到Anki数据库
    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找2021红宝书牌组及其子牌组
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

    # 查找所有卡片（包括子牌组）
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT c.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    cards = {}
    for card_id, fields in cursor.fetchall():
        # 提取单词（在第4个字段，索引3）
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()  # 第4个字段是单词
            if word:
                cards[word] = card_id

    print(f"找到 {len(cards)} 张卡片")

    # 删除这些卡片的所有现有复习记录
    print("\n删除现有复习记录...")
    card_ids = list(cards.values())
    placeholders = ','.join(['?' for _ in card_ids])

    # 先统计要删除的记录数
    cursor.execute(f"SELECT COUNT(*) FROM revlog WHERE cid IN ({placeholders})", card_ids)
    delete_count = cursor.fetchone()[0]
    print(f"将删除 {delete_count} 条现有复习记录")

    # 删除记录
    cursor.execute(f"DELETE FROM revlog WHERE cid IN ({placeholders})", card_ids)
    conn.commit()
    print(f"已删除 {cursor.rowcount} 条记录")

    # 获取剩余的时间戳（用于避免冲突）
    print("检查剩余revlog记录...")
    cursor.execute("SELECT DISTINCT id FROM revlog")
    existing_timestamps = set(row[0] for row in cursor.fetchall())
    print(f"剩余 {len(existing_timestamps)} 条其他记录")

    # 导入复习历史
    print("\n导入复习历史...")
    total_reviews = 0
    error_count = 0
    used_timestamps = set(existing_timestamps)  # 包含已有时间戳

    for word, reviews in word_reviews.items():
        if word not in cards:
            continue

        card_id = cards[word]

        for i, review in enumerate(reviews):
            try:
                # 使用精确时间戳
                timestamp = int(review['timestamp'].timestamp() * 1000)

                # 确保时间戳唯一
                while timestamp in used_timestamps:
                    timestamp += 1

                used_timestamps.add(timestamp)

                # 计算间隔
                if i == 0:
                    ivl = 0
                    last_ivl = 0
                else:
                    prev_timestamp = int(reviews[i-1]['timestamp'].timestamp() * 1000)
                    ivl = max(0, int((timestamp - prev_timestamp) / (1000 * 86400)))
                    last_ivl = reviews[i-1].get('ivl', 0)

                review['ivl'] = ivl

                # 难度因子
                factor = 2500

                # 卡片类型
                card_type = 0 if i == 0 else 2

                # 插入revlog
                cursor.execute("""
                    INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    card_id,
                    -1,
                    review['response'],
                    ivl,
                    last_ivl,
                    factor,
                    review['recall_time'],  # 使用真实的复习时间
                    card_type
                ))

                total_reviews += 1

            except Exception as e:
                error_count += 1
                if error_count <= 10:
                    print(f"错误: {e}")

        if total_reviews % 1000 == 0:
            print(f"进度: {total_reviews} 条记录...")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"导入完成！")
    print(f"成功导入: {total_reviews} 条复习记录")
    print(f"错误: {error_count} 条")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True

def main():
    print("="*60)
    print("导入墨墨记忆数据到2021红宝书")
    print("结合SSR表和DSR表数据")
    print("="*60)

    # 获取复习历史（结合SSR和DSR）
    word_reviews = get_review_history_combined()

    # 导入到Anki
    print("\n开始导入...")
    success = import_review_history_to_anki(word_reviews)

    if success:
        print("\n[完成] 记忆数据已成功导入！")
        print("现在可以打开Anki，FSRS将使用这些数据。")

if __name__ == '__main__':
    main()
