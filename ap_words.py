#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ap_words.py
This Python script is for Japanese national exams for IT engineers.
Author: Junichiro Higuchi
----------------------------------------------------------------
"""

import re
import sys
import argparse
from textwrap import dedent

# 用語例記述の段落が終了したと判断する行頭のパターン
HEADPAT = r'^[1-9]|[【➢（]|[①-⑳]|(?:[1-9][0-9])'

DICTIONARY = [] # 検出した用語のすべてを格納するグローバル変数
RUNMODE = "normal" # コマンド指定による全体的な動作モード
DEFAULT_ASK_FILE = "ap_words_asks.txt"
DEFAULT_SYLLABUS_FILE = "ap_syllabus.txt"

def clean_text(text: str) -> str:
    """テキストからインデントを削除し、前後の空白を削除します。"""
    return dedent(text).strip()

def read_paragraphs(filename) -> list:
    """
    テキストファイルを読み込み、空行で区切られた段落をリストとして返す。
    エラー発生時は空のリストを返す。
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            paragraphs = []
            current_paragraph = []

            for line in f:
                if line.strip() == '':
                    if current_paragraph:
                        paragraphs.append(''.join(current_paragraph).strip())
                        current_paragraph = []
                else:
                    current_paragraph.append(line)

            if current_paragraph:
                paragraphs.append(''.join(current_paragraph).strip())
        return paragraphs

    except FileNotFoundError:
        print(f"Error: ファイル '{filename}' が見つかりません。",file=sys.stderr)
        return []

    except Exception as e:
        print(f"Error: {type(e).__name__}:{e}",file=sys.stderr)
        return []

def get_ask_prompt(filename: str, para_id: list) -> str:
    """
    Args:
        filename: プロンプト文の格納されてるテキストファイル。
        id: プロンプト文に追加する段落のリスト
    """
    ask_default = clean_text("\
    以下の用語の解説を、基本的に400文字以内、複雑な場合は最大700文字で、表形式でまとめてください。\n\
    文体は簡潔にするために、「だ・である」系や体言止めでお願いします。")

    # 段落を asks に読み込む
    if not filename:
        return ask_default
    asks = read_paragraphs(filename)
    if not asks:
        return ask_default

    # 無効な段落番号が含まれている場合は全体無効として入力処理につなげる
    for id in para_id:
        if id > len(asks):
            para_id = []
            break

    # 段落番号指定がされていない場合は入力
    if not para_id:
        # p_asks = [f"{i}) {a[:200]}..." for i, a in enumerate(asks, start=1)]
        p_asks = [f"{i}) {a}" for i, a in enumerate(asks, start=1)]
        print("\n".join(p_asks), file=sys.stderr)
        print("="*20, file=sys.stderr)
        while True:
            s = input("出力する段落を(複数ある場合カンマ区切り)で入力してください。>>")
            try:
                parts = s.split(',')
                tmp = [int(n.strip()) for n in parts]
                para_id = [n for n in tmp if 0 < n <= len(asks)]
                if not para_id:
                    print(f"有効な段落番号が入力されませんでした。1から{len(asks)}までの範囲で入力してください。", file=sys.stderr)
                    continue
            except ValueError:
                print("エラー: 数字とカンマ（,）のみで入力してください。", file=sys.stderr)
            except Exception as e:
                print(f"予期せぬエラーが発生しました: {type(e).__name__} - {e}", file=sys.stderr)
            else:
                break

    ask = ""
    for i, txt in enumerate(asks, start=1):
        if i in para_id:
            if not ask:
                ask = txt + "\n"
            else:
                ask += "|\n" + txt + "\n"

    return clean_text(ask) if ask else ask_default

def preprocess_line(text: str) -> str:
    """
    pdfからコピペしたシラバステキストの前処理を行います。
    Args:
        text (str): 編集する文字列。
    Returns:
        str: 編集後の文字列。
    """
    text = re.sub(r"\.{3,}", "...", text)
    text = re.sub(r"^Copyright.*", "", text, flags=re.S)
    text = re.sub(r"-\d{1,3}-", "", text)
    return text.strip()


def listup_wordlines(wordlines) -> list:
    """
    wordlinesの中身を1行ずつ処理して、単語を取り出し、yougo リストに追加する。
    """
    global DICTIONARY

    full_text = "".join(line.strip() for line in wordlines)

    yougo = []
    current_word = ""
    in_parentheses = False

    for char in full_text:
        if char == '(' or char == '（':
            in_parentheses = True
        elif char == ')' or char == '）':
            in_parentheses = False
        
        if not in_parentheses and (char == '、' or char == '，'):
            if current_word:
                insertword = current_word.strip()
                if insertword not in DICTIONARY:
                    DICTIONARY.append(insertword)
                yougo.append(insertword)
            current_word = ""
        else:
            current_word += char

    if current_word:
        yougo.append(current_word.strip())

    return yougo    

def print_line(text, output_stream):
    """
    動作モードに応じて、テキストを出力する。
    """
    match RUNMODE:
        case "normal":
            print(text.strip(), file=output_stream)

