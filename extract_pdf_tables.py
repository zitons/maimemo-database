#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用pdfplumber从墨墨单词本PDF提取表格数据
"""

import json
import pdfplumber
import re
import time

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def clean_word(word_str):
    """清理单词字符串"""
    if not word_str:
        return None

    # 转小写
    word = word_str.strip().lower()

    # 移除发音符号和括号内容
    # 例如: "jeopardize [jəpɑːrdaɪz]" -> "jeopardize"
    word = re.sub(r'\s*[\[\(].*?[\]\)].*', '', word)

    # 移除行号和其他前缀
    word = re.sub(r'^\d+\s+', '', word)

    # 移除多余空格
    word = re.sub(r'\s+', '', word)

    return word if word else None


def extract_from_pdf():
    """从PDF提取单词和释义"""

    print("=" * 60)
    print("从墨墨单词本PDF提取单词和释义")
    print("=" * 60)

    # 先加载单词列表
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    word_info_map = {item['word']: {
        'note_id': item['note_id'],
        'note_field': item['note_field']
    } for item in words_data}

    print(f"已加载 {len(words_data)} 个单词的note信息")

    results = {}
    extracted_count = 0
    matched_count = 0

    print(f"\n开始提取PDF...\n")

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n")

        for page_num, page in enumerate(pdf.pages, 1):
            # 提取页面的表格
            tables = page.extract_tables()

            if not tables:
                if page_num % 10 == 0:
                    print(f"第 {page_num}/{len(pdf.pages)} 页：无表格")
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # 遍历表格行（跳过表头）
                for row_idx, row in enumerate(table):
                    # 跳过表头行
                    if row_idx == 0:
                        continue

                    if not row or len(row) < 2:
                        continue

                    # 第一列是单词，第二列是释义
                    word_cell = row[0]
                    meaning_cell = row[1]

                    if not word_cell or not meaning_cell:
                        continue

                    # 清理单词
                    word = clean_word(word_cell)
                    if not word:
                        continue

                    extracted_count += 1

                    # 检查是否在需要的单词列表中
                    if word in word_info_map:
                        # 清理释义（移除行号和多余空格）
                        meaning = meaning_cell.strip()
                        meaning = re.sub(r'^[\d\-\.]+\s+', '', meaning)
                        meaning = meaning.strip()

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

            if page_num % 10 == 0:
                print(f"处理进度: {page_num}/{len(pdf.pages)} 页 (已提取 {extracted_count} 条记录)")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"PDF中总记录数: {extracted_count}")
    print(f"成功匹配: {matched_count} 个")
    print(f"覆盖率: {matched_count}/{len(words_data)} ({matched_count/len(words_data)*100:.1f}%)")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    extract_from_pdf()
