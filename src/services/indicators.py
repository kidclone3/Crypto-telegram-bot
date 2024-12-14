import json
import re
import ta
from tabulate import tabulate


def calculate_macd(prices_df):
    macd = ta.trend.MACD(prices_df["close"], 12, 26, 9)
    return macd.macd(), macd.macd_signal()


def calculate_rsi(prices_df, period=14):
    rsi = ta.momentum.RSIIndicator(prices_df["close"], period)
    return rsi.rsi()


def calculate_bollinger_bands(prices_df):
    bb = ta.volatility.BollingerBands(prices_df["close"])
    return bb.bollinger_hband(), bb.bollinger_lband()


def calculate_obv(prices_df):
    obv = ta.volume.OnBalanceVolumeIndicator(prices_df["close"], prices_df["volume"])
    return obv.on_balance_volume()


def calculate_stoch(prices_df):
    stoch = ta.momentum.StochasticOscillator(
        prices_df["high"], prices_df["low"], prices_df["close"]
    )
    return stoch.stoch()


def calculate_mfi(prices_df):
    mfi = ta.volume.MFIIndicator(
        prices_df["high"], prices_df["low"], prices_df["close"], prices_df["volume"], 14
    )
    return mfi.money_flow_index()


##### Quantitative Agent #####
async def quant_agent(prices_df):
    """Analyzes technical indicators and generates trading signals."""
    # Calculate indicators
    # 1. MACD (Moving Average Convergence Divergence)
    macd_line, signal_line = calculate_macd(prices_df)

    # 2. RSI (Relative Strength Index)
    rsi = calculate_rsi(prices_df)

    # 3. Bollinger Bands (Bollinger Bands)
    upper_band, lower_band = calculate_bollinger_bands(prices_df)

    # 4. OBV (On-Balance Volume)
    obv = calculate_obv(prices_df)

    # 5. Stochastic Oscillator
    stoch = calculate_stoch(prices_df)

    # 6. Money Flow Index
    mfi = calculate_mfi(prices_df)

    # Generate individual signals
    signals = []

    # MACD signal
    if (
        macd_line.iloc[-2] < signal_line.iloc[-2]
        and macd_line.iloc[-1] > signal_line.iloc[-1]
    ):
        signals.append("bullish")
    elif (
        macd_line.iloc[-2] > signal_line.iloc[-2]
        and macd_line.iloc[-1] < signal_line.iloc[-1]
    ):
        signals.append("bearish")
    else:
        signals.append("neutral")

    # RSI signal
    if rsi.iloc[-1] <= 30:
        signals.append("bullish")
    elif rsi.iloc[-1] >= 70:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # Bollinger Bands signal
    current_price = prices_df["close"].iloc[-1]
    if current_price < lower_band.iloc[-1]:
        signals.append("bullish")
    elif current_price > upper_band.iloc[-1]:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # OBV signal
    obv_slope = obv.diff().iloc[-5:].mean()
    if obv_slope > 0:
        signals.append("bullish")
    elif obv_slope < 0:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # STOCH signal
    if stoch.iloc[-1] <= 20:
        signals.append("bullish")
    elif stoch.iloc[-1] >= 80:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # MFI signal
    if mfi.iloc[-1] <= 20:
        signals.append("bullish")
    elif mfi.iloc[-1] >= 80:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # Add reasoning collection
    reasoning = {
        "MACD": {
            "signal": signals[0],
            "details": f"{'Line crossed above' if signals[0] == 'bullish' else 'Line crossed below' if signals[0] == 'bearish' else 'no cross'} Signal Line",
        },
        "RSI": {
            "signal": signals[1],
            "details": f"{rsi.iloc[-1]:.2f} ({'oversold' if signals[1] == 'bullish' else 'overbought' if signals[1] == 'bearish' else 'neutral'})",
        },
        "Bollinger": {
            "signal": signals[2],
            "details": f"{'below lower band' if signals[2] == 'bullish' else 'above upper band' if signals[2] == 'bearish' else 'within bands'}",
        },
        "OBV": {
            "signal": signals[3],
            "details": f"Slope: {obv_slope:.2f} ({signals[3]})",
        },
        "STOCH": {
            "signal": signals[4],
            "details": f"{stoch.iloc[-1]:.2f} ({signals[4]})",
        },
        "MFI": {
            "signal": signals[5],
            "details": f"{mfi.iloc[-1]:.2f} ({'oversold' if signals[5] == 'bullish' else 'overbought' if signals[5] == 'bearish' else 'neutral'})",
        },
    }

    # Determine overall signal
    bullish_signals = signals.count("bullish")
    bearish_signals = signals.count("bearish")

    if bullish_signals > bearish_signals:
        overall_signal = "bullish"
    elif bearish_signals > bullish_signals:
        overall_signal = "bearish"
    else:
        overall_signal = "neutral"

    # Calculate confidence level based on the proportion of indicators agreeing
    total_signals = len(signals)
    confidence = max(bullish_signals, bearish_signals) / total_signals

    message_body = []
    for key, value in reasoning.items():
        message_body.append((key, value["signal"], value["details"]))

    table = tabulate(
        message_body, headers=["Indicator", "Signal", "Details"], tablefmt="pretty"
    )
    message_content_string = (
        f"Overall Signal: {overall_signal.upper()}\n"
        f"Confidence: {confidence:.2%}\n\n"
        f"<pre>{table}</pre>"
    )
    return message_content_string
