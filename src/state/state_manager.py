"""
状態管理モジュール
state.json をSSoT (Single Source of Truth) として管理
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StateManager:
    """アプリケーション状態の管理"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.state_file = data_dir / "state.json"
        self.trades_dir = data_dir / "trades"
        self.events_dir = data_dir / "events"

        # ディレクトリ作成
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trades_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        # 初期状態をロードまたは作成
        self._state = self._load_or_create()

    def _load_or_create(self) -> dict:
        """状態ファイルを読み込み、なければ初期状態を作成"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.info(f"状態ファイル読み込み: {self.state_file}")
                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"状態ファイル読み込みエラー: {e} - 初期化します")

        return self._default_state()

    def _default_state(self) -> dict:
        """デフォルトの初期状態"""
        return {
            'position': {
                'side': 'flat',
                'entry_price': 0,
                'size': 0,
                'stop_loss': 0,
                'take_profit': 0,
                'order_id': '',
                'entry_time': 0,
            },
            'daily': {
                'pnl': 0.0,
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'date': self._today_str(),
            },
            'stats': {
                'total_trades': 0,
                'total_pnl': 0.0,
                'consecutive_losses': 0,
                'ai_calls': 0,
                'guardrail_blocks': 0,
            },
            'last_updated': time.time(),
        }

    def _save(self):
        """状態をファイルに保存"""
        self._state['last_updated'] = time.time()
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"状態ファイル書き込みエラー: {e}")

    def get_state(self) -> dict:
        """現在の状態を返す"""
        return self._state.copy()

    def update_position(self, side: str, entry_price: float,
                        size: float, stop_loss: float,
                        take_profit: float, order_id: str):
        """ポジション情報を更新"""
        self._state['position'] = {
            'side': side,
            'entry_price': entry_price,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'order_id': order_id,
            'entry_time': time.time(),
        }
        self._save()
        logger.info(f"ポジション更新: {side} {size} @ {entry_price}")

    def clear_position(self):
        """ポジション情報をクリア"""
        self._state['position'] = {
            'side': 'flat',
            'entry_price': 0,
            'size': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'order_id': '',
            'entry_time': 0,
        }
        self._save()
        logger.info("ポジションクリア")

    def update_daily_pnl(self, pnl: float):
        """日次PnLを更新"""
        today = self._today_str()

        # 日付が変わったらリセット
        if self._state['daily']['date'] != today:
            self._state['daily'] = {
                'pnl': 0.0,
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'date': today,
            }

        self._state['daily']['pnl'] += pnl
        self._state['daily']['trades'] += 1
        if pnl >= 0:
            self._state['daily']['wins'] += 1
        else:
            self._state['daily']['losses'] += 1

        self._state['stats']['total_trades'] += 1
        self._state['stats']['total_pnl'] += pnl

        self._save()

    def increment_ai_calls(self):
        """AI呼び出しカウントを更新"""
        self._state['stats']['ai_calls'] += 1
        self._save()

    def increment_guardrail_blocks(self):
        """ガードレールブロックカウントを更新"""
        self._state['stats']['guardrail_blocks'] += 1
        self._save()

    def record_trade_event(self, event: dict):
        """トレードイベントをJSONLファイルに記録"""
        today = self._today_str()
        event_file = self.events_dir / f"{today}.jsonl"

        try:
            with open(event_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except IOError as e:
            logger.error(f"イベント記録エラー: {e}")

    def has_position(self) -> bool:
        """ポジション保有中か"""
        return self._state['position']['side'] != 'flat'

    def get_position_info(self) -> dict:
        """ポジション情報を返す"""
        return self._state['position'].copy()

    def _today_str(self) -> str:
        """今日の日付文字列"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
