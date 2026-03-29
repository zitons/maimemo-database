#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从PDF提取单词和释义（处理编码问题）
"""

import json
import pdfplumber
import re
import time

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def extract_from_pdf_smart():
    """智能提取PDF中的单词和释义"""

    print("=" * 60)
    print("从PDF提取单词和释义（处理特殊字符）")
    print("=" * 60)

    # 加载单词列表
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    word_info_map = {item['word']: {
        'note_id': item['note_id'],
        'note_field': item['note_field']
    } for item in words_data}

    print(f"已加载 {len(words_data)} 个单词\n")

    results = {}
    matched_count = 0

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n开始提取...\n")

        for page_num, page in enumerate(pdf.pages, 1):
            try:
                # 尝试提取文本
                text = page.extract_text(layout=False) or ""

                if not text:
                    # 尝试提取表格
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if not table:
                                continue

                            for row_idx, row in enumerate(table):
                                if row_idx == 0:  # 跳过表头
                                    continue

                                if not row or len(row) < 2:
                                    continue

                                word_cell = row[0]
                                meaning_cell = row[1]

                                if not word_cell or not meaning_cell:
                                    continue

                                # 清理单词
                                word = word_cell.strip().lower()
                                word = re.sub(r'[\s\[\(\)\]{}].*', '', word)
                                word = re.sub(r'\d+\s+', '', word, count=1)
                                word = word.strip()
                                word = re.sub(r'[\s\-]+', '', word)

                                if word and word in word_info_map:
                                    # 清理释义
                                    meaning = meaning_cell.strip()
                                    meaning = re.sub(r'^[\d\.\-]+\s+', '', meaning)

                                    if meaning:
                                        item = word_info_map[word]
                                        results[word] = {
                                            'word': word,
                                            'interpretation': meaning,
                                            'note_id': item['note_id'],
                                            'note_field': item['note_field'],
                                            'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                                        }
                                        matched_count += 1

                                        if matched_count % 100 == 0:
                                            print(f"已匹配: {matched_count} 个")
            except Exception as e:
                pass  # 跳过错误的页面

            if page_num % 10 == 0:
                print(f"页面进度: {page_num}/{len(pdf.pages)} (匹配: {matched_count})")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"成功匹配: {matched_count} 个")
    print(f"覆盖率: {matched_count}/{len(words_data)} ({matched_count/len(words_data)*100:.1f}%)")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")


if __name__ == '__main__':
    extract_from_pdf_smart()
