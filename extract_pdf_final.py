#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨单词本PDF提取单词和释义（正确的格式解析）
"""

import json
import pdfplumber
import re
import time

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def extract_from_pdf():
    """从PDF提取单词和释义"""

    print("=" * 60)
    print("从墨墨单词本PDF提取单词和释义")
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
    total_lines = 0

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n开始提取...\n")

        for page_num, page in enumerate(pdf.pages, 1):
            try:
                text = page.extract_text()
                if not text:
                    continue

                # 按行分割
                lines = text.split('\n')

                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    total_lines += 1

                    # 匹配格式：数字. 单词 词性 释义
                    # 例如：1 jeopardize v. 危及；损害 Being late so often...
                    match = re.match(r'^(\d+)\.\s+([a-z\-]+)\s+([a-z]+\.)\s+(.+)', line, re.IGNORECASE)

                    if match:
                        word = match.group(2).lower().strip()
                        pos = match.group(3)  # 词性
                        meaning_and_example = match.group(4)  # 释义和例句

                        # 提取释义（例句之前的部分）
                        # 释义通常包含中文、分号等
                        meaning_match = re.match(r'^([^\u4e00-\u9fff]*[\u4e00-\u9fff；；、，,]+)', meaning_and_example)
                        if meaning_match:
                            meaning = meaning_match.group(1).strip()
                        else:
                            # 如果没有找到中文，取前30个字符
                            meaning = meaning_and_example[:30].strip()

                        # 组合：词性 + 释义
                        full_interpretation = f"{pos} {meaning}"

                        # 检查单词是否在列表中
                        if word in word_info_map:
                            item = word_info_map[word]
                            results[word] = {
                                'word': word,
                                'interpretation': full_interpretation,
                                'note_id': item['note_id'],
                                'note_field': item['note_field'],
                                'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                            }
                            matched_count += 1

                            if matched_count % 100 == 0:
                                print(f"已匹配: {matched_count} 个")

                    i += 1

            except Exception as e:
                pass

            if page_num % 10 == 0:
                print(f"页面进度: {page_num}/{len(pdf.pages)} (已匹配: {matched_count})")

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
    extract_from_pdf()
