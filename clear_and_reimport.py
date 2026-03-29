#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从每日统计表重建完整的复习历史并导入到Anki的revlog表
使用真实时间戳（优先DSR表，其次SSR表）
"""

import sqlite3
import json
from datetime import datetime, timedelta
import os
import shutil
from collections import defaultdict

def clear_revlog(anki_profile='账户 1'):
    """清除墨墨牌组的revlog数据"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("清除旧的revlog数据...")

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        try:
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except:
            print("[错误] Anki似乎还在运行！")
            return False

    # 备份
    backup_file = anki_db + f'.backup_clear_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_id = None
    for did, name in cursor.fetchall():
        try:
            if '墨墨' in name or 'momo' in name.lower():
                deck_id = did
                break
        except:
            pass

    if not deck_id:
        print("[错误] 找不到牌组")
        conn.close()
        return False

    # 删除revlog
    cursor.execute(f"""
        DELETE FROM revlog
        WHERE cid IN (SELECT id FROM cards WHERE did = {deck_id})
    """)

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"已删除 {deleted} 条revlog记录")
    return True


def get_review_history(momo_db='momo.v5_5_65.db'):
    """从统计表获取复习历史"""

    print("Step 1: 从DSR表获取详细复习记录（含时间戳）...")
    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # DSR表有精确的时间戳和耗时
    cursor.execute("""
        SELECT
            dsr_new_voc_id,
            dsr_record_time,
            dsr_fm,
            dsr_last_response,
            dsr_recall_time,
            dsr_study_time,
            dsr_interval_byday
        FROM DSR_TB
        ORDER BY dsr_record_time
    """)

    # 构建单词的复习历史
    word_reviews = defaultdict(list)

    for row in cursor.fetchall():
        voc_id, record_time, fm, last_response, recall_time, study_time, interval = row

        # 解析精确时间戳
        try:
            date = datetime.strptime(record_time[:14], '%Y%m%d%H%M%S')
        except:
            continue

        # 映射响应
        if last_response == 3:
            ease = 1  # Again - forget
        elif last_response == 2:
            ease = 3  # Good
        elif last_response == 1:
            ease = 4  # Easy
        else:
            ease = 3  # Good (默认)

        word_reviews[voc_id].append({
            'date': date,
            'timestamp': int(date.timestamp() * 1000),  # 毫秒时间戳
            'ease': ease,
            'fm': fm,
            'recall_time': recall_time if recall_time else 20000,
            'study_time': study_time if study_time else 20000,
            'interval': interval if interval else 0,
            'source': 'DSR'  # 标记来源
        })

    conn.close()
    print(f"从DSR表获取 {len(word_reviews)} 个单词的复习记录")

    # 从SSR表补充缺失的记录
    print("\nStep 2: 从SSR表补充复习记录...")
    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ssr_date,
            ssr_new_vocs_today_well_familiar,
            ssr_new_vocs_today_familiar,
            ssr_new_vocs_today_uncertain,
            ssr_new_vocs_today_forget,
            ssr_today_study_time_ms,
            ssr_count_today_total
        FROM SSR_TB
        ORDER BY ssr_date
    """)

    ssr_count = 0
    for row in cursor.fetchall():
        date_str, well_familiar, familiar, uncertain, forget, total_time_ms, total_count = row

        date = datetime.strptime(date_str[:8], '%Y%m%d')

        # 计算平均耗时
        avg_time = int(total_time_ms / total_count) if total_count > 0 else 20000

        # 每天内的时间偏移（秒）
        time_offset = 0

        def parse_voc_list(voc_list_str, response):
            nonlocal time_offset, ssr_count
            if voc_list_str and voc_list_str != '[]':
                voc_ids = json.loads(voc_list_str)
                for voc_id in voc_ids:
                    # 检查是否已经有该日期的记录（避免重复）
                    existing_dates = [r['date'].date() for r in word_reviews[voc_id]]
                    if date.date() not in existing_dates:
                        # 使用日期+时间偏移作为时间戳
                        timestamp = int(date.timestamp() * 1000) + (time_offset * 1000)

                        word_reviews[voc_id].append({
                            'date': date,
                            'timestamp': timestamp,
                            'ease': response,
                            'fm': None,
                            'recall_time': avg_time,
                            'study_time': avg_time,
                            'interval': 0,
                            'source': 'SSR'
                        })
                        ssr_count += 1
                        time_offset += 1  # 每个单词增加1秒偏移

        # forget -> Again (1)
        parse_voc_list(forget, 1)
        # uncertain -> Hard (2)
        parse_voc_list(uncertain, 2)
        # familiar -> Good (3)
        parse_voc_list(familiar, 3)
        # well_familiar -> Easy (4)
        parse_voc_list(well_familiar, 4)

    conn.close()
    print(f"从SSR表补充了 {ssr_count} 条记录")

    # 排序
    for voc_id in word_reviews:
        word_reviews[voc_id].sort(key=lambda x: x['timestamp'])

    # 获取单词ID映射
    print("\nStep 3: 获取单词映射...")
    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()
    cursor.execute("SELECT id, spelling FROM VOC_TB")
    voc_id_to_spelling = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    return dict(word_reviews), voc_id_to_spelling


def import_to_anki(word_reviews, voc_id_to_spelling, anki_profile='账户 1'):
    """导入到Anki"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("\n" + "="*60)
    print("导入复习历史到Anki")
    print("="*60)

    # 备份
    backup_file = anki_db + f'.backup_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_id = None
    for did, name in cursor.fetchall():
        try:
            if '墨墨' in name or 'momo' in name.lower():
                deck_id = did
                print(f"找到牌组: {name} (ID: {did})")
                break
        except:
            pass

    if not deck_id:
        print("[错误] 找不到牌组")
        conn.close()
        return False

    # 查找卡片
    cursor.execute(f"""
        SELECT c.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did = ?
    """, (deck_id,))

    cards = {}
    for card_id, fields in cursor.fetchall():
        spelling = fields.split('\x1f')[0]
        cards[spelling] = card_id

    print(f"找到 {len(cards)} 张卡片")

    # 导入复习历史
    print("\n导入复习历史...")
    total_reviews = 0
    error_count = 0

    used_timestamps = set()  # 记录已使用的时间戳

    for voc_id, reviews in word_reviews.items():
        if voc_id not in voc_id_to_spelling:
            continue

        spelling = voc_id_to_spelling[voc_id]
        if spelling not in cards:
            continue

        card_id = cards[spelling]

        for i, review in enumerate(reviews):
            try:
                timestamp = review['timestamp']

                # 确保时间戳唯一
                while timestamp in used_timestamps:
                    timestamp += 1  # 增加1毫秒

                used_timestamps.add(timestamp)

                # 计算间隔
                if i == 0:
                    ivl = 0
                    last_ivl = 0
                else:
                    prev_timestamp = reviews[i-1]['timestamp']
                    ivl = max(0, int((timestamp - prev_timestamp) / (1000 * 86400)))  # 天数
                    last_ivl = reviews[i-1].get('ivl', 0)

                review['ivl'] = ivl

                # 难度因子
                fm = review.get('fm')
                if fm:
                    factor = int(fm * 2500)
                    factor = max(1300, min(factor, 5000))
                else:
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
                    review['ease'],
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
    print(f"成功导入: {total_reviews} 条复习记录")
    print(f"错误: {error_count} 条")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


def main():
    print("="*60)
    print("使用真实时间戳重建复习历史")
    print("="*60)

    # 清除旧数据
    if not clear_revlog():
        return

    # 获取复习历史
    word_reviews, voc_id_to_spelling = get_review_history()

    # 导入到Anki
    print("\n重要: 请确保Anki已完全关闭！")
    import_to_anki(word_reviews, voc_id_to_spelling)

    print("\n[完成] 复习历史已成功导入！")
    print("现在可以打开Anki，FSRS将使用这些数据。")


if __name__ == '__main__':
    main()
