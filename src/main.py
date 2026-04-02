"""
エントリーポイント (V2)

旧ボットとの互換性を維持するため、同じパス(src/main.py)にエントリーポイントを配置。
VPSのsystemdサービスから `python src/main.py` で起動される想定。
"""
import asyncio
import logging
import logging.handlers
import sys
from pathlib import Path

from src.config import load_config
from src.execution_controller import ExecutionController


def setup_logging(level: str = "INFO", data_dir: str = "data"):
    """ログ設定（コンソール + ファイル）"""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_path = Path(data_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.TimedRotatingFileHandler(
                str(log_path / "bot.log"),
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            ),
        ],
    )


def main():
    config = load_config()
    setup_logging(config.log_level, str(config.data_dir))

    logger = logging.getLogger(__name__)
    logger.info("Setting up Scalping Bot V2...")

    controller = ExecutionController(config)

    async def _run():
        await controller.initialize()
        await controller.run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Ctrl+C で停止")
    finally:
        logger.info("プロセス終了")


if __name__ == "__main__":
    main()
