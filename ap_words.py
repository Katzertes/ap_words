#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 権限がないと言われた場合 chmod +x ap_words.py
"""
ap_words.py
This Python script is for Japanese national exams for IT engineers.
Version 0.03
Author: Junichiro Higuchi
Last updated: 2025-09-12

概要:
IPA応用情報技術者試験シラバス(PDF)を全選択コビペしたテキストファイルから、
用語例を抽出し、AIに解説を依頼するためのプロンプトテキストを生成する。
テストしていないが FE などの、他のIPA試験シラバスでも使えると思われる。
----------------------------------------------------------------
"""

import re
import sys
from textwrap import dedent

# 用語例記述の段落が終了したと判断する行頭のパターン
HEADPAT = r'^[1-9]|[【➢（]|[①-⑳]|(?:[1-9][0-9])'
# r'^(?:[①-⑳]|[1-9][0-9]?|[１-９][０-９]?|➢|（|【)'

DICTIONARY = [] # 検出した用語のすべてを格納するグローバル変数
RUNMODE = "normal" # コマンド指定による全体的な動作モード
DEFAULT_ASK_FILE = "ap_words_asks.txt"

def clean_text(text: str) -> str:
    return dedent(text).strip()

def read_paragraphs(filename) -> list:
    """
    テキストファイルを読み込み、空行で区切られた段落をリストとして返す。
    エラー発生時は空のリストを返す。
    使用例
    file_path = 'sample.txt'
    result_paragraphs = read_paragraphs(file_path)
    for i, p in enumerate(result_paragraphs, 1):
        print(f"--- 段落 {i} ---")
        print(p)
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

        # for txt in paragraphs:
        #     print(txt,"\n",file=sys.stderr)
        return paragraphs

    except FileNotFoundError:
        print(f"Error: ファイル '{filename}' が見つかりません。",file=sys.stderr)
        return []  # エラー時に空のリストを返す

    except Exception as e:
        print(f"Error: {e}",file=sys.stderr)
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
    if filename == "":
        return ask_default
    asks = read_paragraphs(filename)
    if not asks:
        return ask_default

    # 指定された番号の段落をプロンプト文に追加していく
    ask = ""
    for i, txt in enumerate(asks, start=1):
        if i in para_id:
            if ask == "":
                ask = txt + "\n"
            else:
                ask += "|\n" + txt + "\n"

    if ask == "":
        ask = ask_default
    return clean_text(ask)

def preprocess_line(text: str) -> str:
    """
    pdfからコピペしたシラバステキストの前処理を行います。
    Args:
        text (str): 編集する文字列。
    Returns:
        str: 編集後の文字列。
    """
    # 長い ... を置換
    text = re.sub(r"\.{3,}", "...", text)

    # Copyright行を削除
    pattern = r"^Copyright.*"

    # flags=re.S ドット（.）は、改行文字を含むすべての文字にマッチ
    text = re.sub(pattern, "", text, flags=re.S)

    # ページ番号行を空行にする
    pattern = r"-\d{1,3}-"
    text = re.sub(pattern, "", text)

    return text.strip()


def listup_wordlines(wordlines) -> list:
    """
    wordlinesは、要素それぞれが文字列で、テキストである。
    基本的には最後に改行が入っているが、すべてを連結してから処理する。
    つまり、wordlinesの各要素を改行を取り除いた上で連結してから以下の処理を行う。
    wordlinesの中身を1行ずつ処理して、単語を取り出し、yougo リストに追加する。
    この、単語の取り出し方式としては、原則として全角の「、」「，」を区切り文字とするが、
    半角()や全角（）で囲まれた部分の中にある「、」「，」は区切り文字としない。
    このようにして作られた yougo リストを戻り値とする。
    """
    global DICTIONARY

    # すべての行を結合し、前後の空白と改行を削除
    full_text = "".join(line.strip() for line in wordlines)

    yougo = [] # 用語例から抽出した用語
    current_word = "" # 現在処理中の単語
    in_parentheses = False

    # 結合したテキストを1文字ずつ処理
    for char in full_text:
        # 括弧の開始を判定
        if char == '(' or char == '（':
            in_parentheses = True
        # 括弧の終了を判定
        elif char == ')' or char == '）':
            in_parentheses = False
        
        # 括弧の外にあるカンマを検出
        if not in_parentheses and (char == '、' or char == '，'):
            if current_word:
                # 抽出した単語を用語、およびグローバル変数の辞書に追加
                insertword = current_word.strip()
                if insertword not in DICTIONARY:
                    DICTIONARY.append(insertword)
                yougo.append(insertword)
            current_word = "" # 単語をリセット
        else:
            # カンマ以外の文字、または括弧内の文字を単語に連結
            current_word += char

    # 最後の単語をリストに追加
    if current_word:
        yougo.append(current_word.strip())

    return yougo    

def print_line(text):
    """
    動作モードに応じて、テキストを出力する。
    """
    match RUNMODE:
        case "normal":
            print(text.strip(), file=sys.stdout)

def process_text_file(filename,ask_txt):
    h1txt = "" # 見出し1テキスト
    h2txt = "" # 見出し2テキスト
    num1str = 0 # 見出し1番号文字列
    num2str = 0 # 見出し2番号文字列
    tango = []
    mode = "search"
    wordlines = []
    midashistr = ""

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = preprocess_line(line)
                if not line: continue

                if mode == "capture":
                    if not line:
                        mode = "search"
                    elif re.match(HEADPAT, line):
                        print_line(f"{line}")
                        mode = "search"
                    else:
                        wordlines.append(line)

                if mode == "search":
                    h1txt_prev = h1txt
                    h2txt_prev = h2txt
                    # num1str_prev = num1str
                    # num2str_prev = num2str
                    # 見出し1のパターンをチェック（例: (2) リスク分析と評価）
                    if m1_match := re.match(r'^\s*[\(（](\d|[\uff10-\uff19]+)[\)）]\s*(.*)', line):
                        num1str = m1_match.group(1).strip()
                        h1txt = m1_match.group(2).strip()
                        h2txt = ""
                        midashistr = f"({num1str}) {h1txt}"

                    # 見出し2のパターンをチェック（例: ① 情報資産の調査）
                    elif m2_match := re.match(r'^\s*([①-⑳])\s*(.*)', line):
                        num2str = m2_match.group(1).strip()
                        h2txt = m2_match.group(2).strip()
                        midashistr = f"{num2str} {h2txt}"
                    
                    # 「用語例」という単語が行頭なら、用語取得モードへ
                    elif nextline_match := re.match(r'^\s*用語例(.*)', line):
                        mode = "capture"
                        # print("DEBUG: 用語例モードへ")
                        line = nextline_match.group(1).strip()  # 「用語例」以降の部分を取得
                        wordlines.append(line)  # 最初の行を追加

                    # 見出しの表示
                    if midashistr:
                        #  用語例の行があったのならそれを用語に分解し、AI用プロンプトテキストとして出力する
                        if wordlines:
                            tango = listup_wordlines(wordlines)
                            print_ai_prompt(h1txt_prev, h2txt_prev, tango, ask_txt)
                            wordlines = []
                        print_line(f"\n{midashistr}")
                        midashistr = ""
                    # 見出しでないのなら、そのまま表示
                    elif mode == "search":
                        print_line(f"{line}")
                    # else:
                        # print(f"DEBUG: mode = {mode}")


            # ファイルの最後に用語が残っている場合に出力処理
            if wordlines:
                tango = listup_wordlines(wordlines)
                print_ai_prompt(h1txt, h2txt, tango, ask_txt)

    except FileNotFoundError:
        print(f"ファイル '{filename}' が見つかりません。")
        sys.exit(1)

    except BrokenPipeError:
        sys.exit(0)

def print_ai_prompt(h1txt, h2txt, tango, ask_txt):
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
        print(f"", file=sys.stdout)
    print(f"_ask\n応用情報処理試験の出題範囲{midashi_text}について、\n{ask_txt}")
    for word in tango:
        print(word, file=sys.stdout)
    print(file=sys.stdout)  # 行間を空ける

# ----------------------------------------------------------------
def print_usage():
    msg = f"""
