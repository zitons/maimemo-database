#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 momo.v5_5_65.db 提取复习记录数据
"""

import sqlite3
import pandas as pd
import numpy as np
import json
from datetime import datetime
from pathlib import Path

def parse_date(date_str):
    """将日期字符串转换为可读格式"""
    if date_str and date_str != '00000000000000':
        try:
            return datetime.strptime(date_str[:14], '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        except:
            return date_str
    return None

def parse_date_only(date_str):
    """仅解析日期部分"""
    if date_str and date_str != '00000000000000':
        try:
            return datetime.strptime(date_str[:8], '%Y%m%d').strftime('%Y-%m-%d')
        except:
            return date_str
    return None

def parse_history(history_str):
    """解析历史记录字符串"""
    if not history_str or history_str == '0':
        return []
    try:
        return [int(x) for x in history_str.split(',')]
    except:
        return []

def parse_list(list_str):
    """解析JSON列表字符串"""
    if not list_str or list_str == '[]':
        return []
    try:
        return json.loads(list_str)
    except:
        return []

def extract_vocabulary_data(conn):
    """提取词汇基础数据"""
    print("提取词汇基础数据...")
    query = """
    SELECT
        id as voc_id,
        spelling,
        phonetic_uk,
        phonetic_us,
        frequency,
        difficulty,
        study_user_count,
        acknowledge_rate
    FROM VOC_TB
    """
    df = pd.read_sql_query(query, conn)
    print(f"词汇数据: {len(df)} 条")
    return df

def extract_long_term_study_records(conn):
    """提取长期学习记录"""
    print("提取长期学习记录...")
    query = """
    SELECT
        lsr_uid as user_id,
        lsr_new_voc_id as voc_id,
        lsr_voc_id,
        lsr_frequency as frequency_score,
        lsr_fm as familiarity_level,
        lsr_fm_history_byday as fm_history,
        lsr_last_interval as last_interval_days,
        lsr_interval_history_byday as interval_history,
        lsr_last_response as last_response,
        lsr_response_history_byday as response_history,
        lsr_first_study_date,
        lsr_last_study_date,
        lsr_next_study_date,
        lsr_blocked_code,
        lsr_is_blocked_inDSR,
        lsr_been_blocked,
        lsr_is_new,
        lsr_study_method,
        lsr_add_date,
        lsr_add_order,
        lsr_last_real_interval,
        lsr_last_difficulty,
        lsr_factor,
        lsr_interpretations,
        lsr_phrases,
        lsr_notes
    FROM LSR_TB
    """
    df = pd.read_sql_query(query, conn)

    # 转换日期格式
    df['first_study_date_formatted'] = df['lsr_first_study_date'].apply(parse_date_only)
    df['last_study_date_formatted'] = df['lsr_last_study_date'].apply(parse_date_only)
    df['next_study_date_formatted'] = df['lsr_next_study_date'].apply(parse_date_only)
    df['add_date_formatted'] = df['lsr_add_date'].apply(parse_date)

    # 解析历史记录
    df['fm_history_list'] = df['fm_history'].apply(parse_history)
    df['interval_history_list'] = df['interval_history'].apply(parse_history)
    df['response_history_list'] = df['response_history'].apply(parse_history)

    print(f"长期学习记录: {len(df)} 条")
    return df

def extract_daily_study_records(conn):
    """提取每日学习记录"""
    print("提取每日学习记录...")
    query = """
    SELECT
        dsr_uid as user_id,
        dsr_new_voc_id as voc_id,
        dsr_appear_order,
        dsr_fm as familiarity_level,
        dsr_interval_inday,
        dsr_interval_byday,
        dsr_deviated_interval_byday,
        dsr_first_response,
        dsr_last_response,
        dsr_response_history_inday,
        dsr_record_time,
        dsr_is_blocked,
        dsr_blocked_code,
        dsr_is_new,
        dsr_is_finished,
        dsr_is_matrix,
        dsr_recall_time,
        dsr_study_time,
        dsr_study_method,
        dsr_is_advanced,
        dsr_factor,
        dsr_is_fill,
        dsr_is_algorithm
    FROM DSR_TB
    """
    df = pd.read_sql_query(query, conn)

    # 转换日期格式
    df['record_datetime'] = df['dsr_record_time'].apply(parse_date)

    # 解析历史记录
    df['response_history_list'] = df['dsr_response_history_inday'].apply(parse_history)

    # 删除原始字段
    df = df.drop(columns=['dsr_record_time', 'dsr_response_history_inday'])

    print(f"每日学习记录: {len(df)} 条")
    return df

def extract_statistics_records(conn):
    """提取统计记录"""
    print("提取学习统计记录...")
    query = """
    SELECT
        ssr_date,
        ssr_uid as user_id,
        ssr_count_words_studied,
        ssr_count_today_total,
        ssr_count_today_new,
        ssr_count_today_revision,
        ssr_count_today_well_familiar,
        ssr_count_today_familiar,
        ssr_count_today_uncertain,
        ssr_count_today_forget,
        ssr_count_today_sticking,
        ssr_count_today_unwanted,
        ssr_new_vocs_today_well_familiar,
        ssr_new_vocs_today_familiar,
        ssr_new_vocs_today_uncertain,
        ssr_new_vocs_today_forget,
        ssr_vocs_today_sticking,
        ssr_vocs_today_unwanted,
        ssr_today_study_time,
        ssr_today_study_time_ms,
        ssr_fm_10,
        ssr_fm_30,
        ssr_fm_60,
        ssr_fm_90
    FROM SSR_TB
    ORDER BY ssr_date
    """
    df = pd.read_sql_query(query, conn)

    # 转换日期格式
    df['study_date'] = df['ssr_date'].apply(parse_date_only)

    # 解析词汇列表
    df['vocs_well_familiar'] = df['ssr_new_vocs_today_well_familiar'].apply(parse_list)
    df['vocs_familiar'] = df['ssr_new_vocs_today_familiar'].apply(parse_list)
    df['vocs_uncertain'] = df['ssr_new_vocs_today_uncertain'].apply(parse_list)
    df['vocs_forget'] = df['ssr_new_vocs_today_forget'].apply(parse_list)
    df['vocs_sticking'] = df['ssr_vocs_today_sticking'].apply(parse_list)
    df['vocs_unwanted'] = df['ssr_vocs_today_unwanted'].apply(parse_list)

    # 转换学习时间为分钟
    df['study_time_minutes'] = df['ssr_today_study_time_ms'] / 60000.0

    # 删除原始字段
    df = df.drop(columns=['ssr_date', 'ssr_new_vocs_today_well_familiar',
                          'ssr_new_vocs_today_familiar', 'ssr_new_vocs_today_uncertain',
                          'ssr_new_vocs_today_forget', 'ssr_vocs_today_sticking',
                          'ssr_vocs_today_unwanted'])

    print(f"统计记录: {len(df)} 条")
    return df

def create_summary_report(stats_df, long_term_df, daily_df, vocab_df):
    """创建汇总报告"""
    print("\n创建汇总报告...")

    def to_python_type(val):
        """将numpy类型转换为Python原生类型"""
        if pd.isna(val):
            return None
        if isinstance(val, (int, float, str)):
            return val
        return float(val) if isinstance(val, (np.integer, np.floating)) else str(val)

    import numpy as np

    summary = {
        'overview': {
            'total_vocabulary': int(len(vocab_df)),
            'total_words_studied': int(long_term_df['voc_id'].nunique()),
            'total_study_days': int(len(stats_df)),
            'total_daily_records': int(len(daily_df))
        },
        'study_period': {
            'first_study_date': to_python_type(stats_df['study_date'].min()) if len(stats_df) > 0 else None,
            'last_study_date': to_python_type(stats_df['study_date'].max()) if len(stats_df) > 0 else None
        },
        'study_statistics': {
            'total_study_time_minutes': float(stats_df['ssr_today_study_time_ms'].sum() / 60000.0) if len(stats_df) > 0 else 0.0,
            'total_words': int(stats_df['ssr_count_words_studied'].sum()) if len(stats_df) > 0 else 0,
            'total_new_words': int(stats_df['ssr_count_today_new'].sum()) if len(stats_df) > 0 else 0,
            'total_revision_words': int(stats_df['ssr_count_today_revision'].sum()) if len(stats_df) > 0 else 0,
            'avg_words_per_day': float(stats_df['ssr_count_today_total'].mean()) if len(stats_df) > 0 else 0.0
        },
        'familiarity_distribution': {
            'well_familiar': int(stats_df['ssr_count_today_well_familiar'].sum()) if len(stats_df) > 0 else 0,
            'familiar': int(stats_df['ssr_count_today_familiar'].sum()) if len(stats_df) > 0 else 0,
            'uncertain': int(stats_df['ssr_count_today_uncertain'].sum()) if len(stats_df) > 0 else 0,
            'forget': int(stats_df['ssr_count_today_forget'].sum()) if len(stats_df) > 0 else 0
        }
    }

    return summary

def main():
    """主函数"""
    db_path = 'momo.v5_5_65.db'
    output_dir = Path('review_records_export')
    output_dir.mkdir(exist_ok=True)

    print(f"开始从 {db_path} 提取复习记录数据...\n")

    # 连接数据库
    conn = sqlite3.connect(db_path)

    try:
        # 提取各类数据
        vocab_df = extract_vocabulary_data(conn)
        long_term_df = extract_long_term_study_records(conn)
        daily_df = extract_daily_study_records(conn)
        stats_df = extract_statistics_records(conn)

        # 合并词汇信息到学习记录
        print("\n合并词汇信息...")
        long_term_with_vocab = long_term_df.merge(
            vocab_df[['voc_id', 'spelling', 'phonetic_uk', 'phonetic_us', 'difficulty']],
            on='voc_id',
            how='left'
        )

        daily_with_vocab = daily_df.merge(
            vocab_df[['voc_id', 'spelling', 'phonetic_uk', 'phonetic_us', 'difficulty']],
            on='voc_id',
            how='left'
        )

        # 创建汇总报告
        summary = create_summary_report(stats_df, long_term_df, daily_df, vocab_df)

        # 导出数据
        print("\n导出数据到文件...")

        # 导出为Excel
        excel_path = output_dir / 'review_records.xlsx'
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            stats_df.to_excel(writer, sheet_name='每日统计', index=False)
            long_term_with_vocab.to_excel(writer, sheet_name='长期学习记录', index=False)
            daily_with_vocab.to_excel(writer, sheet_name='每日学习记录', index=False)
            vocab_df.to_excel(writer, sheet_name='词汇库', index=False)

        # 导出为CSV
        stats_df.to_csv(output_dir / 'daily_statistics.csv', index=False, encoding='utf-8-sig')
        long_term_with_vocab.to_csv(output_dir / 'long_term_records.csv', index=False, encoding='utf-8-sig')
        daily_with_vocab.to_csv(output_dir / 'daily_records.csv', index=False, encoding='utf-8-sig')
        vocab_df.to_csv(output_dir / 'vocabulary.csv', index=False, encoding='utf-8-sig')

        # 导出汇总报告
        import json
        summary_path = output_dir / 'summary_report.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 打印汇总信息
        print("\n" + "="*60)
        print("数据提取完成！")
        print("="*60)
        print(f"\n【数据概览】")
        print(f"词汇库总量: {summary['overview']['total_vocabulary']} 个单词")
        print(f"已学习单词: {summary['overview']['total_words_studied']} 个")
        print(f"学习天数: {summary['overview']['total_study_days']} 天")
        print(f"学习记录条数: {summary['overview']['total_daily_records']} 条")

        print(f"\n【学习时间】")
        print(f"首次学习: {summary['study_period']['first_study_date']}")
        print(f"最近学习: {summary['study_period']['last_study_date']}")
        print(f"总学习时长: {summary['study_statistics']['total_study_time_minutes']:.1f} 分钟")
        print(f"日均学习: {summary['study_statistics']['avg_words_per_day']:.1f} 个单词")

        print(f"\n【复习情况】")
        print(f"总学习次数: {summary['study_statistics']['total_words']}")
        print(f"新学单词: {summary['study_statistics']['total_new_words']}")
        print(f"复习单词: {summary['study_statistics']['total_revision_words']}")

        print(f"\n【掌握程度分布】")
        print(f"非常熟悉: {summary['familiarity_distribution']['well_familiar']}")
        print(f"熟悉: {summary['familiarity_distribution']['familiar']}")
        print(f"不确定: {summary['familiarity_distribution']['uncertain']}")
        print(f"忘记: {summary['familiarity_distribution']['forget']}")

        print(f"\n【导出文件】")
        print(f"Excel文件: {excel_path}")
        print(f"CSV文件目录: {output_dir}")
        print(f"汇总报告: {summary_path}")
        print("="*60)

    finally:
        conn.close()

if __name__ == '__main__':
    main()
