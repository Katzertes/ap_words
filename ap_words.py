import re
import sys

def process_text_file(filename):
    """
    指定されたテキストファイルを読み込み、要件に従って処理を行う。
    """
    midashi1 = ""
    midashi2 = ""
    num1str = 0
    num2str = 0
    newmidashi1 = False
    tango = []
    mode = "discard"  # 'discard' (読み捨て) or 'capture' (用語取得)

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                if mode == "discard":
                    # 見出し1のパターンをチェック（例: (2) リスク分析と評価）
                    m1_match = re.match(r'^\s*[\(（](\d|[\uff10-\uff19]+)[\)）]\s*(.*)', line)
                    if m1_match:
                        num1str = m1_match.group(1).strip()
                        midashi1 = m1_match.group(2).strip()
                        midashi2 = ""
                        print(f"\n({num1str}) {midashi1}")
                        continue

                    # 見出し2のパターンをチェック（例: ① 情報資産の調査）
                    m2_match = re.match(r'^\s*([①-⑨])\s*(.*)', line)
                    if m2_match:
                        num2str = m2_match.group(1).strip()
                        midashi2 = m2_match.group(2).strip()
                        print(f"\n{num2str} {midashi2}")
                        continue

                    # 「用語例」という単語が行頭かつ、見出しが設定されていれば、用語取得モードへ

                    nextline_match = re.match(r'^\s*用語例(.*)', line)
                    if nextline_match and (midashi1 or midashi2):
                    # if "用語例" in line and (midashi1 or midashi2):
                        mode = "capture"
                        line = nextline_match.group(1).strip()  # 「用語例」以降の部分を取得
                        # print(f"[DEBUG] Switching to capture mode. Line after '用語例': '{line}'")
                    else:
                        print(f"{line}")  # 読み捨てモードでは行をそのまま出力

                if mode == "capture":
                    # 空行（改行のみもしくは空白文字の行）で用語出力処理を行い、読み捨てモードに戻る
                    if not line:
                        if tango:
                            print_output(midashi1, midashi2, tango)
                            tango = []
                        mode = "discard"
                        continue

                    # 「、」区切りで単語を取得
                    pattern = r'、(?![^((（)）]*\))'
                    words = [w.strip() for w in re.split(pattern, line) if w.strip() and w.strip() != '用語例']
                    # words = [w.strip() for w in line.split('、') if w.strip() and w.strip() != '用語例']
                    # words = [w.strip() for w in line.split('、') if w.strip()]
                    tango.extend(words)                    
    
            # ファイルの最後に用語が残っている場合に出力処理
            if mode == "capture" and tango:
                print_output(midashi1, midashi2, tango)

    except FileNotFoundError:
        print(f"エラー: ファイル '{filename}' が見つかりません。")
        sys.exit(1)

def print_output(midashi1, midashi2, tango):
    """
    指定されたフォーマットで出力を行う。
    """
    # print(f"[DEBUG] {midashi1} {midashi2}")
    midashi_text = ""
    if midashi1 and midashi2:
        midashi_text = f"「{midashi1}」における「{midashi2}」"
    elif midashi1:
        midashi_text = f"「{midashi1}」"
    elif midashi2:
        midashi_text = f"「{midashi2}」"
    
    if midashi1:
        print(f"")
    print(f"応用情報処理試験の出題範囲{midashi_text}について、以下の用語に関する解説(基本的には400文字以内で、内容が複雑な場合は最大600文字、意味が単純なら文字数に合わせず簡潔にまとめてもいい)を、表形式でまとめてください。なお、文体は簡潔にするために「で・ある」系でお願いします。")
    for word in tango:
        print(word)
    print()  # 空行を出力して見やすくする

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("エラー: ファイル名が指定されていません。")
        print("使用方法: python your_script.py <ファイル名>")
        sys.exit(1)
        
    filename_to_process = sys.argv[1]
    process_text_file(filename_to_process)

    