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
import io
from textwrap import dedent
from pathlib import Path
from typing import Generator, Any, TextIO, List

# Global Variables
# 用語例記述の段落が終了したと判断する行頭のパターン
HEADPAT = r'^[1-9]|[【➢（]|[①-⑳]|(?:[1-9][0-9])'

DICTIONARY: List[str] = [] # 検出した用語のすべてを格納するグローバル変数（データ生成時に更新）
RUNMODE = "normal" # コマンド指定による全体的な動作モード
DEFAULT_ASK_FILE = "ap_words_asks.txt"
DEFAULT_SYLLABUS_FILE = "ap_syllabus.txt"

# ----------------------------------------

def clean_text(text: str) -> str:
    """テキストからインデントを削除し、前後の空白を削除します。"""
    return dedent(text).strip()

def read_paragraphs(filename: str) -> list:
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

    if not filename:
        return ask_default
    
    asks = read_paragraphs(filename)
    if not asks:
        return ask_default

    # 無効な段落番号が含まれている場合は全体無効として入力処理につなげる
    is_id_valid = True
    for id in para_id:
        if id <= 0 or id > len(asks):
            is_id_valid = False
            break

    # 段落番号指定がない、または無効な場合は入力
    if not para_id or not is_id_valid:
        print("\n--- プロンプト文の選択 ---", file=sys.stderr)
        p_asks = [f"[{i:2d}] {a[:30]}..." for i, a in enumerate(asks, start=1)]
        print("\n".join(p_asks), file=sys.stderr)
        print("="*40, file=sys.stderr)
        
        while True:
            s = input("使用する段落を(複数ある場合カンマ区切り)で入力してください。>>")
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
                # 複数のプロンプト文を区切るためのパイプ文字
                ask += "|\n" + txt + "\n"

    return clean_text(ask) if ask else ask_default

def preprocess_line(text: str) -> str:
    """
    pdfからコピペしたシラバステキストの前処理を行います。
    """
    # 目次での長すぎるドットリーダーを短縮
    text = re.sub(r"\.{3,}", "...", text) 
    # Copyright 行を消す
    text = re.sub(r"^Copyright\(c\) Information.*", "", text) 
    # ページ番号行を消す
    text = re.sub(r"^-\d{1,3}-$", "", text) 
    return text.strip()


def listup_wordlines(wordlines: List[str]) -> list:
    """
    wordlinesを連結し、括弧の外にある「、」「，」を区切り文字として単語を抽出する。
    抽出した単語はグローバル辞書に追加する。
    """
    global DICTIONARY

    full_text = "".join(line for line in wordlines)

    yougo = []
    current_word = ""
    in_parentheses = 0 # 括弧のネストレベル

    for char in full_text:
        if char == '(' or char == '（':
            in_parentheses += 1
        elif char == ')' or char == '）':
            if in_parentheses > 0:
                in_parentheses -= 1
        
        # 括弧の外にあるカンマを検出
        if in_parentheses == 0 and (char == '、' or char == '，'):
            if current_word:
                insertword = current_word.strip()
                if insertword not in DICTIONARY:
                    DICTIONARY.append(insertword)
                yougo.append(insertword)
            current_word = ""
        else:
            current_word += char

    if current_word:
        insertword = current_word.strip()
        if insertword:
             if insertword not in DICTIONARY:
                DICTIONARY.append(insertword)
             yougo.append(insertword)

    return yougo    

