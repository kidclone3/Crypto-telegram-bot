import pytest
import pandas as pd
import io
from unittest.mock import AsyncMock, patch
from src.bot.price_bot import CryptoPriceBot


@pytest.fixture
def crypto_price_bot():
    bot = CryptoPriceBot()
    return bot


@pytest.fixture
def valid_dataframe():
    data = {
        "open": [100, 110, 105],
        "high": [115, 120, 110],
        "low": [95, 105, 100],
        "close": [110, 108, 104],
        "volume": [1000, 1500, 1200],
    }
    index = pd.date_range(start="2023-01-01", periods=3, freq="1H")
    return pd.DataFrame(data, index=index)


@pytest.mark.asyncio
async def test_generate_chart_with_valid_data(crypto_price_bot, valid_dataframe):
    with patch("src.bot.price_bot.viewable_signal") as mock_signal, patch(
            "src.bot.price_bot.apply_multi_kernel_regression"
    ) as mock_apply_regression:
        mock_apply_regression.return_value = valid_dataframe
        mock_signal.return_value = pd.DataFrame(
            {
                "signal_val_up": [None, 1, None],
                "signal_val_down": [None, None, -1],
            },
            index=valid_dataframe.index,
        )

        result = await crypto_price_bot.generate_chart(
            df=valid_dataframe,
            symbol="BTC/USDT",
            timeframe="1h",
            exchange="binance",
        )

        assert isinstance(result, io.BytesIO)
        assert result.name == "BTC/USDT_1h_chart.png"
        assert result.getbuffer().nbytes > 0


@pytest.mark.asyncio
async def test_generate_chart_with_empty_dataframe(crypto_price_bot):
    empty_df = pd.DataFrame()

    result = await crypto_price_bot.generate_chart(
        df=empty_df, symbol="BTC/USDT", timeframe="1h", exchange="binance"
    )

    assert result is None


@pytest.mark.asyncio
async def test_generate_chart_with_invalid_dataframe(crypto_price_bot):
    invalid_df = None

    result = await crypto_price_bot.generate_chart(
        df=invalid_df, symbol="BTC/USDT", timeframe="1h", exchange="binance"
    )

    assert result is None


@pytest.mark.asyncio
async def test_generate_chart_handles_save_error(crypto_price_bot, valid_dataframe):
    with patch("matplotlib.pyplot.Figure.savefig") as mock_savefig, patch(
            "src.bot.price_bot.viewable_signal"
    ) as mock_signal, patch("src.bot.price_bot.apply_multi_kernel_regression") as mock_apply_regression:
        mock_savefig.side_effect = Exception("Save error")
        mock_apply_regression.return_value = valid_dataframe
        mock_signal.return_value = pd.DataFrame(
            {
                "signal_val_up": [None, 1, None],
                "signal_val_down": [None, None, -1],
            },
            index=valid_dataframe.index,
        )

        result = await crypto_price_bot.generate_chart(
            df=valid_dataframe,
            symbol="BTC/USDT",
            timeframe="1h",
            exchange="binance",
        )

        assert result is None