def process_text_file(filename, ask_txt, output_stream):
    h1txt = ""
    h2txt = ""
    wordlines = []
    midashistr = ""

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = preprocess_line(line)
                if not line: continue

                if midashistr:
                    # 見出しがある場合は先にその行を出力
                    print_line(f"\n{midashistr}", output_stream)
                    midashistr = ""

                if m1_match := re.match(r'^\s*[\(（](\d|[\uff10-\uff19]+)[\)）]\s*(.*)', line):
                    num1str = m1_match.group(1).strip()
                    h1txt = m1_match.group(2).strip()
                    h2txt = ""
                    midashistr = f"({num1str}) {h1txt}"
                elif m2_match := re.match(r'^\s*([①-⑳])\s*(.*)', line):
                    num2str = m2_match.group(1).strip()
                    h2txt = m2_match.group(2).strip()
                    midashistr = f"{num2str} {h2txt}"
                elif re.match(r'^\s*用語例', line):
                    # 「用語例」が見つかったら、これまでの用語を処理
                    if wordlines:
                        tango = listup_wordlines(wordlines)
                        print_ai_prompt(h1txt, h2txt, tango, ask_txt, output_stream)
                        wordlines = []
                    # 次の行から用語をキャプチャ開始
                    wordlines.append(re.sub(r'^\s*用語例\s*', '', line).strip())
                elif wordlines:
                    # 用語例キャプチャモード
                    if not re.match(HEADPAT, line) or not line.strip():
                        wordlines.append(line.strip())
                    else:
                        # 用語例の終わり
                        tango = listup_wordlines(wordlines)
                        print_ai_prompt(h1txt, h2txt, tango, ask_txt, output_stream)
                        wordlines = []
                        print_line(line, output_stream)
                else:
                    # 通常モード
                    print_line(line, output_stream)

            # ファイルの最後に用語が残っている場合に出力処理
            if wordlines:
                tango = listup_wordlines(wordlines)
                print_ai_prompt(h1txt, h2txt, tango, ask_txt, output_stream)

    except FileNotFoundError:
        print(f"ファイル '{filename}' が見つかりません。", file=sys.stderr)
        sys.exit(1)

def print_ai_prompt(h1txt, h2txt, tango, ask_txt, output_stream):
    if RUNMODE == "dict":
        return
    midashi_text = ""
    if h1txt and h2txt:
        midashi_text = f"「{h1txt}」における「{h2txt}」"
    elif h1txt:
        midashi_text = f"「{h1txt}」"
    elif h2txt:
        midashi_text = f"「{h2txt}」"
    
    if h1txt:
        print(f"", file=output_stream)
    print(f"_ask\n応用情報処理試験の出題範囲{midashi_text}について、\n{ask_txt}", file=output_stream)
    for word in tango:
        print(word, file=output_stream)
    print(file=output_stream)

def print_usage():
    msg = f"""
ap_words.py - 応用情報技術者試験のシラバスから用語を抜き出しプロンプト文を作成する

使用例
    python ap_words.py ap.txt > ~/app.txt
    python ap_words.py ap.txt -a 1,3 -o ~/app.txt
    python ap_words.py ap.txt -a 99 -o ~/app.txt

書式
    ap_words.py [-h] [-a ASK_PROMPT] [-o OUTPUT_FILE] [mode] filename_syllabus

位置引数:
  filename_syllabus     IPAシラバスの全選択コピペしたテキスト。省略不可。

オプション:
  -h, --help            ヘルプメッセージを表示して終了します
  -a, --ask [段落番号|ファイル名]
                        <ファイル名>: プロンプトテキストのファイル名を指定します。
                        <段落番号>: 使用するテキストの段落番号（1〜）を指定します。
                                   複数指定する場合はカンマ区切りで入力します。
                                   存在しない段落番号が含まれていると起動後に選択画面となります。
  -o, --output OUTPUT_FILE
                        結果を出力するファイル名を指定します。指定しない場合は標準出力に出力します。

コマンド:
  normal (default)      通常処理。用語解説依頼テキスト以外の情報も出力します。
  ask                   用語解説依頼テキストのみを出力します。
  dict                  用語リストのみを出力します。

"""
    print(clean_text(msg))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="IPAシラバスから用語を抽出し、プロンプト文を作成します。",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False
    )
    parser.add_argument('filename_syllabus', nargs='?', help="IPAシラバスの全選択コピペしたテキスト。")
    parser.add_argument('mode', nargs='?', choices=['normal', 'ask', 'dict'], default='normal', help="コマンド")
    parser.add_argument('-h', '--help', action='store_true', help="ヘルプメッセージを表示して終了します")
    parser.add_argument('-a', '--ask', dest='ask_prompt', help="プロンプトテキストのファイル名か、段落番号を指定します。")
    parser.add_argument('-o', '--output', dest='output_file', help="結果を出力するファイル名を指定します。")

    args = parser.parse_args()

    if args.help:
        print_usage()
        sys.exit(0)

    if not args.filename_syllabus:
        print("読み込むシラバステキストのファイル名が指定されていません。", file=sys.stderr)
        print_usage()
        sys.exit(1)

    RUNMODE = args.mode

    prompt_id = []
    prompt_file = ""
    if args.ask_prompt:
        try:
            # 段落番号の場合
            prompt_id = [int(n.strip()) for n in args.ask_prompt.split(',')]
            prompt_file = DEFAULT_ASK_FILE
        except ValueError:
            # ファイル名の場合
            prompt_file = args.ask_prompt

    ask_txt = get_ask_prompt(prompt_file, prompt_id)
    
    # 出力先の決定
    if args.output_file:
        try:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                process_text_file(args.filename_syllabus, ask_txt, f)
        except Exception as e:
            print(f"Error: 出力ファイル '{args.output_file}' への書き込みに失敗しました。詳細: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 標準出力へ出力
        process_text_file(args.filename_syllabus, ask_txt, sys.stdout)

    # 辞書モードなら、用語リストを出力
    if RUNMODE == "dict":
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                print("\n".join(DICTIONARY), file=f)
        else:
            print("\n".join(DICTIONARY), file=sys.stdout)
