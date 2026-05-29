#!/usr/bin/env python3
"""
PDF文本提取工具 — 将PDF文件内容提取为文本。
用法:
  python pdf2txt.py <pdf文件路径>                # 输出到 stdout
  python pdf2txt.py <pdf文件路径> -o <输出路径>   # 保存到文件
"""
import sys
import argparse
import pdfplumber


def extract_text(pdf_path: str) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages.append(f"--- 第 {i + 1} 页 ---\n{text}")
    return "\n\n".join(pages)


def main():
    parser = argparse.ArgumentParser(description="提取PDF文件中的文本内容")
    parser.add_argument("pdf", help="PDF文件路径")
    parser.add_argument("-o", "--output", help="输出文本文件路径（默认输出到控制台）")
    args = parser.parse_args()

    try:
        text = extract_text(args.pdf)
    except Exception as e:
        print(f"错误：无法读取PDF文件：{e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"文本已保存到：{args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()