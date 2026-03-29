#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨单词本PDF提取单词和释义（改进版，处理多词性）
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
    print("从墨墨单词本PDF提取单词和释义（改进版）")
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
    total_extracted = 0

    # 匹配模式
    pattern_with_number = r'^(\d+)\s*\.?\s*(\w+)\s+(\w+\.)\s+(.+)'
    pattern_without_word = r'^(\d+)\s*\.?\s+(\w+\.)\s+(.+)'  # 多词性情况

    current_word = None
    current_number = None

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n开始提取...\n")

        for page_num, page in enumerate(pdf.pages, 1):
            try:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue

                    # 尝试匹配：数字.? 单词 词性. 释义
                    match = re.match(pattern_with_number, line)

                    if match:
                        total_extracted += 1
                        number = match.group(1)
                        word = match.group(2).lower().strip()
                        pos = match.group(3)
                        rest = match.group(4)

                        current_word = word
                        current_number = number

                        # 提取释义
                        meaning_match = re.search(r'([\u4e00-\u9fff；；、，,\s]+)', rest)
                        if meaning_match:
                            meaning = meaning_match.group(1).strip()
                        else:
                            meaning = rest[:50].strip()

                        full_interpretation = f"{pos} {meaning}"

                        # 检查单词是否在列表中
                        if word in word_info_map and word not in results:
                            item = word_info_map[word]
                            results[word] = {
                                'word': word,
                                'interpretation': full_interpretation,
                                'note_id': item['note_id'],
                                'note_field': item['note_field'],
                                'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                            }
                            matched_count += 1

                            if matched_count % 50 == 0:
                                print(f"已匹配: {matched_count} 个")

                    # 尝试匹配多词性：数字.? 词性. 释义（单词名在上一行）
                    elif current_word:
                        match2 = re.match(pattern_without_word, line)
                        if match2:
                            # 这是当前单词的另一个词性
                            pos = match2.group(2)
                            rest = match2.group(3)

                            meaning_match = re.search(r'([\u4e00-\u9fff；；、，,\s]+)', rest)
                            if meaning_match:
                                meaning = meaning_match.group(1).strip()
                            else:
                                meaning = rest[:50].strip()

                            # 追加到现有释义
                            if current_word in results:
                                results[current_word]['interpretation'] += f"; {pos} {meaning}"
                            elif current_word in word_info_map:
                                item = word_info_map[current_word]
                                results[current_word] = {
                                    'word': current_word,
                                    'interpretation': f"{pos} {meaning}",
                                    'note_id': item['note_id'],
                                    'note_field': item['note_field'],
                                    'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                                }
                                matched_count += 1

            except Exception as e:
                pass

            if page_num % 10 == 0:
                print(f"页面进度: {page_num}/{len(pdf.pages)} (PDF中提取: {total_extracted}, 匹配: {matched_count})")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"PDF中总单词数: {total_extracted}")
    print(f"成功匹配: {matched_count}")
    print(f"覆盖率: {matched_count}/{len(words_data)} ({matched_count/len(words_data)*100:.1f}%)")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")


if __name__ == '__main__':
    extract_from_pdf()
