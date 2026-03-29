#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用pdfplumber提取PDF内容并展示
"""

import pdfplumber
import json

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"

def preview_pdf():
    """提取PDF前3页的内容"""

    print("=" * 60)
    print("提取PDF前3页内容")
    print("=" * 60)

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"\nPDF总页数: {len(pdf.pages)}\n")

        for page_num in range(min(3, len(pdf.pages))):
            page = pdf.pages[page_num]

            print(f"\n{'='*60}")
            print(f"第 {page_num + 1} 页")
            print(f"{'='*60}")

            # 提取文本
            print("\n--- 文本内容 ---")
            text = page.extract_text()
            if text:
                # 显示前500个字符
                print(text[:500])
                if len(text) > 500:
                    print(f"\n... (共 {len(text)} 字符)")
            else:
                print("（无文本）")

            # 提取表格
            print("\n--- 表格内容 ---")
            tables = page.extract_tables()

            if tables:
                print(f"找到 {len(tables)} 个表格")
                for table_idx, table in enumerate(tables):
                    if not table:
                        continue

                    print(f"\n表格 {table_idx + 1}:")
                    print(f"  行数: {len(table)}")

                    # 显示前5行
                    for row_idx, row in enumerate(table[:5]):
                        print(f"  行{row_idx}: {row}")

                    if len(table) > 5:
                        print(f"  ... (共 {len(table)} 行)")
            else:
                print("（无表格）")


if __name__ == '__main__':
    preview_pdf()
