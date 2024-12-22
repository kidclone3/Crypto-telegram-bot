import numpy as np
import pandas as pd


class MultiKernelRegression:
    def __init__(
        self, bandwidth=14, kernel_type="laplace", deviations=2.0, repaint=True
    ):
        self.bandwidth = bandwidth
        self.kernel_type = kernel_type.lower()
        self.deviations = deviations
        self.repaint = repaint

    def _gaussian(self, x):
        return np.exp(-np.square(x) / 2) / np.sqrt(2 * np.pi)

    def _triangular(self, x):
        return np.where(np.abs(x) <= 1, 1 - np.abs(x), 0)

    def _epanechnikov(self, x):
        return np.where(np.abs(x) <= 1, 0.75 * (1 - np.square(x)), 0)

    def _quartic(self, x):
        return np.where(np.abs(x) <= 1, 15 / 16 * np.power(1 - np.square(x), 2), 0)

    def _logistic(self, x):
        return 1 / (np.exp(x) + 2 + np.exp(-x))

    def _cosine(self, x):
        return np.where(np.abs(x) <= 1, (np.pi / 4) * np.cos((np.pi / 2) * x), 0)

    def _laplace(self, x):
        return (1 / 2) * np.exp(-np.abs(x))

    def _exponential(self, x):
        return np.exp(-np.abs(x))

    def _silverman(self, x):
        return np.where(
            np.abs(x) <= 0.5, 0.5 * np.exp(-x / 2) * np.sin(x / 2 + np.pi / 4), 0
        )

    def _tent(self, x):
        return np.where(np.abs(x) <= 1, 1 - np.abs(x), 0)

    def _cauchy(self, x):
        return 1 / (np.pi * (1 + np.square(x)))

    def _sinc(self, x):
        x = np.where(x == 0, 1e-10, x)  # Avoid division by zero
        return np.sin(np.pi * x) / (np.pi * x)

    def _wave(self, x):
        return np.where(np.abs(x) <= 1, (1 - np.abs(x)) * np.cos(np.pi * x), 0)

    def _parabolic(self, x):
        return np.where(np.abs(x) <= 1, 1 - np.square(x), 0)

    def _power(self, x):
        return np.where(np.abs(x) <= 1, np.power(1 - np.power(np.abs(x), 3), 3), 0)

    def _loglogistic(self, x):
        return 1 / np.power(1 + np.abs(x), 2)

    def _morters(self, x):
        return np.where(np.abs(x) <= np.pi, (1 + np.cos(x)) / (2 * np.pi), 0)

    def _get_kernel_function(self):
        kernel_functions = {
            "gaussian": self._gaussian,
            "triangular": self._triangular,
            "epanechnikov": self._epanechnikov,
            "logistic": self._logistic,
            "loglogistic": self._loglogistic,
            "cosine": self._cosine,
            "sinc": self._sinc,
            "laplace": self._laplace,
            "quartic": self._quartic,
            "parabolic": self._parabolic,
            "exponential": self._exponential,
            "silverman": self._silverman,
            "cauchy": self._cauchy,
            "tent": self._tent,
            "wave": self._wave,
            "power": self._power,
            "morters": self._morters,
        }
        return kernel_functions.get(self.kernel_type, self._laplace)

    def _detect_signals(self, regression):
        """
        Detect Up and Down signals based on trend changes

        Parameters:
            regression (np.array): Regression values

        Returns:
            tuple: (up_signals, down_signals)
        """
        # Calculate deltas (price changes)
        deltas = np.diff(regression)
        deltas = np.insert(
            deltas, 0, 0
        )  # Add 0 at the beginning to maintain array size

        # Calculate previous deltas
        prev_deltas = np.roll(deltas, 1)
        prev_deltas[0] = 0

        # Detect signals
        up_signals = (deltas > 0) & (prev_deltas < 0)
        down_signals = (deltas < 0) & (prev_deltas > 0)

        return up_signals, down_signals

    def calculate_non_repainting(self, data):
        """
        Calculate non-repainting kernel regression with signals

        Parameters:
            data (np.array): Price data

        Returns:
            tuple: (regression values, standard deviations, up_signals, down_signals)
        """
        kernel_func = self._get_kernel_function()
        weights = np.array(
            [kernel_func(i**2 / self.bandwidth**2) for i in range(self.bandwidth)]
        )
        weights = weights / np.sum(weights)

        # Calculate regression values
        regression = np.zeros_like(data)
        for i in range(len(data)):
            if i < self.bandwidth:
                regression[i] = np.nan
            else:
                window = data[i - self.bandwidth : i]
                regression[i] = np.sum(window * weights[::-1])

        # Calculate standard deviation
        std_dev = np.zeros_like(data)
        for i in range(len(data)):
            if i < self.bandwidth:
                std_dev[i] = np.nan
            else:
                window = data[i - self.bandwidth : i]
                dev = window - regression[i]
                std_dev[i] = np.sqrt(
                    np.sum(dev**2 * weights[::-1]) / (self.bandwidth - 1)
                )

        # Detect signals
        up_signals, down_signals = self._detect_signals(regression)

        return regression, std_dev * self.deviations, up_signals, down_signals

    def calculate_repainting(self, data):
        """
        Calculate repainting kernel regression with signals

        Parameters:
            data (np.array): Price data

        Returns:
            tuple: (regression values, standard deviations, up_signals, down_signals)
        """
        kernel_func = self._get_kernel_function()
        regression = np.zeros_like(data)
        std_dev = np.zeros_like(data)

        for i in range(len(data)):
            weights = np.array(
                [
                    kernel_func((i - j) / self.bandwidth)
                    for j in range(
                        max(0, i - self.bandwidth),
                        min(len(data), i + self.bandwidth + 1),
                    )
                ]
            )
            weights = weights / np.sum(weights)

            window = data[
                max(0, i - self.bandwidth) : min(len(data), i + self.bandwidth + 1)
            ]
            regression[i] = np.sum(window * weights)

            dev = window - regression[i]
            std_dev[i] = np.sqrt(np.sum(dev**2 * weights) / (len(weights) - 1))

        # Detect signals
        up_signals, down_signals = self._detect_signals(regression)

        return regression, std_dev * self.deviations, up_signals, down_signals

    def calculate(self, data):
        """
        Main calculation function

        Parameters:
            data (np.array): Price data

        Returns:
            tuple: (regression values, upper band, lower band, up_signals, down_signals)
        """
        if self.repaint:
            regression, std_dev, up_signals, down_signals = self.calculate_repainting(
                data
            )
        else:
            regression, std_dev, up_signals, down_signals = (
                self.calculate_non_repainting(data)
            )

        upper_band = regression + std_dev
        lower_band = regression - std_dev

        return regression, upper_band, lower_band, up_signals, down_signals


