"""
設定管理モジュール
環境変数から設定を読み込み、型安全に管理する
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


# .envファイルを読み込む
load_dotenv()


@dataclass
class BitgetConfig:
    """Bitget API設定"""
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""
    sandbox: bool = False  # True=テストネット


@dataclass
class GeminiConfig:
    """Gemini API設定"""
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    temperature: float = 0.1  # 低い温度で一貫性のある判断


@dataclass
class TradingConfig:
    """トレード設定"""
    symbol: str = "ETH/USDT:USDT"
    leverage: int = 2
    initial_capital: float = 100.0  # USDT
    risk_per_trade: float = 0.01   # 1%
    max_position_size: float = 0.5  # ETH
    max_daily_loss_r: int = 4       # 4R
    max_consecutive_losses: int = 10
    confidence_threshold: float = 0.70

    # テクニカル指標パラメータ
    ma_fast: int = 5
    ma_mid: int = 20
    ma_slow: int = 60
    rsi_period: int = 14
    atr_period: int = 14

    # AI呼び出し間隔（秒）
    trend_poll_interval: int = 120     # TREND相場: 2分
    normal_poll_interval: int = 600    # NORMAL相場: 10分

    # ポジション保持上限（分）
    max_hold_minutes: int = 120


@dataclass
class NotificationConfig:
    """通知設定"""
    channel: str = "console"  # console, discord, line
    discord_webhook_url: str = ""
    line_channel_access_token: str = ""
    line_user_id: str = ""


@dataclass
class AppConfig:
    """アプリケーション全体の設定"""
    bot_mode: str = "dry_run"  # dry_run or live
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path("data"))

    bitget: BitgetConfig = field(default_factory=BitgetConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)


def load_config() -> AppConfig:
    """環境変数から設定を読み込む"""
    config = AppConfig(
        bot_mode=os.getenv("BOT_MODE", "dry_run"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        data_dir=Path(os.getenv("DATA_DIR", "data")),

        bitget=BitgetConfig(
            api_key=os.getenv("BITGET_API_KEY", ""),
            secret_key=os.getenv("BITGET_SECRET_KEY", ""),
            passphrase=os.getenv("BITGET_PASSPHRASE", ""),
            sandbox=os.getenv("BITGET_SANDBOX", "false").lower() == "true",
        ),

        gemini=GeminiConfig(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        ),

        trading=TradingConfig(
            symbol=os.getenv("TRADING_SYMBOL", "ETH/USDT:USDT"),
            leverage=int(os.getenv("TRADING_LEVERAGE", "2")),
            initial_capital=float(os.getenv("INITIAL_CAPITAL", "100")),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "0.5")),
            max_daily_loss_r=int(os.getenv("MAX_DAILY_LOSS_R", "4")),
            max_consecutive_losses=int(os.getenv("MAX_CONSECUTIVE_LOSSES", "10")),
        ),

        notification=NotificationConfig(
            channel=os.getenv("NOTIFICATION_CHANNEL", "console"),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""),
            line_user_id=os.getenv("LINE_USER_ID", ""),
        ),
    )

    return config