ap_words.py - 応用情報技術者試験のシラバスから用語を抜き出しプロンプト文を作成する
概要
    ap_words.py [コマンド] <ファイル名> [オプション]
コマンド
    normal 通常処理。用語解説依頼テキスト以外の情報も出力します。(default)
    ask    用語解説依頼テキストのみを出力します。
    dict   用語リストのみを出力します。
引数
    <ファイル名> IPAシラバスの全選択コピペしたテキスト。省略不可。
オプション
    -a, --ask <ファイル名 | 段落番号>
        <ファイル名> : プロンプトテキストのファイル名を指定します。
        <段落番号>       : 使用するテキストの段落番号（1〜）を指定します。複数指定可能
"""
    print(clean_text(msg))

if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print_usage()
            sys.exit(1)

        # 引数解析部分
        prompt_id = [] # 挿入するプロンブト文の段落。複数指定できるのでリストにしている。
        prompt_file = "" # プロンプト文のファイル

        i = 1
        while i < len(sys.argv):
            arg = sys.argv[i]
            match arg:
                case 'help' | '--help' | '-h':
                    print_usage()
                    sys.exit(0)
                case '-a'| '--ask':
                    if i + 1 < len(sys.argv):
                        arg_a = sys.argv[i + 1]
                        # 段落番号の場合
                        if arg_a.isdigit():
                            prompt_id.append(int(arg_a))
                            if prompt_file == "":
                                prompt_file = DEFAULT_ASK_FILE
                        # ファイル名の場合
                        else:
                            prompt_file = arg_a
                            if prompt_id == []:
                                prompt_id.append(1)
                        i += 1 # -a の次の引数も処理したものとして、インデックスを1つ進める
                    else:
                        print("Error: -a の後にファイル名か段落番号を指定してください。",file=sys.stderr)
                        sys.exit(1)
                case 'dict':
                    RUNMODE = "dict"
                case 'ask':
                    RUNMODE = "ask"
                case 'normal':
                    RUNMODE = "normal"
                case _:
                    filename_syllabus = arg
            i += 1

        # プロンプト文の読み込み
        ask_txt = get_ask_prompt(prompt_file, prompt_id)

        # メイン処理部分
        process_text_file(filename_syllabus, ask_txt)

        # 辞書モードなら、用語リストを出力
        if RUNMODE == "dict":
            print("\n".join(DICTIONARY), file=sys.stdout)

    except FileNotFoundError:
        print(f"ファイル '{filename_syllabus}' が見つかりません。", file=sys.stderr)
        sys.exit(1)