def parse_syllabus(filename: str) -> Generator[dict, None, None]:
    """
    シラバスファイルを解析し、抽出された構造化データをyieldするジェネレータ。
    この関数は出力に関わる処理は行わず、データの抽出と構造化のみを行う。
    """
    h1txt = ""
    h2txt = ""
    wordlines = []
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                # 前処理
                line = preprocess_line(line)
                if not line: continue

                # (1)〜　の形式の見出し行にマッチした時の処理 (大項目)
                m1_match = re.match(r'^\s*[\(（](\d|[\uff10-\uff19]+)[\)）]\s*(.*)', line)
                # ①〜　の形式の見出し行にマッチした時の処理 (中項目)
                m2_match = re.match(r'^\s*([①-⑳])\s*(.*)', line)
                # （a）〜　の形式の見出し行にマッチした時の処理 (小項目)
                m_sub_match = re.match(r'^\s*[\(（]([a-z])[\)）]\s*(.*)', line)


                # --- ★修正ロジック★ ---
                # 用語キャプチャモード中に、次の見出しに遭遇したら直ちに現在のブロックを終了させる
                # 既存の m1_match, m2_match のどちらか、または新しい m_sub_match にマッチした場合
                if wordlines and (m1_match or m2_match or m_sub_match):
                    # 直前の用語例ブロックを処理
                    yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}
                    wordlines = []
                # -----------------------


                if m1_match:
                    num1str = m1_match.group(1).strip()
                    h1txt = m1_match.group(2).strip()
                    h2txt = ""
                    yield {'type': 'header', 'level': 2, 'text': f"({num1str}) {h1txt}"}
 
                elif m2_match:
                    num2str = m2_match.group(1).strip()
                    h2txt = m2_match.group(2).strip()
                    yield {'type': 'header', 'level': 3, 'text': f"{num2str} {h2txt}"}

                elif m_sub_match:
                    # （a）などの小項目はヘッダとして扱わず、通常のテキストとして出力するが、
                    # wordlinesをリセットする目的で上のロジックに追加した
                    yield {'type': 'text', 'text': line}
 
                # 用語例が現れた場合
                elif re.match(r'^\s*用語例', line):
                    if wordlines:
                        # 直前の用語例ブロックを処理（用語例が連続する場合など）
                        yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}
                        wordlines = []
                    # 次の行から用語をキャプチャ開始
                    wordlines.append(re.sub(r'^\s*用語例\s*', '', line).strip())

                # 分類見出しの出力 (Markdown では Lv1 扱い)
                elif m := re.match(r'大分類(\d+|[\uff10-\uff19]+)[:：](.+)\s+中分類(\d+|[\uff10-\uff19]+)[:：](.+)', line):
                    if wordlines:
                        yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}
                        wordlines = []

                    # 大分類名と中分類名を解析
                    # group(2)は大分類名、group(4)は中分類名
                    yield {'type': 'header', 'level': 1, 'text': f"中分類{m.group(3)} {m.group(4)}"}
                
                # 用語例キャプチャモード
                elif wordlines:
                    # HEADPATによる終了判定は弱いため、単純に空行または非見出し行をキャプチャし続ける
                    if not re.match(HEADPAT, line) and line.strip():
                        wordlines.append(line)
                    else:
                        # 用語例ブロックの終わり (HEADPATにマッチした場合)
                        yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}
                        wordlines = []
                        yield {'type': 'text', 'text': line} # 用語例の終わりだが、次の見出しにマッチしなかった行

                # それ以外のテキスト
                else:
                    yield {'type': 'text', 'text': line}

            # ファイルの最後に用語が残っている場合に出力処理
            if wordlines:
                yield {'type': 'word_block', 'h1': h1txt, 'h2': h2txt, 'words': listup_wordlines(wordlines)}

    except FileNotFoundError:
        # ここで処理を中断し、メインでエラーメッセージを表示
        raise

# ----------------------------------------
# 出力整形ロジック (すべてここに集約)

def format_prompt(h1txt: str, h2txt: str, words: List[str], ask_txt: str, out: TextIO):
    """AIプロンプト形式で出力する"""
    midashi_text = ""
    if h1txt and h2txt:
        midashi_text = f"「{h1txt}」における「{h2txt}」"
    elif h1txt:
        midashi_text = f"「{h1txt}」"
    elif h2txt:
        midashi_text = f"「{h2txt}」"
    
    print(f"", file=out)
    print(f"_ask\n応用情報処理試験の出題範囲{midashi_text}について、\n{ask_txt}", file=out)
    for word in words:
        print(word, file=out)
    print(file=out)


