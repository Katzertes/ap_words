#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ap_words.py
情報処理技術者試験のシラバスから用語を抽出し、プロンプト文を生成します。
Author: Junichiro Higuchi
----------------------------------------------------------------
"""

import re
import sys
import argparse
import io
from textwrap import dedent
from pathlib import Path
from datetime import date
from typing import Generator, Any, TextIO, List, Iterable, Set

# --- 定数 ---
DEFAULT_ASK_FILE = "ap_words_asks.txt"

# ----------------------------------------
# ヘルパー関数

def clean_text(text: str) -> str:
    """テキストのインデントを削除し、前後の空白を取り除きます。"""
    return dedent(text).strip()

def read_paragraphs(filename: str) -> list:
    """
    テキストファイルを読み込み、空行で区切られた段落のリストを返します。
    エラーの場合は空のリストを返します。
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # 連続した空行を区切り文字として段落に分割
            return [p.strip() for p in f.read().split('\n\n') if p.strip()]
    except FileNotFoundError:
        print(f"エラー: ファイル '{filename}' が見つかりません。", file=sys.stderr)
        return []
    except Exception as e:
        print(f"エラー: {type(e).__name__}:{e}", file=sys.stderr)
        return []

def get_ask_prompt(filename: str, para_id: list) -> str:
    """
    AIへのプロンプト文を構築します。
    
    Args:
        filename: プロンプト文が格納されたテキストファイル。
        para_id: プロンプト文に含める段落番号のリスト。
    """
    ask_default = clean_text("""
    以下の用語の解説を、基本的に400文字以内、複雑な場合は最大700文字で、表形式でまとめてください。
    文体は簡潔にするために、「だ・である」系や体言止めでお願いします。
    """)

    if not filename:
        return ask_default
    
    asks = read_paragraphs(filename)
    if not asks:
        return ask_default

    # 段落番号が有効かチェック
    is_id_valid = all(0 < i <= len(asks) for i in para_id)

    # 段落番号の指定がない、または無効な場合はユーザーに入力を求める
    if not para_id or not is_id_valid:
        print("\n--- プロンプト文の選択 ---", file=sys.stderr)
        p_asks = [f"[{i:2d}] {a[:30]}..." for i, a in enumerate(asks, start=1)]
        print("\n".join(p_asks), file=sys.stderr)
        print("="*40, file=sys.stderr)
        
        while True:
            try:
                s = input("使用する段落をカンマ区切りで入力してください: >> ")
                parts = s.split(',')
                tmp = [int(n.strip()) for n in parts]
                para_id = [n for n in tmp if 0 < n <= len(asks)]
                if para_id:
                    break
                print(f"無効な入力です。1から{len(asks)}までの数字を入力してください。", file=sys.stderr)
            except ValueError:
                print("エラー: 数字とカンマのみで入力してください。", file=sys.stderr)
            except Exception as e:
                print(f"予期せぬエラーが発生しました: {e}", file=sys.stderr)

    selected_prompts = [asks[i-1] for i in para_id]
    # 複数のプロンプト文がある場合はパイプ記号で区切る
    return "\n|\n".join(selected_prompts) if selected_prompts else ask_default

def preprocess_line(text: str) -> str:
    """シラバスPDFからコピーしたテキストの1行を前処理します。"""
    text = re.sub(r"\.{3,}", "...", text)  # 長すぎるドットリーダーを短縮
    text = re.sub(r"^Copyright\(c\) Information.*", "", text)  # Copyright行を削除
    text = re.sub(r"^-\d{1,3}-$", "", text)  # ページ番号行を削除
    text = re.sub(r'^[\s\u3000\ufeff\u200b]+', '', text)  # 行頭の空白や不可視文字を削除
    return text.strip()

# ----------------------------------------
# 中核ロジック関数

