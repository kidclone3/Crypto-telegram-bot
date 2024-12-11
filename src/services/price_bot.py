import logging
from typing import Optional
import ccxt.async_support as ccxt
from ccxt.base.errors import BadSymbol
import asyncio
import pandas as pd
import io
import matplotlib.pyplot as plt
import mplfinance as mpf


class CryptoPriceBot:
    def __init__(self, exchange_ids: list[str] = ["binance", "okx"]):
        self.exchanges = [
            getattr(ccxt, exchange_id)(
                {
                    "enableRateLimit": True,
                }
            )
            for exchange_id in exchange_ids
        ]
        self.chart_style = self._create_chart_style()

    async def fetch_ohlcv_data(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> pd.DataFrame | None:
        """
        Fetch OHLCV data and convert to DataFrame for charting

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch

        Returns:
            pd.DataFrame | None: OHLCV data in DataFrame format or None if error
        """
        try:
            try:
                ohlcv = await self.exchanges[0].fetch_ohlcv(
                    symbol, timeframe, limit=limit
                )
            except BadSymbol as e:
                ohlcv = await self.exchanges[1].fetch_ohlcv(
                    symbol, timeframe, limit=limit
                )

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df

        except Exception as e:
            print(f"Error fetching OHLCV data for {symbol}: {str(e)}")
            return None

    async def fetch_future_ohlcv_data(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> pd.DataFrame | None:
        """
        Fetch OHLCV data for future and convert to DataFrame for charting

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch

        Returns:
            pd.DataFrame | None: OHLCV data in DataFrame format or None if error
        """
        try:
            try:
                ohlcv = await self.exchanges[0].fetch_ohlcv(
                    symbol + ":USDT", timeframe, limit=limit
                )
            except BadSymbol as e:
                ohlcv = await self.exchanges[1].fetch_ohlcv(
                    symbol + ":USDT", timeframe, limit=limit
                )

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df

        except Exception as e:
            print(f"Error fetching OHLCV data for {symbol}: {str(e)}")
            return None

    def _create_chart_style(self) -> dict:
        """Create and return the MPLFinance style configuration"""
        return mpf.make_mpf_style(
            base_mpf_style="charles",  # base style
            marketcolors={
                "candle": {"up": "#17a488", "down": "#ff4d4d"},
                "edge": {"up": "#17a488", "down": "#ff4d4d"},
                "wick": {"up": "#17a488", "down": "#ff4d4d"},
                "ohlc": {"up": "#17a488", "down": "#ff4d4d"},
                "volume": {"up": "#17a488", "down": "#ff4d4d"},
                "vcedge": {"up": "#17a488", "down": "#ff4d4d"},
                "vcdopcod": False,
                "alpha": 0.9,
            },
            gridstyle="",
            y_on_right=True,
            rc={
                "figure.facecolor": "white",
                "axes.facecolor": "white",
                "axes.edgecolor": "black",
                "axes.grid": True,
                "axes.grid.axis": "y",
                "grid.linewidth": 0.4,
                "grid.color": "#a0a0a0",
            },
            figcolor="white",
        )

    async def generate_chart(
        self, df, symbol: str, timeframe: str, figsize: tuple = (12, 8), dpi: int = 200
    ) -> Optional[io.BytesIO]:
        """
        Generate a candlestick chart with volume.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading pair symbol
            timeframe: Chart timeframe
            figsize: Figure size tuple (width, height)
            dpi: DPI for the output image

        Returns:
            BytesIO buffer containing the chart image or None if error occurs
        """
        buf = None
        fig = None

        try:
            # Validate input data
            if df is None or df.empty:
                raise ValueError("Empty or invalid DataFrame provided")

            # Create buffer for the image
            buf = io.BytesIO()

            # Create chart
            fig, axlist = mpf.plot(
                df,
                type="candle",
                title=f"{symbol} {timeframe} Chart",
                volume=True,
                style=self.chart_style,
                returnfig=True,
                figsize=figsize,
                panel_ratios=(3, 1),
                tight_layout=True,
            )

            # Save to buffer with error handling
            try:
                fig.savefig(
                    buf,
                    format="png",
                    dpi=dpi,
                    bbox_inches="tight",
                    facecolor=self.chart_style["figcolor"],
                )
                buf.name = f"{symbol}_{timeframe}_chart.png"
                buf.seek(0)
                return buf
            except Exception as save_error:
                logging.error(f"Error saving chart: {str(save_error)}")
                return None

        except ValueError as ve:
            logging.error(f"Validation error: {str(ve)}")
            return None

        except Exception as e:
            logging.error(f"Error creating chart: {str(e)}")
            return None

        finally:
            # Cleanup
            if fig is not None:
                plt.close(fig)
            if buf is not None and buf.getbuffer().nbytes == 0:
                buf.close()

    async def fetch_timeframe_change(self, symbol: str, timeframe: str) -> dict | None:
        """Helper function to fetch price change for a specific timeframe"""
        try:
            try:
                ohlcv = await self.exchanges[0].fetch_ohlcv(symbol, timeframe, limit=2)
            except BadSymbol as e:
                ohlcv = await self.exchanges[1].fetch_ohlcv(symbol, timeframe, limit=2)
            if len(ohlcv) >= 2:
                prev_close = ohlcv[0][4]
                current_close = ohlcv[1][4]
                pct_change = ((current_close - prev_close) / prev_close) * 100
                return {
                    "timeframe": timeframe,
                    "prev_price": prev_close,
                    "current_price": current_close,
                    "pct_change": round(pct_change, 2),
                    "timestamp": ohlcv[1][0],
                }
            return None
        except Exception as e:
            print(f"Error fetching {timeframe} data for {symbol}: {str(e)}")
            return None

    async def fetch_latest_price(self, symbol: str) -> dict | None:
        """
        Fetch the latest price and price changes across multiple timeframes

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            dict | None: Dictionary containing latest price data and changes across timeframes
        """
        try:
            # Fetch current ticker data
            try:
                ticker = await self.exchanges[0].fetch_ticker(symbol)
            except BadSymbol as e:
                ticker = await self.exchanges[1].fetch_ticker(symbol)

            # Fetch price changes for different timeframes concurrently
            timeframes = ["5m", "15m", "1h", "4h", "1d"]
            tasks = [self.fetch_timeframe_change(symbol, tf) for tf in timeframes]
            timeframe_changes = await asyncio.gather(*tasks)

            # Create timeframe changes dictionary
            changes = {
                change["timeframe"]: {
                    "prev_price": change["prev_price"],
                    "current_price": change["current_price"],
                    "pct_change": change["pct_change"],
                    "timestamp": change["timestamp"],
                }
                for change in timeframe_changes
                if change
            }

            return {
                "symbol": symbol,
                "current_price": ticker["last"],
                "volume": ticker["quoteVolume"],
                "high_24h": ticker["high"],
                "low_24h": ticker["low"],
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "timestamp": ticker["timestamp"],
                "timeframe_changes": changes,
            }

        except Exception as e:
            print(f"Error fetching latest price for {symbol}: {str(e)}")
            return None

    async def fetch_price_changes(
        self, symbol: str, timeframe: str = "1h", threshold: float = 1.0
    ) -> dict | None:
        """
        Fetch and filter price changes based on a threshold

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTC/USDT')
            timeframe (str): Time interval (e.g., '1h', '4h', '1d')
            threshold (float): Minimum percentage change to report

        Returns:
            dict | None: Dictionary containing price change data or None if below threshold/error
        """
        try:
            data = await self.fetch_timeframe_change(symbol, timeframe)
            if data and abs(data["pct_change"]) >= threshold:
                data["symbol"] = symbol
                data["timeframe"] = timeframe
                data["threshold_met"] = True
                return data
            return None
        except Exception as e:
            print(f"Error fetching price changes for {symbol}: {str(e)}")
            return None

    async def close(self):
        """Close the exchange connection"""
        # await self.exchanges.close()
        for exchange in self.exchanges:
            await exchange.close()
