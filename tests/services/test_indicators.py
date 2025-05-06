import pytest
import pandas as pd
import numpy as np
from src.services.indicators import (
    calculate_macd,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_obv,
    calculate_stoch,
    calculate_mfi,
    quant_agent,
    format_indicator_message,
)


# Sample DataFrame for testing
@pytest.fixture
def sample_prices_df():
    data = {
        "timestamp": pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
                "2023-01-06",
                "2023-01-07",
                "2023-01-08",
                "2023-01-09",
                "2023-01-10",
                "2023-01-11",
                "2023-01-12",
                "2023-01-13",
                "2023-01-14",
                "2023-01-15",
                "2023-01-16",
                "2023-01-17",
                "2023-01-18",
                "2023-01-19",
                "2023-01-20",
                "2023-01-21",
                "2023-01-22",
                "2023-01-23",
                "2023-01-24",
                "2023-01-25",
                "2023-01-26",
                "2023-01-27",
                "2023-01-28",
                "2023-01-29",
                "2023-01-30",
            ]
        ),
        "open": np.random.rand(30) * 100 + 1000,
        "high": np.random.rand(30) * 10 + 1100,
        "low": 1000 - np.random.rand(30) * 10,
        "close": np.random.rand(30) * 100 + 1000,
        "volume": np.random.rand(30) * 10000 + 50000,
    }
    df = pd.DataFrame(data)
    df.set_index("timestamp", inplace=True)
    # Ensure enough data for calculations like MACD(12, 26)
    min_required = 26 + 9  # Common requirement for MACD signal line
    if len(df) < min_required:
        # Extend df if needed, simple forward fill for example
        additional_data = pd.DataFrame(
            index=pd.date_range(
                start=df.index[-1] + pd.Timedelta(days=1),
                periods=min_required - len(df),
                freq="D",
            )
        )
        df = pd.concat([df, additional_data]).ffill()

    # Add more data points if needed for specific indicators
    # For RSI(14), need at least 15 data points
    # For MFI(14), need at least 15 data points
    # For STOCH(14, 3, 3), need at least 14 + 3 + 3 = 20 points approx.
    # Ensure the sample data meets the minimum length requirements for all indicators used.
    # Let's ensure we have at least 35 points for safety margin with various lookbacks and smoothing.
    min_required = 35
    if len(df) < min_required:
        additional_data = pd.DataFrame(
            index=pd.date_range(
                start=df.index[-1] + pd.Timedelta(days=1),
                periods=min_required - len(df),
                freq="D",
            )
        )
        df = pd.concat([df, additional_data]).ffill()

    # Recalculate high/low based on close/open after ffill if necessary
    df["high"] = df[["open", "close"]].max(axis=1) + np.random.rand(len(df)) * 5
    df["low"] = df[["open", "close"]].min(axis=1) - np.random.rand(len(df)) * 5

    return df


def test_calculate_macd(sample_prices_df):
    macd_line, signal_line = calculate_macd(sample_prices_df)
    assert isinstance(macd_line, pd.Series)
    assert isinstance(signal_line, pd.Series)
    assert not macd_line.isnull().all()  # Check that it's not all NaN
    assert not signal_line.isnull().all()
    assert len(macd_line) == len(sample_prices_df)


def test_calculate_rsi(sample_prices_df):
    rsi = calculate_rsi(sample_prices_df)
    assert isinstance(rsi, pd.Series)
    assert not rsi.isnull().all()
    assert len(rsi) == len(sample_prices_df)
    assert rsi.min() >= 0
    assert rsi.max() <= 100


def test_calculate_bollinger_bands(sample_prices_df):
    upper_band, lower_band = calculate_bollinger_bands(sample_prices_df)
    assert isinstance(upper_band, pd.Series)
    assert isinstance(lower_band, pd.Series)
    assert not upper_band.isnull().all()
    assert not lower_band.isnull().all()
    assert len(upper_band) == len(sample_prices_df)
    assert len(lower_band) == len(sample_prices_df)

    # Drop the nan values for comparison
    upper_band = upper_band.dropna()
    lower_band = lower_band.dropna()
    assert len(upper_band) == len(lower_band)

    assert (upper_band >= lower_band).all()  # Upper band should always be >= lower band


