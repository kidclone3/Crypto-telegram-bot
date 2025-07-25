import numpy as np
import pandas as pd
import pytest

from telegram_bot.services.MultiKernelRegression import (
    MultiKernelRegression,
    apply_multi_kernel_regression,
    viewable_signal,
)


@pytest.fixture
def sample_regression_df():
    # Create a sample DataFrame similar to what might be used
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    data = {
        "close": np.random.rand(100) * 100 + 1000,
        "high": np.random.rand(100) * 10 + 1100,
        "low": 1000 - np.random.rand(100) * 10,
    }
    df = pd.DataFrame(data, index=dates)
    return df


# Test the MultiKernelRegression class initialization and kernel methods
@pytest.mark.parametrize(
    "kernel_type",
    [
        "gaussian",
        "triangular",
        "epanechnikov",
        "logistic",
        "loglogistic",
        "cosine",
        "sinc",
        "laplace",
        "quartic",
        "parabolic",
        "exponential",
        "silverman",
        "cauchy",
        "tent",
        "wave",
        "power",
        "morters",
    ],
)
def test_mkr_class_init_and_kernels(kernel_type):
    mkr = MultiKernelRegression(
        bandwidth=14, kernel_type=kernel_type, deviations=2.0, repaint=True
    )
    assert mkr.bandwidth == 14
    assert mkr.kernel_type == kernel_type
    assert mkr.deviations == 2.0
    assert mkr.repaint is True
    # Test if the kernel function exists
    assert hasattr(mkr, f"_{kernel_type}")
    kernel_func = getattr(mkr, f"_{kernel_type}")
    # Test kernel function with a sample value
    result = kernel_func(
        np.array([0.5])
    )  # Test with a value within typical kernel ranges
    assert isinstance(result, np.ndarray)
    # Add more specific checks for kernel outputs if needed


# Test the calculate method (both repainting and non-repainting)
@pytest.mark.parametrize("repaint_flag", [True, False])
def test_mkr_calculate(sample_regression_df, repaint_flag):
    mkr = MultiKernelRegression(
        bandwidth=14,
        kernel_type="laplace",
        deviations=2.0,
        repaint=repaint_flag,
    )
    data = sample_regression_df["close"].values
    regression, upper, lower, up_signals, down_signals = mkr.calculate(data)

    assert isinstance(regression, np.ndarray)
    assert isinstance(upper, np.ndarray)
    assert isinstance(lower, np.ndarray)
    assert isinstance(up_signals, np.ndarray)
    assert isinstance(down_signals, np.ndarray)
    # Drop NA for up_signals and down_signals
    up_signals = up_signals[~np.isnan(up_signals)]
    down_signals = down_signals[~np.isnan(down_signals)]

    assert len(regression) == len(data)
    assert len(upper) == len(data)
    assert len(lower) == len(data)
    assert len(up_signals) == len(data)
    assert len(down_signals) == len(data)
    upper = upper[~np.isnan(upper)]
    lower = lower[~np.isnan(lower)]

    assert np.all(upper >= lower)  # Upper band should be >= lower band
    # Assert signals are lists of boolean values (True or False)
    assert all(isinstance(signal, bool) for signal in up_signals.tolist()), (
        "Signals should be True or False"
    )
    assert all(isinstance(signal, bool) for signal in down_signals.tolist()), (
        "Signals should be True or False"
    )


# Test the apply_multi_kernel_regression function
def test_apply_multi_kernel_regression(sample_regression_df):
    df_result = apply_multi_kernel_regression(
        sample_regression_df.copy(),  # Use copy to avoid modifying fixture
        source="close",
        bandwidth=14,
        kernel_type="laplace",
        deviations=2.0,
        repaint=True,
    )

    assert isinstance(df_result, pd.DataFrame)
    assert "kernel_ma" in df_result.columns
    assert "kernel_upper" in df_result.columns
    assert "kernel_lower" in df_result.columns
    assert "signal_up" in df_result.columns
    assert "signal_down" in df_result.columns

    assert not df_result["kernel_ma"].isnull().all()
    assert not df_result["signal_up"].isnull().all()


def test_viewable_signal(sample_regression_df):
    # First apply MKR to get the signal columns
    df_with_signals = apply_multi_kernel_regression(sample_regression_df.copy())

    # Then apply viewable_signal
    df_viewable = viewable_signal(df_with_signals)

    # Basic structure tests
    assert isinstance(df_viewable, pd.DataFrame)
    assert "signal_val_up" in df_viewable.columns
    assert "signal_val_down" in df_viewable.columns

    # Check that values are NaN where signal is False
    assert (
        df_viewable.loc[~df_viewable["signal_up"], "signal_val_up"].isna().all()
    )
    assert (
        df_viewable.loc[~df_viewable["signal_down"], "signal_val_down"]
        .isna()
        .all()
    )

    # Check that values are calculated where signal is True
    if df_viewable["signal_up"].any():
        # No NaN values where signal_up is True
        assert (
            not df_viewable.loc[df_viewable["signal_up"], "signal_val_up"]
            .isna()
            .any()
        )

        # Verify calculation: signal_val_up = low * 0.99
        pd.testing.assert_series_equal(
            df_viewable.loc[df_viewable["signal_up"], "signal_val_up"],
            df_viewable.loc[df_viewable["signal_up"], "low"] * 0.99,
            check_names=False,
        )

    if df_viewable["signal_down"].any():
        # No NaN values where signal_down is True
        assert (
            not df_viewable.loc[df_viewable["signal_down"], "signal_val_down"]
            .isna()
            .any()
        )

        # Verify calculation: signal_val_down = high * 1.01
        pd.testing.assert_series_equal(
            df_viewable.loc[df_viewable["signal_down"], "signal_val_down"],
            df_viewable.loc[df_viewable["signal_down"], "high"] * 1.01,
            check_names=False,
        )
