from datetime import datetime
from functools import wraps
import time


def symbol_complete(symbol: str) -> str:
    """Complete the symbol with /USDT if not present"""
    result = symbol + "/USDT" if not symbol.endswith("/USDT") else symbol
    return result.upper()


def time_it(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(f"Function {func.__name__}{args} {kwargs} Took {total_time:.4f} seconds")
        return result

    return timeit_wrapper


def format_price_message(data: dict) -> str:
    """Format price data into a readable message with all timeframes"""

    def get_change_emoji(pct: float) -> str:
        if pct > 3:
            return "🚀"
        elif pct > 0:
            return "🟢"
        elif pct < -3:
            return "💥"
        else:
            return "🔴"

    # Header with current price and basic info
    message = (
        f"💰 {data['symbol']} Price Information\n"
        f"📅 {datetime.fromtimestamp(data['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"Current Price: ${data['current_price']:,.4f}\n"
        f"24h Range: ${data['low_24h']:,.4f} - ${data['high_24h']:,.4f}\n"
        f"24h Volume: ${data['volume']:,.2f}\n\n"
    )

    # Add timeframe changes section
    message += "⏱ Price Changes:\n"
    for tf in ["5m", "15m", "1h", "4h", "1d"]:
        if tf in data["timeframe_changes"]:
            tf_data = data["timeframe_changes"][tf]
            pct_change = tf_data["pct_change"]
            emoji = get_change_emoji(pct_change)
            message += f"{tf:>3}: {pct_change:+.2f}% {emoji}\n"

    if data.get("bid") and data.get("ask"):
        # Add spread information at the bottom
        spread = data["ask"] - data["bid"]
        spread_pct = (spread / data["current_price"]) * 100
        message += f"\n📊 Spread: ${spread:.2f} ({spread_pct:.3f}%)"

    return message
