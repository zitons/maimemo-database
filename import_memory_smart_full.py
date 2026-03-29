#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能合并导入墨墨记忆数据（完整版）
1. 提取非墨墨单词的revlog记录和卡片状态
2. 清空所有revlog记录
3. 插入非墨墨记录 + 墨墨新记录
4. 恢复非墨墨卡片状态 + 更新墨墨卡片状态
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

    cursor.execute("SELECT id, spelling FROM VOC_TB")
    voc_id_to_spelling = {row[0]: row[1].lower() for row in cursor.fetchall()}

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

        parse_voc_list(forget, 3)
        parse_voc_list(uncertain, 2)
        parse_voc_list(familiar, 1)
        parse_voc_list(well_familiar, 1)

    print(f"    找到 {len(word_reviews)} 个单词的复习记录")

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

    print("  步骤4：合并复习历史和时间数据...")
    for spelling in word_reviews:
        date_offset = {}

        for review in word_reviews[spelling]:
            review_date = review['date'].date()

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

            if review_date not in date_offset:
                date_offset[review_date] = 0

            base_hour = 8
            offset_minutes = date_offset[review_date]

            review['timestamp'] = datetime(
                review['date'].year,
                review['date'].month,
                review['date'].day,
                base_hour, 0, 0
            ) + timedelta(minutes=offset_minutes)

            review['recall_time'] = int(daily_avg_time.get(review_date, 20000))
            date_offset[review_date] += 2

    for spelling in word_reviews:
        word_reviews[spelling].sort(key=lambda x: x['timestamp'])
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

