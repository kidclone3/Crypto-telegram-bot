import numpy as np
import pandas as pd
from typing import Tuple


class PinbarDetector:
    """
    Pinbar Detector - detects Pinbar patterns on financial charts.
    Python implementation of the EarnForex.com Pinbar Detector.
    """

    def __init__(
        self,
        count_bars: int = 0,
        use_custom_settings: bool = False,
        custom_max_nose_body_size: float = 0.33,
        custom_nose_body_position: float = 0.4,
        custom_left_eye_opposite_direction: bool = True,
        custom_nose_same_direction: bool = False,
        custom_nose_body_inside_left_eye_body: bool = False,
        custom_left_eye_min_body_size: float = 0.1,
        custom_nose_protruding: float = 0.5,
        custom_nose_body_to_left_eye_body: float = 1.0,
        custom_nose_length_to_left_eye_length: float = 0.0,
        custom_left_eye_depth: float = 0.1,
        custom_minimum_nose_length: float = 1.0,
    ):
        """
        Initialize the Pinbar Detector with custom or default settings.

        Args:
            count_bars: Number of bars to analyze (0 = all bars)
            use_custom_settings: Whether to use custom settings
            custom_*: Various custom parameters for pinbar detection
        """
        self.count_bars = count_bars

        # Set parameters based on custom settings
        if use_custom_settings:
            self.max_nose_body_size = custom_max_nose_body_size
            self.nose_body_position = custom_nose_body_position
            self.left_eye_opposite_direction = custom_left_eye_opposite_direction
            self.nose_same_direction = custom_nose_same_direction
            self.nose_body_inside_left_eye_body = custom_nose_body_inside_left_eye_body
            self.left_eye_min_body_size = custom_left_eye_min_body_size
            self.nose_protruding = custom_nose_protruding
            self.nose_body_to_left_eye_body = custom_nose_body_to_left_eye_body
            self.nose_length_to_left_eye_length = custom_nose_length_to_left_eye_length
            self.left_eye_depth = custom_left_eye_depth
            self.minimum_nose_length = custom_minimum_nose_length
        else:
            # Default settings
            self.max_nose_body_size = 0.33
            self.nose_body_position = 0.4
            self.left_eye_opposite_direction = True
            self.nose_same_direction = False
            self.nose_body_inside_left_eye_body = False
            self.left_eye_min_body_size = 0.1
            self.nose_protruding = 0.5
            self.nose_body_to_left_eye_body = 1.0
            self.nose_length_to_left_eye_length = 0.0
            self.left_eye_depth = 0.1
            self.minimum_nose_length = 1.0

    def detect(self, df: pd.DataFrame) -> Tuple[list, list]:
        """
        Detect pinbar patterns in the provided OHLC data.

        Args:
            df: pandas DataFrame with columns 'open', 'high', 'low', 'close'

        Returns:
            Tuple of (signals, colors) where:
                signals: list of pinbar signals (None for no signal, price level for signal)
                colors: list of colors (0 for bullish, 1 for bearish)
        """
        if len(df) < 2:
            raise ValueError("Need at least 2 bars of data")

        # Convert DataFrame to numpy arrays for faster processing
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        # Initialize output arrays
        signals = [None] * len(df)
        colors = [None] * len(df)

        # Calculate number of bars to process
        bars_to_process = (
            len(df) if self.count_bars == 0 else min(self.count_bars, len(df))
        )

        # Main detection loop
        for i in range(1, bars_to_process):
            # Calculate bar parameters
            nose_length = highs[i] - lows[i]
            if nose_length < self.minimum_nose_length:
                continue

            left_eye_length = highs[i - 1] - lows[i - 1]
            nose_body = abs(opens[i] - closes[i])
            left_eye_body = abs(opens[i - 1] - closes[i - 1])

            # Check for bearish pinbar
            if self._is_bearish_pinbar(
                i,
                opens,
                highs,
                lows,
                closes,
                nose_length,
                left_eye_length,
                nose_body,
                left_eye_body,
            ):
                signals[i] = highs[i] + nose_length / 5
                colors[i] = 1

            # Check for bullish pinbar
            elif self._is_bullish_pinbar(
                i,
                opens,
                highs,
                lows,
                closes,
                nose_length,
                left_eye_length,
                nose_body,
                left_eye_body,
            ):
                signals[i] = lows[i] - nose_length / 5
                colors[i] = 0

        return signals, colors

    def _is_bearish_pinbar(
        self,
        i: int,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        nose_length: float,
        left_eye_length: float,
        nose_body: float,
        left_eye_body: float,
    ) -> bool:
        """Check if current bar is a bearish pinbar."""

        # Nose protrusion check
        if highs[i] - highs[i - 1] < nose_length * self.nose_protruding:
            return False

        # Body size check
        if nose_body / nose_length > self.max_nose_body_size:
            return False

        # Body position check
        if (
            1 - (highs[i] - max(opens[i], closes[i])) / nose_length
            >= self.nose_body_position
        ):
            return False

        # Left eye direction check
        if self.left_eye_opposite_direction and closes[i - 1] <= opens[i - 1]:
            return False

        # Nose direction check
        if self.nose_same_direction and closes[i] >= opens[i]:
            return False

        # Additional criteria checks
        if (
            left_eye_body / left_eye_length < self.left_eye_min_body_size
            or nose_body / left_eye_body > self.nose_body_to_left_eye_body
            or nose_length / left_eye_length < self.nose_length_to_left_eye_length
            or lows[i] - lows[i - 1] < left_eye_length * self.left_eye_depth
        ):
            return False

        # Nose body inside left eye body check
        if self.nose_body_inside_left_eye_body:
            if max(opens[i], closes[i]) > max(opens[i - 1], closes[i - 1]) or min(
                opens[i], closes[i]
            ) < min(opens[i - 1], closes[i - 1]):
                return False

        return True

    def _is_bullish_pinbar(
        self,
        i: int,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        nose_length: float,
        left_eye_length: float,
        nose_body: float,
        left_eye_body: float,
    ) -> bool:
        """Check if current bar is a bullish pinbar."""

        # Nose protrusion check
        if lows[i - 1] - lows[i] < nose_length * self.nose_protruding:
            return False

        # Body size check
        if nose_body / nose_length > self.max_nose_body_size:
            return False

        # Body position check
        if (
            1 - (min(opens[i], closes[i]) - lows[i]) / nose_length
            >= self.nose_body_position
        ):
            return False

        # Left eye direction check
        if self.left_eye_opposite_direction and closes[i - 1] >= opens[i - 1]:
            return False

        # Nose direction check
        if self.nose_same_direction and closes[i] <= opens[i]:
            return False

        # Additional criteria checks
        if (
            left_eye_body / left_eye_length < self.left_eye_min_body_size
            or nose_body / left_eye_body > self.nose_body_to_left_eye_body
            or nose_length / left_eye_length < self.nose_length_to_left_eye_length
            or highs[i - 1] - highs[i] < left_eye_length * self.left_eye_depth
        ):
            return False

        # Nose body inside left eye body check
        if self.nose_body_inside_left_eye_body:
            if max(opens[i], closes[i]) > max(opens[i - 1], closes[i - 1]) or min(
                opens[i], closes[i]
            ) < min(opens[i - 1], closes[i - 1]):
                return False

        return True


# Example usage:
if __name__ == "__main__":
    # Create sample data
    data = pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [105, 106, 107, 108, 109],
            "Low": [95, 96, 97, 98, 99],
            "Close": [102, 103, 104, 105, 106],
        }
    )

    # Initialize detector
    detector = PinbarDetector(
        use_custom_settings=True,
        custom_max_nose_body_size=0.33,
        custom_nose_body_position=0.4,
    )

    # Detect pinbars
    signals, colors = detector.detect(data)
    # Print results
    for i, (signal, color) in enumerate(zip(signals, colors)):
        if signal is not None:
            pattern = "Bullish" if color == 0 else "Bearish"
            print(f"Bar {i}: {pattern} pinbar detected at price {signal:.2f}")
