from datetime import datetime

import pytest

from telegram_bot.utils.tools import format_price_message, symbol_complete


def test_symbol_complete_no_usdt():
    assert symbol_complete("BTC") == "BTC/USDT"


def test_symbol_complete_with_usdt():
    assert symbol_complete("ETH/USDT") == "ETH/USDT"


def test_symbol_complete_lowercase():
    assert symbol_complete("ada") == "ADA/USDT"


def test_symbol_complete_mixed_case():
    assert symbol_complete("Xrp/UsdT") == "XRP/USDT"


def test_format_price_message_basic():
    data = {
        "symbol": "BTC/USDT",
        "timestamp": 1678886400000,  # 2023-03-15 12:00:00 UTC
        "current_price": 50000.12345,
        "low_24h": 48000.5,
        "high_24h": 51000.75,
        "volume": 1000000000.50,
        "timeframe_changes": {
            "5m": {"pct_change": 0.5},
            "15m": {"pct_change": -1.2},
            "1h": {"pct_change": 2.5},
            "4h": {"pct_change": 5.0},
            "1d": {"pct_change": -4.0},
        },
        "bid": 49999.0,
        "ask": 50001.0,
    }
    expected_message = (
        "💰 BTC/USDT Price Information\n"
        "📅 2023-03-15 20:20:00 UTC\n\n"
        "Current Price: $50,000.1234\n"
        "24h Range: $48,000.5000 - $51,000.7500\n"
        "24h Volume: $1,000,000,000.50\n\n"
        "⏱ Price Changes:\n"
        " 5m: +0.50% 🟢\n"
        "15m: -1.20% 🔴\n"
        " 1h: +2.50% 🟢\n"
        " 4h: +5.00% 🚀\n"
        " 1d: -4.00% 💥\n\n"
        "📊 Spread: $2.00 (0.004%)"
    )
    # Normalize line endings and spacing for comparison
    actual_message = format_price_message(data).replace("\r\n", "\n").strip()
    expected_message = expected_message.replace("\r\n", "\n").strip()
    assert actual_message == expected_message


def test_format_price_message_missing_spread():
    data = {
        "symbol": "ETH/USDT",
        "timestamp": 1678886400000,
        "current_price": 3000.0,
        "low_24h": 2900.0,
        "high_24h": 3100.0,
        "volume": 500000000.0,
        "timeframe_changes": {"1h": {"pct_change": 1.0}},
        # Missing bid/ask
    }
    expected_message = (
        "💰 ETH/USDT Price Information\n"
        "📅 2023-03-15 20:20:00 UTC\n\n"
        "Current Price: $3,000.0000\n"
        "24h Range: $2,900.0000 - $3,100.0000\n"
        "24h Volume: $500,000,000.00\n\n"
        "⏱ Price Changes:\n"
        " 1h: +1.00% 🟢"  # No spread info
    )
    actual_message = format_price_message(data).replace("\r\n", "\n").strip()
    expected_message = expected_message.replace("\r\n", "\n").strip()
    assert actual_message == expected_message


def test_format_price_message_missing_timeframes():
    data = {
        "symbol": "LTC/USDT",
        "timestamp": 1678886400000,
        "current_price": 150.0,
        "low_24h": 140.0,
        "high_24h": 160.0,
        "volume": 100000000.0,
        "timeframe_changes": {},  # Empty timeframe changes
        "bid": 149.9,
        "ask": 150.1,
    }
    expected_message = (
        "💰 LTC/USDT Price Information\n"
        "📅 2023-03-15 20:20:00 UTC\n\n"
        "Current Price: $150.0000\n"
        "24h Range: $140.0000 - $160.0000\n"
        "24h Volume: $100,000,000.00\n\n"
        "⏱ Price Changes:\n\n"  # Only header for changes
        "📊 Spread: $0.20 (0.133%)"
    )
    actual_message = format_price_message(data).replace("\r\n", "\n").strip()
    expected_message = expected_message.replace("\r\n", "\n").strip()
    assert actual_message == expected_message


# Example of testing the time_it decorator (Optional, requires a helper function)
# from telegram_bot.utils.tools import time_it
# import time

# @time_it
# def dummy_function(duration):
#     time.sleep(duration)
#     return "done"

# def test_time_it_decorator(capsys):
#     result = dummy_function(0.1)
#     captured = capsys.readouterr()
#     assert result == "done"
#     assert "Function dummy_function" in captured.out
#     assert "Took" in captured.out
#     assert "seconds" in captured.out
