#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 権限がないと言われた場合 chmod +x ap_words.py
"""
ap_words.py
This Python script is for Japanese national exams for IT engineers.
Version 0.02
Author: Junichiro Higuchi
Last updated: 2025-09-07

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

def print_usage():
    msg = """
    Usage: ap_words.py <command> <filename>
    <filename>: IPAシラバスを全選択コピペしたテキストファイル
    <command>:
        normal(default) : 通常の処理。「用語解説お願い」以外のテキストも出力する。
        ask : 用語解説お願いテキストのみを出力する。
        dict : 用語のみを出力する。
    """
    print(clean_text(msg))

def clean_text(text: str) -> str:
    return dedent(text).strip()

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

def process_text_file(filename):
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
                            print_ai_prompt(h1txt_prev, h2txt_prev, tango)
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
                print_ai_prompt(h1txt, h2txt, tango)

    except FileNotFoundError:
        print(f"ファイル '{filename}' が見つかりません。")
        sys.exit(1)

    except BrokenPipeError:
        sys.exit(0)

def print_ai_prompt(h1txt, h2txt, tango):
    if RUNMODE == "dict":
        return
    # print(f"[DEBUG] {h1txt} {h2txt}")
    midashi_text = ""
    if h1txt and h2txt:
        midashi_text = f"「{h1txt}」における「{h2txt}」"
    elif h1txt:
        midashi_text = f"「{h1txt}」"
    elif h2txt:
        midashi_text = f"「{h2txt}」"
    
    if h1txt:
        print(f"", file=sys.stdout)
    print(f"""_ask
応用情報処理試験の出題範囲{midashi_text}について、
以下の用語に関する解説(基本的には400文字以内で、内容が複雑な場合は最大600文字、
意味が単純なら文字数に合わせず簡潔にまとめてもいい)を、表形式でまとめてください。
なお、文体は簡潔にするために、「だ・である」系や体言止めでお願いします。""", file=sys.stdout)
    for word in tango:
        print(word, file=sys.stdout)
    print(file=sys.stdout)  # 行間を空ける

# ----------------------------------------------------------------
if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print_usage()
            sys.exit(1)

        # 引数解析部分
        for i, arg in enumerate(sys.argv[1:], 1):
            match arg:
                case 'help' | '--help' | '-h':
                    print_usage()
                    sys.exit(0)
                case 'dict':
                    RUNMODE = "dict"
                case 'ask':
                    RUNMODE = "ask"
                case 'normal':
                    RUNMODE = "normal"
                case _:
                    filename_syllabus = arg

        process_text_file(filename_syllabus)
        if RUNMODE == "dict":
            print("\n".join(DICTIONARY), file=sys.stdout)

    except FileNotFoundError:
        print(f"ファイル '{filename_syllabus}' が見つかりません。", file=sys.stderr)
        sys.exit(1)


    