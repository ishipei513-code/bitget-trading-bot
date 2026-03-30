#!/bin/bash
# GCP (Ubuntu) 上でのBitget Trading Botセットアップスクリプト

set -e # エラー発生時に即座に停止する

echo "======================================"
echo "  Bitget Trading Bot - Setup Script"
echo "======================================"

# 1. システムパッケージ更新
echo ">> [1/5] システムパッケージ更新と必要なソフトのインストール..."
sudo apt update -y
sudo apt install -y python3-venv python3-pip git

# 2. 仮想環境の作成
echo ">> [2/5] 仮想環境 (venv) を作成します..."
python3 -m venv venv
source venv/bin/activate

# 3. 依存ライブラリのインストール
echo ">> [3/5] 依存ライブラリ (requirements.txt) のインストール..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. .envテンプレートのコピー
echo ">> [4/5] 環境設定ファイルの準備..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env を作成しました。"
    echo "⚠️ セットアップ後、nano .env を実行して各種APIキーを入力してください。"
else
    echo ".env は既に存在します。"
fi

# 5. Systemd サービス登録ファイルの準備
echo ">> [5/5] systemdサービスファイルの準備..."
# スクリプトを実行しているユーザー名に置換
CURRENT_USER=$(whoami)
sed -i "s/__USER__/$CURRENT_USER/g" deploy/bitget-bot.service

echo ""
echo "======================================================"
echo "🎉 セットアップ前半が完了しました！"
echo ""
echo "▼ 次にやるべきこと（手動）"
echo "1. APIキーの設定:"
echo "   nano .env    # ファイルを開き、APIキーを追加する"
echo ""
echo "2. システム実行の登録（GCP再起動時に自動起動するため）:"
echo "   sudo cp deploy/bitget-bot.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable bitget-bot"
echo "   sudo systemctl start bitget-bot"
echo ""
echo "3. 動作ログの確認:"
echo "   journalctl -u bitget-bot -f"
echo "======================================================"
