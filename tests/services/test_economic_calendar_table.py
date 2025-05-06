import pytest
import pandas as pd
from bs4 import BeautifulSoup
from src.services.economic_calendar_table import (
    usa_table,
    find_number_star,
    find_event,
    find_value,
    get_extreme,
    clean_df,
    # final_table and get_event might require mocking network requests,
    # focusing on the pure transformation functions first.
)


# Sample DataFrame fixtures
@pytest.fixture
def sample_calendar_df():
    data = {
        "Time": ["08:30", "10:00", "14:00", "14:00"],
        "Currency": ["USD", "EUR", "USD", "GBP"],
        "Importance": ["***", "**", "***", "*"],
        "Event": [
            "Nonfarm Payrolls",
            "ECB Rate Decision",
            "Michigan Sentiment",
            "BoE Gov Speaks",
        ],
        "Actual": ["250K", "1.5%", "95.2", ""],
        "Forecast": ["200K", "1.5%", "95.0", ""],
        "Previous": ["180K", "1.25%", "94.8", ""],
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_uncleaned_df():
    data = {
        "Actual": ["250K\xa0", "\xa01.5%", "95.2", "\xa0"],
        "Forecast": ["200K", "1.5%\xa0", "\xa095.0", ""],
        "Previous": ["\xa0180K\xa0", "1.25%", "", "\xa0"],
    }
    return pd.DataFrame(data)


# Sample BeautifulSoup element fixtures
@pytest.fixture
def sample_html_element_star():
    html = """
    <tr class="js-event-item" data-event-id="123">
        <td class="left flagCur noWrap"><span title="United States" class="ceFlags USA"></span>USD</td>
        <td class="left textNum sentiment noWrap" data-img_key="bull3">High</td>
        <td class="left event"> <a href="/economic-calendar/event">Test Event Name</a></td>
        <td>1.0%</td>
        <td>0.9%</td>
        <td>0.8%</td>
    </tr>
    """
    return BeautifulSoup(html, "html.parser").find("tr")


@pytest.fixture
def sample_html_element_event():
    html = """
    <tr class="js-event-item" data-event-id="456">
        <td class="left flagCur noWrap"><span title="Euro Zone" class="ceFlags EUR"></span>EUR</td>
        <td class="left textNum sentiment noWrap" data-img_key="bull2">Med</td>
        <td class="left event"><a href="/some/link" target="_blank"> Specific Event Title </a></td>
        <td>A</td>
        <td>F</td>
        <td>P</td>
    </tr>
    """
    return BeautifulSoup(html, "html.parser").find("tr")


@pytest.fixture
def sample_html_element_value():
    html = """
    <tr class="js-event-item" data-event-id="789">
        <td>Time</td>
        <td>Cur</td>
        <td>Imp</td>
        <td>Event</td>
        <td id="eventActual_789"> 100 </td>
        <td id="eventForecast_789"> 90 </td>
        <td id="eventPrevious_789"> 80 </td>
    </tr>
    """
    return BeautifulSoup(html, "html.parser").find("tr")


# Tests for individual functions
def test_usa_table(sample_calendar_df):
    usa_df = usa_table(sample_calendar_df.copy())  # Use copy
    assert len(usa_df) == 2
    assert all(usa_df["Currency"] == "USD")
    assert list(usa_df["Event"]) == ["Nonfarm Payrolls", "Michigan Sentiment"]


def test_find_number_star(sample_html_element_star):
    stars = find_number_star(sample_html_element_star)
    assert stars == "***"


def test_find_event(sample_html_element_event):
    event_name = find_event(sample_html_element_event)
    assert event_name == "Specific Event Title"


def test_find_value(sample_html_element_value):
    actual, forecast, previous = find_value("789", sample_html_element_value)
    assert actual == "100"
    assert forecast == "90"
    assert previous == "80"


def test_get_extreme(sample_calendar_df):
    extreme_df = get_extreme(sample_calendar_df.copy())  # Use copy
    assert len(extreme_df) == 2
    assert all(extreme_df["Importance"] == "***")
    assert list(extreme_df["Event"]) == ["Nonfarm Payrolls", "Michigan Sentiment"]


def test_clean_df(sample_uncleaned_df):
    cleaned_df = clean_df(sample_uncleaned_df.copy())  # Use copy
    assert cleaned_df["Actual"][0] == "250K"
    assert cleaned_df["Actual"][1] == "1.5%"
    assert cleaned_df["Actual"][3] == ""
    assert cleaned_df["Forecast"][1] == "1.5%"
    assert cleaned_df["Forecast"][2] == "95.0"
    assert cleaned_df["Previous"][0] == "180K"
    assert cleaned_df["Previous"][3] == ""


# Add more tests, potentially mocking network calls for final_table and get_event if needed