def listup_wordlines(wordlines: List[str]) -> list:
    """
    複数行のテキストを結合し、括弧の外にある「、」または「，」で区切られた用語を抽出します。
    """
    full_text = "".join(line for line in wordlines)
    yougo = []
    current_word = ""
    in_parentheses = 0  # 括弧のネストレベル

    for char in full_text:
        if char in '（(':
            in_parentheses += 1
        elif char in '）)':
            if in_parentheses > 0:
                in_parentheses -= 1
        
        # 括弧の外にある読点（区切り文字）を検出
        if in_parentheses == 0 and char in '、，':
            if current_word.strip():
                yougo.append(current_word.strip())
            current_word = ""
        else:
            current_word += char

    # 最後の単語を追加
    if current_word.strip():
        yougo.append(current_word.strip())

    return yougo

def parse_syllabus(filename: str) -> Generator[dict, None, None]:
    """
    シラバスファイルを解析し、構造化されたデータブロックをyieldするジェネレータです。
    この関数は解析のみに専念し、出力形式には関与しません。
    """
    h1txt = ""
    h2txt = ""
    wordlines = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = preprocess_line(line)
            if not line: continue

            # ▼▼▼ 変更点: 目次行の判定ロジックを追加 ▼▼▼
            # 行末が「...」と数字で終わる場合は目次行とみなし、通常のテキストとして処理する
            if re.search(r'\s*\.{3,}\s*\d+$', line):
                yield {'type': 'text', 'text': line}
                continue
            # ▲▲▲ 変更点 ▲▲▲

            # --- 各階層の見出しに対応する正規表現 ---
            m_class_match = re.match(r'大分類(\d+|[\uff10-\uff19]+)[:：](.+)\s+中分類(\d+|[\uff10-\uff19]+)[:：](.+)', line)
            m3_match = re.match(r'^\s*(\d+)\.\s+(.*)', line)
            m1_match = re.match(r'^\s*[\(（](\d|[\uff10-\uff19]+)[\)）]\s*(.*)', line)
            m2_match = re.match(r'^\s*([①-⑳])\s*(.*)', line)
            m_sub_match = re.match(r'^\s*[\(（]([a-z])[\)）]\s*(.*)', line)
            m_word_start = re.match(r'^\s*用語例(.*)', line)
            
            # --- 現在の「用語例」ブロックを終了させるためのロジック ---
            is_header_or_class = m_class_match or m3_match or m1_match or m2_match or m_sub_match
            if wordlines and (is_header_or_class or m_word_start):
                yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}
                wordlines = []
            
            # --- マッチしたパターンに基づいて現在の行を処理 ---
            if m_class_match:
                h1txt, h2txt = "", "" # 文脈をリセット
                full_title = f"大分類{m_class_match.group(1)}：{m_class_match.group(2).strip()} 中分類{m_class_match.group(3)}：{m_class_match.group(4).strip()}"
                link_text = f"中分類{m_class_match.group(3)}：{m_class_match.group(4).strip()}"
                yield {'type': 'header', 'level': 1, 'text': link_text, 'full_title': full_title}
            elif m3_match:
                h1txt = m3_match.group(2).strip()
                h2txt = ""
                yield {'type': 'header', 'level': 2, 'text': f"{m3_match.group(1)}. {h1txt}"}
            elif m1_match:
                h2txt = m1_match.group(2).strip() # このレベルではh2txtを使用
                yield {'type': 'header', 'level': 3, 'text': f"({m1_match.group(1)}) {h2txt}"}
            elif m2_match:
                # このレベルではプロンプト用のh1/h2文脈を更新しない
                yield {'type': 'header', 'level': 4, 'text': f"{m2_match.group(1)} {m2_match.group(2).strip()}"}
            elif m_sub_match:
                yield {'type': 'text', 'text': line}
            elif m_word_start:
                wordlines.append(m_word_start.group(1).strip())
            elif wordlines:
                wordlines.append(line)
            else:
                yield {'type': 'text', 'text': line}
        
        # ファイル末尾に残っている用語例ブロックを処理
        if wordlines:
            yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}

# ----------------------------------------
# 出力整形関数

def format_prompt(h1txt: str, h2txt: str, words: List[str], ask_txt: str, out: TextIO):
    """AIへのプロンプトテキストを整形して出力します。"""
    midashi_text = ""
    if h1txt and h2txt:
        midashi_text = f"「{h1txt}」における「{h2txt}」"
    elif h1txt:
        midashi_text = f"「{h1txt}」"
    
    print(f"\n_ask\n応用情報技術者試験のシラバスの{midashi_text}について、\n{ask_txt}", file=out)
    for word in words:
        print(word, file=out)
    print(file=out)

