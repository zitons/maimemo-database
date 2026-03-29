#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取PDF内容并保存到文件
"""

import pdfplumber
import json

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
OUTPUT_FILE = "pdf_content_preview.txt"


def preview_pdf():
    """提取PDF前3页的内容"""

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("提取PDF前3页内容\n")
        f.write("=" * 60 + "\n")

        with pdfplumber.open(PDF_FILE) as pdf:
            f.write(f"\nPDF总页数: {len(pdf.pages)}\n\n")

            for page_num in range(min(3, len(pdf.pages))):
                page = pdf.pages[page_num]

                f.write(f"\n{'='*60}\n")
                f.write(f"第 {page_num + 1} 页\n")
                f.write(f"{'='*60}\n")

                # 提取文本
                f.write("\n--- 文本内容 ---\n")
                text = page.extract_text()
                if text:
                    f.write(text[:1000])
                    if len(text) > 1000:
                        f.write(f"\n\n... (共 {len(text)} 字符)\n")
                else:
                    f.write("（无文本）\n")

                # 提取表格
                f.write("\n--- 表格内容 ---\n")
                tables = page.extract_tables()

                if tables:
                    f.write(f"找到 {len(tables)} 个表格\n")
                    for table_idx, table in enumerate(tables):
                        if not table:
                            continue

                        f.write(f"\n表格 {table_idx + 1}:\n")
                        f.write(f"  行数: {len(table)}\n")

                        # 显示前10行
                        for row_idx, row in enumerate(table[:10]):
                            f.write(f"  行{row_idx}: {row}\n")

                        if len(table) > 10:
                            f.write(f"  ... (共 {len(table)} 行)\n")
                else:
                    f.write("（无表格）\n")

    print(f"内容已保存到: {OUTPUT_FILE}")


if __name__ == '__main__':
    preview_pdf()
