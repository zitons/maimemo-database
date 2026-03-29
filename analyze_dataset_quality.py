#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析数据集质量和FSRS拟合问题
"""

import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_dataset():
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', '账户 1')
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找2021红宝书牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_ids = []
    for did, name in cursor.fetchall():
        try:
            if '2021' in name and '红宝书' in name:
                deck_ids.append(did)
        except:
            pass

    placeholders = ','.join(['?' for _ in deck_ids])

    print('=' * 60)
    print('数据集质量分析')
    print('=' * 60)

    # 1. 评分分布
    print('\n1. 评分分布（FSRS需要多样性）:')
    cursor.execute(f'''
        SELECT r.ease, COUNT(*) as count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        GROUP BY r.ease
        ORDER BY r.ease
    ''', deck_ids)

    ease_names = {1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy'}
    results = cursor.fetchall()
    total = sum(count for _, count in results)

    for ease, count in results:
        pct = count * 100.0 / total
        print(f'  {ease_names.get(ease, ease)}: {count} ({pct:.1f}%)')

    # 2. 时间分布
    print('\n2. 时间跨度分析:')
    cursor.execute(f'''
        SELECT MIN(r.id) as min_ts, MAX(r.id) as max_ts, COUNT(*) as total
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
    ''', deck_ids)

    min_ts, max_ts, total = cursor.fetchone()
    start_date = datetime.fromtimestamp(min_ts / 1000)
    end_date = datetime.fromtimestamp(max_ts / 1000)
    days = (max_ts - min_ts) / (1000 * 86400)

    print(f'  最早记录: {start_date.strftime("%Y-%m-%d")}')
    print(f'  最晚记录: {end_date.strftime("%Y-%m-%d")}')
    print(f'  时间跨度: {days:.0f} 天')
    print(f'  总记录数: {total} 条')
    print(f'  平均每天: {total/days:.1f} 条')

    # 3. 每张卡片的复习次数分布
    print('\n3. 每张卡片的复习次数分布:')
    cursor.execute(f'''
        SELECT
            CASE
                WHEN review_count = 1 THEN '1次'
                WHEN review_count BETWEEN 2 AND 5 THEN '2-5次'
                WHEN review_count BETWEEN 6 AND 10 THEN '6-10次'
                WHEN review_count > 10 THEN '>10次'
            END as range,
            COUNT(*) as card_count
        FROM (
            SELECT c.id, COUNT(*) as review_count
            FROM cards c
            JOIN revlog r ON c.id = r.cid
            WHERE c.did IN ({placeholders})
            GROUP BY c.id
        )
        GROUP BY range
        ORDER BY MIN(review_count)
    ''', deck_ids)

    for range_name, count in cursor.fetchall():
        print(f'  {range_name}: {count} 张卡片')

    # 4. Again率分析
    print('\n4. Again率分析（FSRS拟合的关键）:')
    cursor.execute(f'''
        SELECT
            c.id,
            SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) as again_count,
            COUNT(*) as total_count
        FROM cards c
        JOIN revlog r ON c.id = r.cid
        WHERE c.did IN ({placeholders})
        GROUP BY c.id
    ''', deck_ids)

    again_rates = []
    for card_id, again_count, total_count in cursor.fetchall():
        again_rate = again_count / total_count if total_count > 0 else 0
        again_rates.append(again_rate)

    if again_rates:
        avg_again = sum(again_rates) / len(again_rates) * 100
        print(f'  平均Again率: {avg_again:.1f}%')
        print(f'  Again率范围: {min(again_rates)*100:.1f}% - {max(again_rates)*100:.1f}%')

        # Again率分布
        again_dist = defaultdict(int)
        for rate in again_rates:
            if rate < 0.2:
                again_dist['0-20%'] += 1
            elif rate < 0.4:
                again_dist['20-40%'] += 1
            elif rate < 0.6:
                again_dist['40-60%'] += 1
            elif rate < 0.8:
                again_dist['60-80%'] += 1
            else:
                again_dist['80-100%'] += 1

        print('\n  Again率分布:')
        for range_name in ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']:
            print(f'    {range_name}: {again_dist[range_name]} 张卡片')

    # 5. 间隔分布
    print('\n5. 间隔分布（FSRS优化的关键）:')
    cursor.execute(f'''
        SELECT r.ivl, COUNT(*) as count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        AND r.ivl > 0
        GROUP BY r.ivl
        ORDER BY r.ivl
        LIMIT 20
    ''', deck_ids)

    print('  前20个间隔天数:')
    for ivl, count in cursor.fetchall():
        print(f'    {ivl}天: {count} 次')

    # 6. 数据问题检查
    print('\n6. 潜在问题检查:')

    # 检查间隔为0但评分是Good的情况
    cursor.execute(f'''
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        AND r.ivl = 0
        AND r.ease = 3
    ''', deck_ids)

    count = cursor.fetchone()[0]
    if count > 0:
        print(f'  [!] 间隔=0但评分=Good的记录: {count} 条（可能是新卡片评Good）')

    # 检查type分布
    print('\n7. Revlog的type分布:')
    cursor.execute(f'''
        SELECT r.type, COUNT(*) as count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        GROUP BY r.type
        ORDER BY r.type
    ''', deck_ids)

    type_names = {0: 'new', 1: 'learning', 2: 'review', 3: 'relearning'}
    for rtype, count in cursor.fetchall():
        print(f'  {type_names.get(rtype, rtype)}: {count} 条')

    conn.close()

    print('\n' + '=' * 60)
    print('FSRS拟合建议：')
    print('=' * 60)
    print('如果FSRS拟合困难，可能的原因：')
    print('1. Again率过高或过低（理想范围20-40%）')
    print('2. 评分过于单一（缺少Hard/Easy评分）')
    print('3. 时间戳批量导入导致分布不自然')
    print('4. 间隔数据不符合FSRS的记忆曲线模型')
    print('5. 只有Again和Good评分，缺少Hard/Easy')
    print('\n解决方案：')
    print('- 继续使用Anki学习，让FSRS收集更多真实数据')
    print('- 评分时更准确地区分Hard/Good/Easy')
    print('- FSRS会随着数据积累逐渐优化参数')

if __name__ == '__main__':
    analyze_dataset()