def output_results(results_generator: Generator[dict, None, None], ask_txt: str, out: TextIO, use_md: bool):
    """
    解析結果を受け取り、RUNMODEとuse_mdに基づいて整形して出力する
    """
    global RUNMODE

    if RUNMODE == "dict":
        # DICTモードではメインブロックで処理済みのため、ここはスキップ
        return

    for block in results_generator:
        b_type = block['type']

        if b_type == 'header':
            text = block['text'].strip()
            if RUNMODE == "normal":
                if use_md:
                    prefix = "#" * block['level'] + " "
                    print(f"\n{prefix}{text}", file=out)
                else:
                    print(f"\n{text}", file=out)

        elif b_type == 'text':
            if RUNMODE == "normal":
                print(block['text'].strip(), file=out)

        elif b_type == 'word_block':
            words = block['words']
            if not words:
                continue

            if RUNMODE == "ask":
                # ASKモード: AIプロンプトのみを出力
                format_prompt(block['h1'], block['h2'], words, ask_txt, out)
            
            elif RUNMODE == "normal":
                # NORMALモード: 用語リストとAIプロンプトを出力
                print(f"\n用語例: {', '.join(words)}", file=out)
                format_prompt(block['h1'], block['h2'], words, ask_txt, out)


# ----------------------------------------

def handle_output(args: argparse.Namespace, ask_txt: str, results_generator: Generator[dict, None, None]):
    """
    出力モードとファイル指定に応じて、結果をファイルまたは標準出力に出力する。
    """
    global DICTIONARY, RUNMODE
    
    # .md 拡張子の判定
    use_md = args.output_file and Path(args.output_file).suffix.lower() in (".md", ".markdown")

    if args.output_file:
        try:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                if RUNMODE == "dict":
                    # DICTモード: メインブロックで既にジェネレータは消費済み
                    print("\n".join(DICTIONARY), file=f)
                else:
                    # normal/askモード: ここでジェネレータを消費しつつ出力
                    output_results(results_generator, ask_txt, f, use_md)
        except Exception as e:
            print(f"Error: 出力ファイル '{args.output_file}' への書き込みに失敗しました。詳細: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 標準出力へ出力
        if RUNMODE == "dict":
            # DICTモード: メインブロックで既にジェネレータは消費済み
            print("\n".join(DICTIONARY), file=sys.stdout)
        else:
            # normal/askモード: ここでジェネレータを消費しつつ出力
            output_results(results_generator, ask_txt, sys.stdout, use_md)


def print_usage():
    msg = f"""
ap_words.py - 応用情報技術者試験のシラバスから用語を抜き出しプロンプト文を作成する

使用例
    python ap_words.py syllabus.txt -a 99 -o 応用情報用語.md

書式
    ap_words.py [-h] [-a ASK_PROMPT] [-o OUTPUT_FILE] [mode] filename_syllabus

位置引数:
  filename_syllabus  IPAシラバスの全選択コピペしたテキスト。省略不可。

オプション:
  -h, --help    ヘルプメッセージを表示して終了します
  -a, --ask [段落番号|ファイル名]
    <ファイル名>: プロンプトテキストのファイル名を指定します。
    <段落番号>: 使用するテキストの段落番号（1〜）を指定します。
                複数指定する場合はカンマ区切りで入力します。
                存在しない段落番号が含まれていると起動後に選択画面となります。
  -o, --output OUTPUT_FILE
    結果を出力するファイル名を指定します。指定しない場合は標準出力に出力します。
    ☀️拡張子が .md である場合、マークダウン記法での出力となります。

コマンド:
  normal (default) 通常処理。用語解説依頼テキスト以外の情報も出力します。
  ask              用語解説依頼テキストのみを出力します。
  dict             用語リストのみを出力します。

"""
    print(clean_text(msg))

# ----------------------------------------

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

    # 1. 起動時のエラーチェックとヘルプ表示
    if args.help:
        print_usage()
        sys.exit(0)

    if not args.filename_syllabus:
        print("読み込むシラバステキストのファイル名が指定されていません。", file=sys.stderr)
        print_usage()
        sys.exit(1)

    RUNMODE = args.mode

    # 2. プロンプト文の準備
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
    
    # 3. シラバスの解析（ジェネレータの取得）
    try:
        results = parse_syllabus(args.filename_syllabus)
    except FileNotFoundError:
        sys.exit(1)
        
    # 4. DICTモードの処理: グローバル辞書を完成させるためにジェネレータを消費する
    if RUNMODE == "dict":
        # parse_syllabus内でグローバルDICTIONARYに用語を格納するため、ここでジェネレータを消費
        list(results) 

    # 5. 出力処理を専用関数に委譲
    handle_output(args, ask_txt, results)