def apply_multi_kernel_regression(
    df,
    source="close",
    bandwidth=14,
    kernel_type="laplace",
    deviations=2.0,
    repaint=True,
):
    """
    Apply multi kernel regression to a pandas DataFrame

    Parameters:
        df (pd.DataFrame): DataFrame with OHLCV data
        source (str): Column name to use as source
        bandwidth (int): Kernel bandwidth
        kernel_type (str): Type of kernel to use
        deviations (float): Number of standard deviations for bands
        repaint (bool): Whether to allow repainting

    Returns:
        pd.DataFrame: Original DataFrame with additional columns for regression and signals
    """
    mkr = MultiKernelRegression(bandwidth, kernel_type, deviations, repaint)

    # Calculate regression, bands, and signals
    regression, upper, lower, up_signals, down_signals = mkr.calculate(
        df[source].values
    )

    # Add results to DataFrame
    df["kernel_ma"] = regression
    if deviations > 0:
        df["kernel_upper"] = upper
        df["kernel_lower"] = lower

    # Add signals
    df["signal_up"] = up_signals
    df["signal_down"] = down_signals

    return df


def viewable_signal(df):
    df["signal_val_up"] = df.apply(
        lambda row: row["low"] * 0.99 if row["signal_up"] else np.nan, axis=1
    )
    df["signal_val_down"] = df.apply(
        lambda row: row["high"] * 1.01 if row["signal_down"] else np.nan, axis=1
    )
    return df
