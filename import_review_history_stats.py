#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从每日统计表重建完整的复习历史并导入到Anki的revlog表
使用统计方法：SSR_TB + DSR_TB
"""

import sqlite3
import json
from datetime import datetime
import os
import shutil

def get_review_history_from_stats(momo_db='momo.v5_5_65.db'):
    """从每日统计表重建复习历史"""

    print("Step 1: 从SSR表获取每日单词状态...")
    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    # 获取所有单词的ID到spelling映射
    cursor.execute("SELECT id, spelling FROM VOC_TB")
    voc_id_to_spelling = {row[0]: row[1] for row in cursor.fetchall()}

    # 从SSR表提取每日复习记录
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

    # 构建每个单词的复习历史
    word_reviews = {}

    for row in cursor.fetchall():
        date_str, well_familiar, familiar, uncertain, forget = row

        # 解析日期
        date = datetime.strptime(date_str[:8], '%Y%m%d')

        # 处理每种状态的单词
        def parse_voc_list(voc_list_str, response):
            if voc_list_str and voc_list_str != '[]':
                voc_ids = json.loads(voc_list_str)
                for voc_id in voc_ids:
                    if voc_id not in word_reviews:
                        word_reviews[voc_id] = []
                    word_reviews[voc_id].append({
                        'date': date,
                        'response': response
                    })

        parse_voc_list(forget, 3)        # forget -> 响应3 (Again)
        parse_voc_list(uncertain, 2)     # uncertain -> 响应2 (Hard)
        parse_voc_list(familiar, 1)       # familiar -> 响应1 (Good)
        parse_voc_list(well_familiar, 1)  # well_familiar -> 响应1 (Good/Easy)

    conn.close()

    print(f"找到 {len(word_reviews)} 个单词的复习记录")

    # 获取DSR表中的耗时数据
    print("\nStep 2: 从DSR表获取复习耗时...")
    conn = sqlite3.connect(momo_db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            dsr_new_voc_id,
            dsr_record_time,
            dsr_recall_time,
            dsr_study_time
        FROM DSR_TB
        ORDER BY dsr_record_time
    """)

    # 构建单词到耗时的映射
    word_times = {}
    for row in cursor.fetchall():
        voc_id, record_time, recall_time, study_time = row
        if voc_id not in word_times:
            word_times[voc_id] = []

        date = datetime.strptime(record_time[:14], '%Y%m%d%H%M%S')
        word_times[voc_id].append({
            'date': date,
            'recall_time': recall_time,  # 毫秒
            'study_time': study_time      # 毫秒
        })

    conn.close()
    print(f"找到 {len(word_times)} 个单词的耗时数据")

    # 合并数据
    print("\nStep 3: 合并复习历史和耗时数据...")
    for voc_id in word_reviews:
        if voc_id in word_times:
            # 匹配日期
            for review in word_reviews[voc_id]:
                review_date = review['date'].date()
                for time_data in word_times[voc_id]:
                    if time_data['date'].date() == review_date:
                        review['recall_time'] = time_data['recall_time']
                        review['study_time'] = time_data['study_time']
                        break

    # 按日期排序
    for voc_id in word_reviews:
        word_reviews[voc_id].sort(key=lambda x: x['date'])

    return word_reviews, voc_id_to_spelling


def import_review_history_to_anki(word_reviews, voc_id_to_spelling, anki_profile='账户 1'):
    """导入复习历史到Anki"""

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
        except Exception as e:
            print("\n[错误] Anki似乎还在运行！")
            print("请完全关闭Anki后再运行此脚本。")
            return False

    print(f"\nAnki数据库: {anki_db}")

    # 备份数据库
    backup_file = anki_db + f'.backup_stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 连接到Anki数据库
    print("\n连接Anki数据库...")
    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找墨墨背单词牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_id = None
    for did, name in cursor.fetchall():
        try:
            if '墨墨' in name or 'momo' in name.lower() or 'Momo' in name:
                deck_id = did
                print(f"找到牌组: {name} (ID: {did})")
                break
        except:
            pass

    if not deck_id:
        print("[错误] 找不到'墨墨背单词'牌组")
        conn.close()
        return False

    # 查找所有卡片
    cursor.execute(f"""
        SELECT c.id, c.nid, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did = ?
    """, (deck_id,))

    cards = {row[2].split('\x1f')[0]: row[0] for row in cursor.fetchall()}
    print(f"找到 {len(cards)} 张卡片")

    # 导入复习历史
    print("\n导入复习历史...")
    total_reviews = 0
    error_count = 0

    for voc_id, reviews in word_reviews.items():
        if voc_id not in voc_id_to_spelling:
            continue

        spelling = voc_id_to_spelling[voc_id]
        if spelling not in cards:
            continue

        card_id = cards[spelling]

        for i, review in enumerate(reviews):
            try:
                # 计算时间戳（毫秒）
                timestamp = int(review['date'].timestamp() * 1000)
                # 添加偏移避免冲突
                timestamp += i * 1000

                # 映射响应到Anki评分
                response = review['response']
                if response == 3:
                    ease = 1  # Again
                elif response == 2:
                    ease = 2  # Hard
                else:
                    ease = 3  # Good

                # 计算间隔
                if i == 0:
                    ivl = 0
                    last_ivl = 0
                else:
                    prev_date = reviews[i-1]['date']
                    ivl = (review['date'] - prev_date).days
                    last_ivl = reviews[i-1].get('ivl', 0)

                review['ivl'] = ivl

                # 获取耗时（默认20秒）
                recall_time = review.get('recall_time', 20000)

                # 卡片类型
                if i == 0:
                    card_type = 0  # new
                else:
                    card_type = 2  # review

                # 难度因子（默认2.5）
                factor = 2500

                # 插入revlog记录
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
                    recall_time,
                    card_type
                ))

                total_reviews += 1

            except Exception as e:
                error_count += 1
                if error_count <= 5:
                    print(f"错误: {e}")

        if total_reviews % 500 == 0:
            print(f"进度: {total_reviews} 条复习记录...")

    # 提交更改
    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"导入完成！")
    print(f"总复习记录: {total_reviews} 条")
    print(f"处理单词: {len(word_reviews)} 个")
    if error_count > 0:
        print(f"错误: {error_count} 条")
    print(f"备份保存在: {backup_file}")
    print(f"{'='*60}")

    return True


def main():
    print("="*60)
    print("从统计表重建复习历史")
    print("="*60)

    # 从统计表获取复习历史
    word_reviews, voc_id_to_spelling = get_review_history_from_stats()

    # 导入到Anki
    print("\n重要提示：请确保Anki已完全关闭！")
    import_review_history_to_anki(word_reviews, voc_id_to_spelling)

    print("\n[完成] 复习历史已导入到Anki！")
    print("现在可以打开Anki，FSRS将使用这些历史数据进行优化。")


if __name__ == '__main__':
    main()
