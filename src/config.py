"""
設定管理モジュール (V2)
環境変数から設定を読み込み、dataclassで型安全に管理する。
旧ボットの複雑なConfig群を1つのAppConfigに統合。
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    """アプリケーション設定（全パラメータを1箇所に集約）"""

    # --- Bitget API ---
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""

    # --- Gemini API ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"

    # --- Trading ---
    symbol: str = "ETH/USDT:USDT"
    leverage: int = 5
    risk_per_trade: float = 0.01       # 1R = 口座残高の1%
    max_position_size: float = 0.1     # コイン枚数の絶対上限
    confidence_threshold: float = 0.65 # この値未満のconfidenceはスキップ
    rr_ratio: float = 2.0             # リスクリワード比 (TP = SL幅 × この値)
    atr_sl_multiplier: float = 1.5    # SL幅 = ATR × この値

    # --- Loop Intervals ---
    loop_interval_no_pos: int = 30    # ポジションなし時のループ間隔(秒)
    loop_interval_has_pos: int = 10   # ポジション保有中のループ間隔(秒)

    # --- Notification ---
    discord_webhook_url: str = ""

    # --- Logging ---
    log_level: str = "INFO"
    data_dir: Path = Path("data")


def load_config() -> AppConfig:
    """環境変数から設定を読み込む"""
    return AppConfig(
        # Bitget
        api_key=os.getenv("BITGET_API_KEY", ""),
        secret_key=os.getenv("BITGET_SECRET_KEY", ""),
        passphrase=os.getenv("BITGET_PASSPHRASE", ""),

        # Gemini
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),

        # Trading
        symbol=os.getenv("TRADING_SYMBOL", "ETH/USDT:USDT"),
        leverage=int(os.getenv("TRADING_LEVERAGE", "5")),
        risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
        max_position_size=float(os.getenv("MAX_POSITION_SIZE", "0.1")),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.65")),
        rr_ratio=float(os.getenv("RR_RATIO", "2.0")),
        atr_sl_multiplier=float(os.getenv("ATR_SL_MULTIPLIER", "1.5")),

        # Loop
        loop_interval_no_pos=int(os.getenv("LOOP_INTERVAL_NO_POS", "30")),
        loop_interval_has_pos=int(os.getenv("LOOP_INTERVAL_HAS_POS", "10")),

        # Notification
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),

        # Logging
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
    )