def import_review_history_smart_full(word_reviews, anki_profile='账户 1'):
    """智能合并导入（完整版：revlog + cards状态）"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("\n" + "="*60)
    print("智能合并导入（完整版）")
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
            return False

    print(f"\nAnki数据库: {anki_db}")

    backup_file = anki_db + f'.backup_smart_full_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 获取collection创建时间
    cursor.execute("SELECT crt FROM col")
    collection_crt = cursor.fetchone()[0]
    print(f"Collection创建时间: {datetime.fromtimestamp(collection_crt)}")

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
        SELECT c.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    cards = {}
    for card_id, fields in cursor.fetchall():
        field_list = fields.split('\x1f')
        if len(field_list) > 3:
            word = field_list[3].strip().lower()
            if word:
                cards[word] = card_id

    print(f"找到 {len(cards)} 张卡片")

    momo_words = set(word_reviews.keys())
    print(f"墨墨单词数: {len(momo_words)}")

    # 步骤1：提取非墨墨单词的revlog记录和卡片状态
    print("\n步骤1：提取非墨墨单词的数据...")
    card_ids = list(cards.values())
    placeholders_cards = ','.join(['?' for _ in card_ids])

    cursor.execute(f"""
        SELECT r.id, r.cid, r.usn, r.ease, r.ivl, r.lastIvl, r.factor, r.time, r.type
        FROM revlog r
        WHERE r.cid IN ({placeholders_cards})
    """, card_ids)

    all_revlogs = cursor.fetchall()
    print(f"总revlog记录数: {len(all_revlogs)}")

    non_momo_revlogs = []
    momo_revlogs = []
    card_id_to_word = {v: k for k, v in cards.items()}

    for revlog in all_revlogs:
        card_id = revlog[1]
        word = card_id_to_word.get(card_id, '')
        if word not in momo_words:
            non_momo_revlogs.append(revlog)
        else:
            momo_revlogs.append(revlog)

    print(f"非墨墨单词的revlog记录: {len(non_momo_revlogs)} 条（将保留）")
    print(f"墨墨单词的旧revlog记录: {len(momo_revlogs)} 条（将替换）")

    # 提取非墨墨卡片的当前状态
    print("\n提取非墨墨卡片的当前状态...")
    non_momo_card_states = {}
    cursor.execute(f"""
        SELECT c.id, c.type, c.queue, c.due, c.ivl, c.factor, c.reps, c.lapses, c.left, c.odue
        FROM cards c
        WHERE c.id IN ({placeholders_cards})
    """, card_ids)

    for card_id, ctype, queue, due, ivl, factor, reps, lapses, left, odue in cursor.fetchall():
        word = card_id_to_word.get(card_id, '')
        if word not in momo_words:
            non_momo_card_states[card_id] = {
                'type': ctype,
                'queue': queue,
                'due': due,
                'ivl': ivl,
                'factor': factor,
                'reps': reps,
                'lapses': lapses,
                'left': left,
                'odue': odue
            }

    print(f"非墨墨卡片: {len(non_momo_card_states)} 张（状态将保留）")

    # 步骤2：清空所有revlog记录
    print("\n步骤2：清空所有revlog记录...")
    cursor.execute(f"DELETE FROM revlog WHERE cid IN ({placeholders_cards})", card_ids)
    print(f"已删除 {cursor.rowcount} 条记录")

    # 步骤3：插入非墨墨记录
    print("\n步骤3：恢复非墨墨单词的revlog记录...")
    for revlog in non_momo_revlogs:
        cursor.execute("""
            INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, revlog)

    print(f"已恢复 {len(non_momo_revlogs)} 条非墨墨记录")

    # 步骤4：插入墨墨新记录
    print("\n步骤4：插入墨墨新记录...")

    cursor.execute("SELECT DISTINCT id FROM revlog")
    existing_timestamps = set(row[0] for row in cursor.fetchall())
    used_timestamps = set(existing_timestamps)

    total_reviews = 0
    error_count = 0

    for word, reviews in word_reviews.items():
        if word not in cards:
            continue

        card_id = cards[word]

        for i, review in enumerate(reviews):
            try:
                timestamp = int(review['timestamp'].timestamp() * 1000)

                while timestamp in used_timestamps:
                    timestamp += 1

                used_timestamps.add(timestamp)

                response = review['response']
                if response == 3:
                    ease = 1
                elif response == 2:
                    ease = 1
                else:
                    ease = 3

                if i == 0:
                    ivl = 0
                    last_ivl = 0
                else:
                    prev_timestamp = int(reviews[i-1]['timestamp'].timestamp() * 1000)
                    ivl = max(0, int((timestamp - prev_timestamp) / (1000 * 86400)))
                    last_ivl = reviews[i-1].get('ivl', 0)

                review['ivl'] = ivl
                factor = 2500
                card_type = 0 if i == 0 else 2

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

    print(f"已插入 {total_reviews} 条墨墨新记录")

    # 步骤5：恢复非墨墨卡片状态
    print("\n步骤5：恢复非墨墨卡片状态...")
    for card_id, state in non_momo_card_states.items():
        cursor.execute("""
            UPDATE cards
            SET type = ?, queue = ?, due = ?, ivl = ?, factor = ?, reps = ?, lapses = ?, left = ?, odue = ?
            WHERE id = ?
        """, (
            state['type'], state['queue'], state['due'], state['ivl'],
            state['factor'], state['reps'], state['lapses'], state['left'], state['odue'],
            card_id
        ))

    print(f"已恢复 {len(non_momo_card_states)} 张非墨墨卡片状态")

    # 步骤6：更新墨墨卡片状态
    print("\n步骤6：更新墨墨卡片状态...")
    momo_card_ids = [cards[word] for word in momo_words if word in cards]
    updated_count = 0

    for card_id in momo_card_ids:
        try:
            cursor.execute("""
                SELECT id, ease, ivl, lastIvl, factor, type
                FROM revlog
                WHERE cid = ?
                ORDER BY id ASC
            """, (card_id,))

            revlogs = cursor.fetchall()

            if not revlogs:
                continue

            reps = len(revlogs)
            lapses = sum(1 for r in revlogs if r[1] == 1)

            last_rev = revlogs[-1]
            last_rev_id, last_ease, last_ivl, last_lastIvl, last_factor, last_type = last_rev

            if last_ease == 1 and len(revlogs) > 1:
                prev_rev = revlogs[-2]
                current_ivl = prev_rev[2] if prev_rev[2] > 0 else 1
            else:
                current_ivl = last_ivl if last_ivl > 0 else 1

            due = int((last_rev_id / 1000 - collection_crt) / 86400) + current_ivl

            card_type = 2
            queue = 2

            factor = last_factor if last_factor and last_factor > 0 else 2500

            left = 0
            odue = 0
            mod = int(datetime.now().timestamp() * 1000)

            cursor.execute("""
                UPDATE cards
                SET type = ?, queue = ?, ivl = ?, due = ?, factor = ?, reps = ?, lapses = ?, left = ?, odue = ?, mod = ?
                WHERE id = ?
            """, (card_type, queue, current_ivl, due, factor, reps, lapses, left, odue, mod, card_id))

            updated_count += 1

            if updated_count % 100 == 0:
                print(f"进度: {updated_count} 张卡片...")

        except Exception as e:
            if error_count <= 10:
                print(f"错误: {e}")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"导入完成！")
    print(f"非墨墨revlog记录（保留）: {len(non_momo_revlogs)} 条")
    print(f"墨墨旧revlog记录（替换）: {len(momo_revlogs)} 条")
    print(f"墨墨新revlog记录: {total_reviews} 条")
    print(f"总revlog记录数: {len(non_momo_revlogs) + total_reviews} 条")
    print(f"非墨墨卡片状态（保留）: {len(non_momo_card_states)} 张")
    print(f"墨墨卡片状态（更新）: {updated_count} 张")
    print(f"错误: {error_count} 条")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True

def main():
    print("="*60)
    print("智能合并导入墨墨记忆数据（完整版）")
    print("="*60)

    word_reviews = get_review_history_combined()

    print("\n开始导入...")
    success = import_review_history_smart_full(word_reviews)

    if success:
        print("\n[完成] 数据已成功导入！")
        print("无需运行其他脚本，cards表状态已同时处理。")

if __name__ == '__main__':
    main()
