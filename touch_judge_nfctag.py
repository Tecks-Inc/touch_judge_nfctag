import sys
import time
from smartcard.System import readers
from smartcard.CardConnection import CardConnection

def main():
    # 1. 利用可能なPC/SCカードリーダーのリストを取得
    available_readers = readers()
    
    # リーダーが接続されていない場合のガード
    if not available_readers or len(available_readers) == 0:
        print("【エラー】PC/SCカードリーダーが認識されていません。")
        print("         USBケーブルが正しく接続されているか確認してください。")
        sys.exit(1)

    # リストから「最初の1台」のリーダーオブジェクトを取得
    reader = available_readers[0]
    
    print(f"使用するリーダー: {reader}")
    print("--------------------------------------------------")
    print(" NFCタグ・ICカード（Suica、クレジットカード、マイナンバーカード等）をかざしてください。")
    print(" ※ スマートフォン（モバイルSuica等）には対応していません。")
    print(" ※ 終了するには [Ctrl + C] を押してください。")
    print("--------------------------------------------------\n")

    card_present_last_time = False

    try:
        # ループの外で接続オブジェクトを1つだけ生成（終了時のPCSCCardConnectionエラー対策）
        connection = reader.createConnection()

        while True:
            try:
                # 物理カードと通信するため、標準プロトコルで接続
                connection.connect(CardConnection.T0_protocol | CardConnection.T1_protocol)
                card_detected = True
            except Exception:
                card_detected = False

            # 【カードが置かれた瞬間の処理】
            if card_detected and not card_present_last_time:
                try:
                    # 1. ATRを取得して解析
                    atr = connection.getATR()
                    atr_hex = [f"{b:02X}" for b in atr]
                    atr_str = " ".join(atr_hex)
                    
                    # 2. 固有番号（UID/IDm）を取得する共通コマンド
                    apdu_get_uid = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                    response, sw1, sw2 = connection.transmit(apdu_get_uid)
                    
                    uid_str = "取得失敗"
                    if sw1 == 0x90 and sw2 == 0x00:
                        uid_hex = [f"{b:02X}" for b in response]
                        uid_str = "".join(uid_hex)

                    final_standard = "判別不能（未知のカード）"

                    # --- 物理カード専用 判定ロジック ---

                    # 高機能なクレジットカード（物理）が返す特殊なATRをType Aへ救済
                    if atr_str == "3B 80 80 01 01":
                        final_standard = "ISO/IEC 14443 Type A"

                    # パターン1: PC/SC標準の非接触ストレージ形式（通常のSuicaやMifare等）
                    elif len(atr_hex) >= 15 and atr_hex[7:12] == ["A0", "00", "00", "03", "06"]:
                        ss = atr_hex[12]
                        nn = f"{atr_hex[13]}{atr_hex[14]}"
                        
                        if ss == "03":
                            final_standard = "ISO/IEC 14443 Type A"
                        elif ss == "0B":
                            final_standard = "ISO/IEC 14443 Type B"
                        elif ss == "11":
                            final_standard = "FeliCa (ISO/IEC 18092 / Type F)"
                    
                    # パターン2: 生の高機能ICカード（国の公的カード等）
                    else:
                        if len(atr_hex) > 0 and (atr_hex[0] == "3B" or atr_hex[0] == "3F"):
                            final_standard = "ISO/IEC 14443 Type B"

                    # 3. 画面への最終出力
                    print("◆ カードを検知しました ◆")
                    print(f"  [ATR値]   : {atr_str}")
                    print(f"  [規格] : {final_standard}")
                    if final_standard.startswith("FeliCa"):
                        print(f"  [IDm番号] : {uid_str}")
                    else:
                        print(f"  [UID番号] : {uid_str}")
                    print("-" * 50)
                    
                except Exception as e:
                    print(f"【エラー】データ解析中に問題が発生しました: {e}\n")

                # カードの置きっぱなしによる連打をガード
                card_present_last_time = True

            # 【カードが離された時の処理】
            elif not card_detected and card_present_last_time:
                card_present_last_time = False
                # 切断して次のカード受付に備える
                try:
                    connection.disconnect()
                except Exception:
                    pass
                print("◆ カードが離れました。 ◆\n")

            # 0.1秒待機してループを回す
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n終了しました。")

if __name__ == "__main__":
    main()
