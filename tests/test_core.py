"""
テクニカル指標のユニットテスト
"""
import pytest
from src.analysis.technical import TechnicalAnalyzer


def generate_mock_ohlcv(num_candles: int = 100,
                         base_price: float = 3500.0,
                         trend: str = "bullish") -> list:
    """テスト用のモックOHLCVデータを生成"""
    import time
    ohlcv = []
    price = base_price
    ts = int(time.time() * 1000) - num_candles * 60000

    for i in range(num_candles):
        if trend == "bullish":
            change = 0.5 + (i * 0.05)  # 徐々に上昇
        elif trend == "bearish":
            change = -0.5 - (i * 0.05)
        else:
            change = 0.5 if i % 2 == 0 else -0.5  # レンジ

        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + 1
        low_p = min(open_p, close_p) - 1
        volume = 100 + i

        ohlcv.append([ts + i * 60000, open_p, high_p, low_p, close_p, volume])
        price = close_p

    return ohlcv


class TestTechnicalAnalyzer:
    """TechnicalAnalyzerのテスト"""

    def test_calculate_all_bullish(self):
        """強気相場のテクニカル指標計算"""
        analyzer = TechnicalAnalyzer()
        ohlcv = generate_mock_ohlcv(100, trend="bullish")
        result = analyzer.calculate_all(ohlcv)

        assert result is not None
        assert result['market_structure'] in ("BULLISH", "RANGING", "BEARISH")
        assert 0 <= result['rsi'] <= 100
        assert result['atr'] >= 0
        assert result['price'] > 0

    def test_calculate_all_bearish(self):
        """弱気相場のテクニカル指標計算"""
        analyzer = TechnicalAnalyzer()
        ohlcv = generate_mock_ohlcv(100, trend="bearish")
        result = analyzer.calculate_all(ohlcv)

        assert result is not None
        assert 0 <= result['rsi'] <= 100

    def test_insufficient_data(self):
        """データ不足時にNoneを返す"""
        analyzer = TechnicalAnalyzer()
        ohlcv = generate_mock_ohlcv(10)  # 60本未満
        result = analyzer.calculate_all(ohlcv)

        assert result is None

    def test_rsi_range(self):
        """RSIが0〜100の範囲内"""
        analyzer = TechnicalAnalyzer()
        ohlcv = generate_mock_ohlcv(100)
        result = analyzer.calculate_all(ohlcv)

        assert result is not None
        assert 0 <= result['rsi'] <= 100

    def test_volatility_regimes(self):
        """ボラティリティレジーム判定"""
        analyzer = TechnicalAnalyzer()

        assert analyzer._determine_volatility_regime(0.3) == "NORMAL"
        assert analyzer._determine_volatility_regime(0.8) == "TREND"
        assert analyzer._determine_volatility_regime(2.0) == "HIGH_VOL"
        assert analyzer._determine_volatility_regime(5.0) == "EXTREME"

    def test_market_structure(self):
        """マーケット構造判定"""
        analyzer = TechnicalAnalyzer()

        assert analyzer._determine_market_structure(100, 90, 80) == "BULLISH"
        assert analyzer._determine_market_structure(80, 90, 100) == "BEARISH"
        assert analyzer._determine_market_structure(90, 100, 80) == "RANGING"

    def test_detect_events(self):
        """イベント検出"""
        analyzer = TechnicalAnalyzer()
        ohlcv = generate_mock_ohlcv(100)

        # 前回指標なし → イベントなし
        events = analyzer.detect_events(ohlcv, None)
        assert events == []


class TestGuardrail:
    """ガードレールのテスト"""

    def test_format_guard_low_confidence(self):
        """低Confidenceのブロック"""
        from src.trading.guardrail import FormatGuard
        from src.ai.gemini_client import TradingDecision
        from src.config import TradingConfig

        guard = FormatGuard(TradingConfig())
        decision = TradingDecision(
            action="ENTER_LONG",
            confidence=0.50,
            size=0.1,
            stop_loss_price=3400,
            take_profit_price=3700,
            rationale="test",
        )

        passed, reason = guard.check(decision, 3500)
        assert not passed
        assert "Confidence" in reason

    def test_format_guard_wrong_sl_direction(self):
        """SL方向エラーのブロック"""
        from src.trading.guardrail import FormatGuard
        from src.ai.gemini_client import TradingDecision
        from src.config import TradingConfig

        guard = FormatGuard(TradingConfig())
        # LONG なのにSLが現在価格より上
        decision = TradingDecision(
            action="ENTER_LONG",
            confidence=0.80,
            size=0.1,
            stop_loss_price=3600,  # 現在価格3500より上 → NG
            take_profit_price=3700,
            rationale="test",
        )

        passed, reason = guard.check(decision, 3500)
        assert not passed
        assert "SL方向" in reason

    def test_market_guard_high_spread(self):
        """高スプレッドのブロック"""
        from src.trading.guardrail import MarketGuard

        guard = MarketGuard()
        indicators = {'spread_pct': 0.50, 'volatility_regime': 'TREND', 'spread_atr_ratio': 0.1}
        passed, reason = guard.check(indicators)
        assert not passed
        assert "スプレッド" in reason

    def test_fund_guard_daily_loss(self):
        """日次損失上限のブロック"""
        from src.trading.guardrail import FundGuard
        from src.config import TradingConfig

        guard = FundGuard(TradingConfig(initial_capital=100))
        balance = {'total': 100, 'free': 50, 'used': 50}

        # 日次損失 -4R = -4 USDT (100 * 0.01 * 4)
        passed, reason = guard.check(balance, -5.0, 0, 100)
        assert not passed
        assert "日次損失上限" in reason


class TestRiskManager:
    """リスク管理のテスト"""

    def test_position_size_calculation(self):
        """ポジションサイズ計算"""
        from src.trading.risk_manager import RiskManager
        from src.config import TradingConfig

        rm = RiskManager(TradingConfig(
            initial_capital=100,
            risk_per_trade=0.01,
            leverage=2,
            max_position_size=0.5,
        ))

        size = rm.calculate_position_size(
            entry_price=3500,
            stop_loss_price=3400,
            capital=100,
            free_margin=50,
        )

        assert size > 0
        assert size <= 0.5  # 上限以下
        assert size >= 0.01  # 最小単位以上

    def test_trade_result_tracking(self):
        """トレード結果の追跡"""
        from src.trading.risk_manager import RiskManager
        from src.config import TradingConfig

        rm = RiskManager(TradingConfig())

        rm.record_trade_result(5.0)
        assert rm.daily_pnl == 5.0
        assert rm.consecutive_losses == 0

        rm.record_trade_result(-2.0)
        assert rm.daily_pnl == 3.0
        assert rm.consecutive_losses == 1

        rm.record_trade_result(-3.0)
        assert rm.consecutive_losses == 2

        rm.record_trade_result(1.0)
        assert rm.consecutive_losses == 0  # 勝ちでリセット
