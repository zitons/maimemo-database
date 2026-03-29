#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入墨墨记忆数据到2021红宝书牌组（追加模式）
保留现有进度，只添加墨墨的历史记录
"""

import sqlite3
import json
from datetime import datetime, timedelta
import os
import shutil
from collections import defaultdict

def get_review_history_combined(momo_db='momo.v5_5_65.db'):
    """从SSR表和DSR表获取复习历史"""
    print("从SSR表和DSR表获取复习历史...")

    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # 获取单词ID映射
    cursor.execute("SELECT id, spelling FROM VOC_TB")
    voc_id_to_spelling = {row[0]: row[1].lower() for row in cursor.fetchall()}

    # 步骤1：从SSR表获取每日复习状态（这是响应的唯一来源）
    print("  步骤1：从SSR表获取每日复习状态...")
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
        date = datetime.strptime(date_str[:8], '%Y%m%d')

        def parse_voc_list(voc_list_str, response):
            if voc_list_str and voc_list_str != '[]':
                voc_ids = json.loads(voc_list_str)
                for voc_id in voc_ids:
                    if voc_id not in voc_id_to_spelling:
                        continue
                    spelling = voc_id_to_spelling[voc_id]
                    word_reviews[spelling].append({
                        'date': date,
                        'response': response
                    })

        # SSR表响应映射（中间值，后面会转换为Anki评分）
        parse_voc_list(forget, 3)        # forget -> 响应3
        parse_voc_list(uncertain, 2)     # uncertain -> 响应2
        parse_voc_list(familiar, 1)      # familiar -> 响应1
        parse_voc_list(well_familiar, 1) # well_familiar -> 响应1

    print(f"    找到 {len(word_reviews)} 个单词的复习记录")

    # 步骤2：从DSR表获取精确时间戳和耗时（不使用响应）
    print("  步骤2：从DSR表获取精确时间戳和耗时...")
    cursor.execute("""
        SELECT
            dsr_new_voc_id,
            dsr_record_time,
            dsr_recall_time
        FROM DSR_TB
        WHERE dsr_record_time IS NOT NULL
        AND dsr_record_time != '00000000000000'
        ORDER BY dsr_record_time
    """)

    # 构建单词到时间的映射
    word_times = defaultdict(list)
    for row in cursor.fetchall():
        voc_id, record_time, recall_time = row
        if voc_id not in voc_id_to_spelling:
            continue

        try:
            timestamp = datetime.strptime(record_time[:14], '%Y%m%d%H%M%S')
            spelling = voc_id_to_spelling[voc_id]
            word_times[spelling].append({
                'date': timestamp.date(),
                'timestamp': timestamp,
                'recall_time': recall_time if recall_time else 20000
            })
        except:
            continue

    # 步骤3：从SSR表获取每天的平均耗时
    print("  步骤3：从SSR表获取每天的平均耗时...")
    cursor.execute("""
        SELECT
            ssr_date,
            ssr_today_study_time_ms,
            ssr_count_today_total
        FROM SSR_TB
    """)

    daily_avg_time = {}
    for row in cursor.fetchall():
        date_str, study_time_ms, count = row
        if count and count > 0 and study_time_ms:
            date = datetime.strptime(date_str[:8], '%Y%m%d').date()
            avg_time = study_time_ms / count
            daily_avg_time[date] = avg_time

    print(f"    找到 {len(daily_avg_time)} 天的平均耗时数据")

    conn.close()
    print(f"    找到 {len(word_times)} 个单词的精确时间数据")

    # 步骤4：合并数据并分配时间
    print("  步骤4：合并复习历史和时间数据...")
    for spelling in word_reviews:
        # 为每个日期分配时间偏移
        date_offset = {}

        for review in word_reviews[spelling]:
            review_date = review['date'].date()

            # 优先使用DSR的精确时间
            if spelling in word_times:
                found = False
                for time_data in word_times[spelling]:
                    if time_data['date'] == review_date:
                        review['timestamp'] = time_data['timestamp']
                        review['recall_time'] = time_data['recall_time']
                        found = True
                        break

                if found:
                    continue

            # 没有DSR数据，使用日期+时间偏移
            if review_date not in date_offset:
                date_offset[review_date] = 0

            # 计算时间戳：日期的08:00 + 偏移
            base_hour = 8
            offset_minutes = date_offset[review_date]

            review['timestamp'] = datetime(
                review['date'].year,
                review['date'].month,
                review['date'].day,
                base_hour, 0, 0
            ) + timedelta(minutes=offset_minutes)

            # 使用当天的平均耗时，或默认20秒
            review['recall_time'] = int(daily_avg_time.get(review_date, 20000))

            # 每个单词增加偏移（模拟不同时间复习）
            date_offset[review_date] += 2  # 每次增加2分钟

    # 按时间排序并去重
    for spelling in word_reviews:
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

    total_reviews = sum(len(reviews) for reviews in word_reviews.values())
    print(f"  总复习记录数：{total_reviews} 条")

    return dict(word_reviews)

def import_review_history_append(word_reviews, anki_profile='账户 1'):
    """导入复习历史到Anki的revlog表（追加模式）"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("\n" + "="*60)
    print("导入复习历史到Anki（追加模式，保留现有记录）")
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
    backup_file = anki_db + f'.backup_append_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
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
            word = field_list[3].strip().lower()
            if word:
                cards[word] = card_id

    print(f"找到 {len(cards)} 张卡片")

    # 获取现有revlog记录（不删除！）
    print("\n检查现有revlog记录...")
    card_ids = list(cards.values())
    placeholders = ','.join(['?' for _ in card_ids])

    cursor.execute(f"SELECT COUNT(*) FROM revlog WHERE cid IN ({placeholders})", card_ids)
    existing_count = cursor.fetchone()[0]
    print(f"现有 {existing_count} 条复习记录（将保留）")

    # 获取现有时间戳（用于避免冲突）
    cursor.execute("SELECT DISTINCT id FROM revlog")
    existing_timestamps = set(row[0] for row in cursor.fetchall())
    print(f"剩余 {len(existing_timestamps)} 条其他记录")

    # 导入复习历史（追加模式）
    print("\n追加墨墨复习历史...")
    total_reviews = 0
    error_count = 0
    used_timestamps = set(existing_timestamps)

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

                # 映射响应到Anki评分
                # SSR表：forget=3, uncertain=2, familiar=1, well_familiar=1
                # Anki评分：1=Again, 2=Hard, 3=Good, 4=Easy
                # 用户要求：uncertain和forget都映射为Again，familiar映射为Good
                response = review['response']
                if response == 3:
                    ease = 1  # Again - forget
                elif response == 2:
                    ease = 1  # Again - uncertain
                else:
                    ease = 3  # Good - familiar/well_familiar

                # 计算间隔
                if i == 0:
                    ivl = 0
                    last_ivl = 0
                else:
                    prev_timestamp = int(reviews[i-1]['timestamp'].timestamp() * 1000)
                    ivl = max(0, int((timestamp - prev_timestamp) / (1000 * 86400)))
                    last_ivl = reviews[i-1].get('ivl', 0)

                review['ivl'] = ivl

                # 难度因子（固定值，FSRS会重新计算）
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
                    ease,
                    ivl,
                    last_ivl,
                    factor,
                    review['recall_time'],
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
    print(f"原有记录: {existing_count} 条（已保留）")
    print(f"新增记录: {total_reviews} 条")
    print(f"总记录数: {existing_count + total_reviews} 条")
    print(f"错误: {error_count} 条")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True

def main():
    print("="*60)
    print("导入墨墨记忆数据到2021红宝书（追加模式）")
    print("（保留现有进度，只添加墨墨历史）")
    print("="*60)

    # 获取复习历史
    word_reviews = get_review_history_combined()

    # 导入到Anki
    print("\n开始导入...")
    success = import_review_history_append(word_reviews)

    if success:
        print("\n[完成] 记忆数据已成功追加！")
        print("接下来请运行：python update_cards_after_import.py")
        print("来更新cards表的状态字段。")

if __name__ == '__main__':
    main()