def test_calculate_obv(sample_prices_df):
    obv = calculate_obv(sample_prices_df)
    assert isinstance(obv, pd.Series)
    assert not obv.isnull().all()
    assert len(obv) == len(sample_prices_df)


def test_calculate_stoch(sample_prices_df):
    stoch = calculate_stoch(sample_prices_df)
    assert isinstance(stoch, pd.Series)
    assert not stoch.isnull().all()
    assert len(stoch) == len(sample_prices_df)
    assert stoch.min() >= 0
    assert stoch.max() <= 100


def test_calculate_mfi(sample_prices_df):
    mfi = calculate_mfi(sample_prices_df)
    assert isinstance(mfi, pd.Series)
    assert not mfi.isnull().all()
    assert len(mfi) == len(sample_prices_df)
    assert mfi.min() >= 0
    assert mfi.max() <= 100


# @pytest.mark.asyncio
# async def test_quant_agent(sample_prices_df):
#     # Ensure the DataFrame has enough data points after indicator calculations might drop initial NaNs
#     # quant_agent uses the last value [-1], so ensure calculations don't make the last value NaN
#     # Rerun calculations inside test if needed or ensure fixture provides sufficient valid trailing data
#     macd_line, signal_line = calculate_macd(sample_prices_df)
#     rsi = calculate_rsi(sample_prices_df)
#     upper_band, lower_band = calculate_bollinger_bands(sample_prices_df)
#     obv = calculate_obv(sample_prices_df)
#     stoch = calculate_stoch(sample_prices_df)
#     mfi = calculate_mfi(sample_prices_df)
#
#     # Check if the last values are valid before passing to quant_agent
#     required_indicators = [
#         macd_line,
#         signal_line,
#         rsi,
#         upper_band,
#         lower_band,
#         obv,
#         stoch,
#         mfi,
#     ]
#     if any(ind.iloc[-1:].isnull().any() for ind in required_indicators):
#         pytest.skip(
#             "Insufficient data or leading NaNs affect the final indicator values needed for quant_agent test."
#         )
#
#     message_body, overall_signal, confidence, reasoning = await quant_agent(
#         sample_prices_df
#     )
#
#     assert isinstance(message_body, list)
#     assert isinstance(overall_signal, str)
#     assert overall_signal in ["bullish", "bearish", "neutral"]
#     assert isinstance(confidence, float)
#     assert 0 <= confidence <= 1
#     assert isinstance(reasoning, dict)
#     assert len(reasoning) == 6  # MACD, RSI, Bollinger, OBV, STOCH, MFI
#     assert all(
#         key in reasoning for key in ["MACD", "RSI", "Bollinger", "OBV", "STOCH", "MFI"]
#     )
#     assert len(message_body) == len(reasoning)


def test_format_indicator_message():
    reasoning = {
        "MACD": {"signal": "bullish", "details": "Line crossed above Signal Line"},
        "RSI": {"signal": "neutral", "details": "45.67 (neutral)"},
        "Bollinger": {"signal": "bearish", "details": "above upper band"},
    }
    overall_signal = "neutral"
    confidence = 0.33
    price = 50000.12

    message = format_indicator_message(price, reasoning, overall_signal, confidence)

    assert isinstance(message, str)
    assert "💰 Price: $50,000.1200" in message
    assert "📊 Signal: ⚪ NEUTRAL" in message
    assert "🎯 Confidence: 33.0%" in message
    assert "MACD: Line crossed above Signal Line" in message
    assert "RSI(14): 45.67 (neutral)" in message
    assert "BBands: above upper band" in message