def output_results(structured_data: Iterable[dict], ask_txt: str, out: TextIO, use_md: bool, mode: str, level_offset: int = 0):
    """
    解析済みのデータを受け取り、モードとレベルオフセットに基づいて出力用に整形します。
    """
    for block in structured_data:
        b_type = block.get('type')

        if b_type == 'header':
            if mode == "normal":
                level = block.get('level', 1)
                # レベルがオフセット後も1以上の場合のみ出力
                if level - level_offset > 0:
                    text = block.get('text', '').strip()
                    prefix = "#" * (level - level_offset) + " " if use_md else ""
                    print(f"\n{prefix}{text}", file=out)

        elif b_type == 'text':
            if mode == "normal":
                print(block.get('text', '').strip(), file=out)

        elif b_type == 'word_block':
            words = block.get('words', [])
            if not words: continue

            if mode == "ask":
                format_prompt(block['h1'], block['h2'], words, ask_txt, out)
            elif mode == "normal":
                print(f"\n用語例: {', '.join(words)}", file=out)
                format_prompt(block['h1'], block['h2'], words, ask_txt, out)

def handle_split_output(args: argparse.Namespace, ask_txt: str, structured_data: List[dict]):
    """分割出力モードの処理を行います。"""
    base_path = Path(args.output_file)
    base_name = base_path.stem
    ext = base_path.suffix

    chunks = []
    pre_content = []
    current_chunk = []
    
    # データを中分類（レベル1ヘッダー）ごとに分割
    first_header_found = False
    for block in structured_data:
        if block.get('type') == 'header' and block.get('level') == 1:
            first_header_found = True
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = [block]
        elif first_header_found:
            current_chunk.append(block)
        else:
            pre_content.append(block)
    if current_chunk:
        chunks.append(current_chunk)

    # 1. 目次ファイルの作成
    with open(base_path, 'w', encoding='utf-8') as f:
        print("目次\n---", file=f)
        for i, chunk in enumerate(chunks, 1):
            chunk_title = chunk[0].get('text', f'無題{i}')
            split_filename = f"{base_name}{i:02d}{ext}"
            print(f"- [{chunk_title}]({split_filename})", file=f)
        
        print("\n---", file=f)
        # 序文を出力
        output_results(pre_content, ask_txt, f, True, "normal")

    # 2. 各分割ファイルの作成
    for i, chunk in enumerate(chunks, 1):
        split_filename = base_path.parent / f"{base_name}{i:02d}{ext}"
        full_title = chunk[0].get('full_title', '無題')
        with open(split_filename, 'w', encoding='utf-8') as f:
            # YAMLフロントマターの出力
            print("---", file=f)
            print(f"title: {full_title}", file=f)
            print(f"date: {date.today().isoformat()}", file=f)
            print("tags: [応用情報技術者試験, シラバス, 用語集]", file=f)
            print("---\n", file=f)
            
            # 本文の先頭にタイトルを太字で出力
            print(f"**{full_title}**\n", file=f)

            # 最初のヘッダーを除いた内容を、レベルを1下げて出力
            output_results(chunk[1:], ask_txt, f, True, "normal", level_offset=1)

