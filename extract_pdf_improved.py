#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨单词本PDF提取所有单词和释义（改进版）
使用多行匹配来捕获所有格式的条目
"""

import json
import pdfplumber
import re
import time

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results_improved.json"


def extract_from_pdf():
    """从PDF提取单词和释义"""

    print("=" * 60)
    print("从墨墨单词本PDF提取所有单词和释义（改进版）")
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
    all_pdf_words = {}  # 存储所有从PDF提取的单词
    unmatched_words = []  # 记录未匹配的单词

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

                    # 跳过空行
                    if not line:
                        i += 1
                        continue

                    # 匹配模式：数字（可选的点） 单词
                    match = re.match(r'^(\d+)\s*\.?\s+(\w+)', line)

                    if match:
                        number = match.group(1)
                        word = match.group(2).lower().strip()
                        total_extracted += 1

                        # 尝试从接下来的行提取释义信息
                        interpretation = ""
                        j = i + 1
                        found_interpre = False

                        # 向下查找，最多查找10行
                        while j < min(i + 10, len(lines)):
                            next_line = lines[j].strip()

                            # 如果遇到下一个词条（数字开头）就停止
                            if re.match(r'^\d+\s*\.?\s+\w+', next_line):
                                break

                            # 查找包含中文的行（词性和释义）
                            if re.search(r'[\u4e00-\u9fff]', next_line):
                                interpretation = next_line
                                found_interpre = True
                                break

                            # 如果找到词性标记（v., n., adj.等），继续查找释义
                            if re.match(r'^[a-z]+\.\s+', next_line):
                                # 这行可能包含词性和释义
                                interpretation = next_line
                                found_interpre = True
                                break

                            j += 1

                        # 存储这个单词的信息
                        all_pdf_words[word] = {
                            'number': number,
                            'interpretation': interpretation
                        }

                        # 如果在需要的单词列表中
                        if word in word_info_map and word not in results:
                            if interpretation:  # 只有有释义才记录
                                item = word_info_map[word]
                                results[word] = {
                                    'word': word,
                                    'interpretation': interpretation,
                                    'note_id': item['note_id'],
                                    'note_field': item['note_field'],
                                    'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                                }
                                matched_count += 1

                                if matched_count % 50 == 0:
                                    print(f"已匹配: {matched_count} 个")
                            else:
                                unmatched_words.append(word)

                    i += 1

            except Exception as e:
                print(f"页面 {page_num} 错误: {e}")

            if page_num % 10 == 0:
                print(f"页面进度: {page_num}/{len(pdf.pages)} (PDF中提取: {total_extracted}, 已匹配: {matched_count})")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计信息
    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"PDF中总单词数: {total_extracted}")
    print(f"成功匹配: {matched_count}")
    print(f"覆盖率: {matched_count}/{len(words_data)} ({matched_count/len(words_data)*100:.1f}%)")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")

    # 输出前10个匹配成功的单词
    print("\n前10个匹配成功的单词示例：")
    for word, data in list(results.items())[:10]:
        print(f"  {word}: {data['interpretation'][:50]}...")


if __name__ == '__main__':
    extract_from_pdf()
