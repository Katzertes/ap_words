import re
import sys

HEADPAT = r'^(?:[①-⑳]|[1-9][0-9]?|[１-９][０-９]?|➢|（|【)'

def preprocess_line(text):
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
    text = re.sub(pattern, "", text, flags=re.S) # flags=re.S ドット（.）は、改行文字を含むすべての文字にマッチ
    # ページ番号行を空行にする
    pattern = r"-\d{1,3}-"
    text = re.sub(pattern, "", text)

    return text.strip()


"""
wordlinesは、要素それぞれが文字列で、テキストである。基本的には最後に改行が入っているが、すべてを連結してから処理する。つまり、wordlinesの各要素を改行を取り除いた上で連結してから以下の処理を行う。
wordlinesの中身を1行ずつ処理して、単語を取り出し、yougo リストに追加する。
この、単語の取り出し方式としては、原則として全角の「、」「，」を区切り文字とするが、半角()や全角（）で囲まれた部分の中にある「、」「，」は区切り文字としない。
このようにして作られた yougo リストを戻り値とする。
"""
def listup_wordlines(wordlines):
    # すべての行を結合し、前後の空白と改行を削除
    full_text = "".join(line.strip() for line in wordlines)

    yougo = []
    current_word = ""
    in_parentheses = False

    # テキストを1文字ずつ処理
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
                # 抽出した単語をリストに追加
                yougo.append(current_word.strip())
            current_word = "" # 単語をリセット
        else:
            # カンマ以外の文字、または括弧内の文字を単語に連結
            current_word += char

    # 最後の単語をリストに追加
    if current_word:
        yougo.append(current_word.strip())

    return yougo    

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
                        print(f"> {line}")
                        mode = "search"
                    else:
                        wordlines.append(line)

                if mode == "search":
                    h1txt_prev = h1txt
                    h2txt_prev = h2txt
                    num1str_prev = num1str
                    num2str_prev = num2str
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
                        if not h1txt: h1txt = "No h1txt"
                        if not h2txt: h2txt = "No h2txt"
                        mode = "capture"
                        print("DEBUG: 用語例モードへ")
                        line = nextline_match.group(1).strip()  # 「用語例」以降の部分を取得
                        wordlines.append(line)  # 最初の行を追加

                    # 見出しの表示
                    if midashistr:
                        #  用語例の行がその前にあったのならそれを分解し、AI用プロンプトテキストとして出力する
                        if wordlines:
                            tango = listup_wordlines(wordlines)
                            print_output(h1txt_prev, h2txt_prev, tango)
                            wordlines = []
                        print(f"\n{midashistr}")
                        midashistr = ""
                    # 見出しでないのなら、そのまま表示
                    elif mode == "search":
                        print(f"> {line}")
                    else:
                        print(f"DEBUG: mode = {mode}")


            # ファイルの最後に用語が残っている場合に出力処理
            if wordlines:
                tango = listup_wordlines(wordlines)
                print_output(h1txt, h2txt, tango)

    except FileNotFoundError:
        print(f"ファイル '{filename}' が見つかりません。")
        sys.exit(1)

def print_output(h1txt, h2txt, tango):
    # print(f"[DEBUG] {h1txt} {h2txt}")
    midashi_text = ""
    if h1txt and h2txt:
        midashi_text = f"「{h1txt}」における「{h2txt}」"
    elif h1txt:
        midashi_text = f"「{h1txt}」"
    elif h2txt:
        midashi_text = f"「{h2txt}」"
    
    if h1txt:
        print(f"")
    print(f"""_ask
応用情報処理試験の出題範囲{midashi_text}について、
以下の用語に関する解説(基本的には400文字以内で、内容が複雑な場合は最大600文字、
意味が単純なら文字数に合わせず簡潔にまとめてもいい)を、表形式でまとめてください。
なお、文体は簡潔にするために、「だ・である」系や体言止めでお願いします。""")
    for word in tango:
        print(word)
    print()  # 行間を空ける

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("ファイル名が指定されていません。")
        print("使用方法: python ap_words.py <シラバスをテキスト化したファイル>")
        sys.exit(1)
        
    filename_to_process = sys.argv[1]
    process_text_file(filename_to_process)

    