def handle_output(args: argparse.Namespace, ask_txt: str, structured_data: List[dict], master_dictionary: Set[str]):
    """
    引数に基づいて、単一出力または分割出力を実行します。
    """
    if args.split:
        if not args.output_file:
            print("エラー: 分割出力モード(-S)では出力ファイル名(-o)の指定が必須です。", file=sys.stderr)
            sys.exit(1)
        if not Path(args.output_file).suffix.lower() in (".md", ".markdown"):
            print("エラー: 分割出力モードはMarkdown形式(.md, .markdown)でのみサポートされています。", file=sys.stderr)
            sys.exit(1)
        
        handle_split_output(args, ask_txt, structured_data)
        print(f"分割ファイルが {Path(args.output_file).stem}XX.md の形式で生成されました。", file=sys.stderr)

    else: # 単一ファイル出力
        use_md = args.output_file and Path(args.output_file).suffix.lower() in (".md", ".markdown")
        output_target = args.output_file

        def write_data(out_stream):
            if args.mode == "dict":
                print("\n".join(sorted(list(master_dictionary))), file=out_stream)
            else:
                output_results(structured_data, ask_txt, out_stream, use_md, args.mode)

        if output_target:
            try:
                with open(output_target, 'w', encoding='utf-8') as f:
                    write_data(f)
            except Exception as e:
                print(f"エラー: 出力ファイル '{output_target}' への書き込みに失敗しました。詳細: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            write_data(sys.stdout)

# ----------------------------------------
# メイン実行ブロック

def print_usage():
    """コマンドラインの使用方法を出力します。"""
    msg = """
    ap_words.py - 応用情報技術者試験のシラバスから用語を抜き出しプロンプト文を作成する

    書式:
        python ap_words.py <シラバスファイル> [mode] [-a PROMPT] [-o 出力ファイル] [-S]

    引数:
      シラバスファイル        必須。IPAシラバスをコピーしたテキストファイル。

    コマンド:
      normal (default)      通常処理。用語プロンプト以外の情報も出力します。
      ask                   AIへの用語解説依頼プロンプトのみを出力します。
      dict                  抽出した用語リストのみを出力します。

    オプション:
      -h, --help            このヘルプメッセージを表示して終了します。
      -a, --ask PROMPT      プロンプトテキストのファイル名、または段落番号(例: "1,3")を指定します。
      -o, --output FILE     結果を出力するファイル名を指定します。指定しない場合は標準出力になります。
                            拡張子が .md の場合、Markdown形式で出力します。
      -s, -S, --split       出力を中分類ごとにMarkdownファイルに分割します (-oでのファイル指定が必須)。
    """
    print(clean_text(msg))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="IPAシラバスから用語を抽出し、プロンプト文を作成します。",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False
    )
    parser.add_argument('filename_syllabus', nargs='?', help="IPAシラバスのテキストファイル。")
    parser.add_argument('mode', nargs='?', choices=['normal', 'ask', 'dict'], default='normal', help="実行モード。")
    parser.add_argument('-h', '--help', action='store_true', help="ヘルプメッセージを表示します。")
    parser.add_argument('-a', '--ask', dest='ask_prompt', help="プロンプトファイルまたは段落番号。")
    parser.add_argument('-o', '--output', dest='output_file', help="出力ファイル名。")
    parser.add_argument('-s', '-S', '--split', action='store_true', help="出力を中分類ごとに分割します。")

    args = parser.parse_args()

    if args.help:
        print_usage()
        sys.exit(0)

    if not args.filename_syllabus:
        print("エラー: シラバスのファイル名が指定されていません。", file=sys.stderr)
        print_usage()
        sys.exit(1)

    # --- ステップ1: プロンプト文の準備 ---
    prompt_id = []
    prompt_file = ""
    if args.ask_prompt:
        try:
            # 引数が数字なら段落番号として解釈
            prompt_id = [int(n.strip()) for n in args.ask_prompt.split(',')]
            prompt_file = DEFAULT_ASK_FILE
        except ValueError:
            # 数字でなければファイル名として解釈
            prompt_file = args.ask_prompt
    ask_txt = get_ask_prompt(prompt_file, prompt_id)
    
    # --- ステップ2: シラバスの解析とデータ集約 ---
    # ジェネレータはここで一度だけ消費し、全データ構造を構築する
    try:
        structured_data = []
        master_dictionary = set()
        
        results_generator = parse_syllabus(args.filename_syllabus)
        for block in results_generator:
            structured_data.append(block)
            if block.get('type') == 'word_block' and block.get('words'):
                master_dictionary.update(block['words'])

    except FileNotFoundError:
        # エラーメッセージは parse_syllabus 内で処理済み
        sys.exit(1)
    except Exception as e:
        print(f"解析中にエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)
        
    # --- ステップ3: 出力処理 ---
    # 集約したデータをまとめて出力ハンドラに渡す
    handle_output(args, ask_txt, structured_data, master_dictionary)

