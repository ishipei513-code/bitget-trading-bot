"""
通知モジュール
トレードイベントを各チャネルに通知
"""
import json
import logging
from typing import Optional

from src.config import NotificationConfig

logger = logging.getLogger(__name__)


class Notifier:
    """通知送信"""

    def __init__(self, config: NotificationConfig):
        self.config = config

    def send_entry(self, message: str):
        """エントリー通知"""
        self._send(f"🟢 ENTRY\n{message}")

    def send_exit(self, message: str):
        """エグジット通知"""
        self._send(f"🔴 EXIT\n{message}")

    def send_error(self, message: str):
        """エラー通知"""
        self._send(f"⚠️ ERROR\n{message}")

    def send_info(self, message: str):
        """情報通知"""
        self._send(f"ℹ️ INFO\n{message}")

    def send_daily_summary(self, stats: dict):
        """日次サマリー通知"""
        msg = (
            f"📊 日次サマリー\n"
            f"PnL: {stats.get('daily_pnl', 0):+.2f} USDT\n"
            f"トレード数: {stats.get('total_trades', 0)}\n"
            f"勝率: {stats.get('win_rate', 0):.1f}%\n"
            f"連敗: {stats.get('consecutive_losses', 0)}\n"
            f"AI呼び出し: {stats.get('ai_calls', 0)}回\n"
            f"ガードレールブロック: {stats.get('guardrail_blocks', 0)}回"
        )
        self._send(msg)

    def _send(self, message: str):
        """チャネルに応じてメッセージを送信"""
        channel = self.config.channel

        if channel == "console":
            self._send_console(message)
        elif channel == "discord":
            self._send_discord(message)
        elif channel == "line":
            self._send_line(message)
        else:
            self._send_console(message)

    def _send_console(self, message: str):
        """コンソール出力"""
        logger.info(f"\n{'='*50}\n{message}\n{'='*50}")

    def _send_discord(self, message: str):
        """Discord Webhook送信"""
        if not self.config.discord_webhook_url:
            logger.warning("Discord Webhook URLが設定されていません")
            self._send_console(message)
            return

        try:
            import requests

            payload = {"content": message[:2000]}
            resp = requests.post(
                self.config.discord_webhook_url,
                json=payload,
                timeout=5
            )
            
            if resp.status_code not in (200, 204):
                logger.error(f"Discord送信エラー: {resp.status_code} {resp.text}")
                self._send_console(message)

        except Exception as e:
            logger.error(f"Discord送信エラー: {e}")
            self._send_console(message)

    def _send_line(self, message: str):
        """LINE Messaging API (Push Message) 送信"""
        if not self.config.line_channel_access_token or not self.config.line_user_id:
            logger.warning("LINE Token または User IDが設定されていません")
            self._send_console(message)
            return

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.config.line_channel_access_token}",
                "Content-Type": "application/json",
            }
            data = {
                "to": self.config.line_user_id,
                "messages": [{"type": "text", "text": message[:5000]}]
            }
            resp = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers=headers,
                json=data,
            )
            if resp.status_code != 200:
                logger.error(f"LINE送信エラー: {resp.status_code} {resp.text}")
                self._send_console(message)
        except Exception as e:
            logger.error(f"LINE送信エラー: {e}")
            self._send_console(message)
