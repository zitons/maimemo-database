#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨单词本PDF提取单词和释义
"""

import json
import pdfplumber
import re

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def extract_from_pdf():
    """从PDF提取单词和释义"""

    print("=" * 60)
    print("从墨墨单词本PDF提取单词和释义")
    print("=" * 60)

    # 先加载单词列表（获取note_id和note_field）
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    # 字典映射：word -> {note_id, note_field}
    word_info_map = {item['word']: {
        'note_id': item['note_id'],
        'note_field': item['note_field']
    } for item in words_data}

    print(f"已加载 {len(words_data)} 个单词的note信息")

    # 提取PDF中的数据
    results = {}
    extracted_count = 0
    not_found_count = 0

    print(f"\n开始提取PDF...")

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}")

        for page_num, page in enumerate(pdf.pages, 1):
            # 提取表格
            tables = page.extract_tables()

            if not tables:
                continue

            for table in tables:
                if not table:
                    continue

                # 跳过表头
                for row_idx, row in enumerate(table):
                    if row_idx == 0:  # 跳过表头
                        continue

                    if not row or len(row) < 2:
                        continue

                    # 提取单词和释义
                    word_cell = row[0]
                    meaning_cell = row[1]

                    if not word_cell or not meaning_cell:
                        continue

                    # 清理单词（移除空白和换行）
                    word = word_cell.strip().lower()

                    # 移除单词中的发音符号和括号
                    # 如"jeopardize [jəpɑːrdaɪz]" -> "jeopardize"
                    word = re.sub(r'\s*\[.*?\].*', '', word).strip()

                    if not word:
                        continue

                    # 清理释义（只取第一行或核心部分）
                    meaning = meaning_cell.strip()

                    # 检查单词是否在列表中
                    if word not in word_info_map:
                        not_found_count += 1
                        continue

                    # 保存结果
                    item = word_info_map[word]
                    results[word] = {
                        'word': word,
                        'interpretation': meaning,
                        'note_id': item['note_id'],
                        'note_field': item['note_field'],
                        'fetch_time': __import__('time').strftime('%Y-%m-%dT%H:%M:%S')
                    }
                    extracted_count += 1

                    if extracted_count % 100 == 0:
                        print(f"已提取: {extracted_count} 个")

            if page_num % 10 == 0:
                print(f"处理进度: {page_num}/{len(pdf.pages)} 页")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"总提取: {extracted_count} 个")
    print(f"未找到: {not_found_count} 个")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    extract_from_pdf()
