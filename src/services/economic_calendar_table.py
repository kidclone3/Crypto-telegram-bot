import json
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from urllib.request import urlopen, Request


def connection(url):
    """get html of website with request and parse it with soup"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36"
    }
    data = requests.get(url, headers=headers).content
    soup = BeautifulSoup(data, "html.parser")
    table = soup.find("table", id="economicCalendarData")
    return table


def find_time(element):
    """find the time of each id"""
    time_ = element.find("td", class_="first left time js-time").string
    return time_


def find_flag(element):
    """find the flag of each id"""
    flag_name = element.find("td", class_="left flagCur noWrap").text.strip()
    return flag_name


def usa_table(table):
    """only show USA event"""
    for index, flag in enumerate(table.values):
        if not flag[1] == "USD":
            table = table.drop(index)
    table = table.reset_index(drop=True)
    return table


def find_number_star(element):
    """evaluating value of each news by number of stars"""
    imp = element.find("td", class_="left textNum sentiment noWrap").attrs[
        "data-img_key"
    ]
    imp_list = []
    pattern = re.compile("bull([0-3])")
    len_star = pattern.findall(imp)
    for i in range(int(len_star[0])):
        imp_list.append("*")
    imp_star = "".join(imp_list)
    return imp_star


def find_event(element):
    """the name of event find with this function"""
    Event = element.find("a", href=True).text.strip()
    return Event


def find_value(id, element):
    """find the value of each rows of Actual Forecast and Previous"""
    actual = element.find("td", id=f"eventActual_{id}").text
    forecast = element.find("td", id=f"eventForecast_{id}").text
    previous = element.find("td", id=f"eventPrevious_{id}").text

    return actual, forecast, previous


def get_extreme(table):
    """get only data that important"""
    for index, data in enumerate(table.values):
        if not data[2] == "***":
            table = table.drop(index)
    table = table.reset_index(drop=True)

    return table


def clean_df(table):
    """
    table was clean from \xa0 decoded and clean and nothing wasn't shown
    """
    table["Actual"] = table["Actual"].apply(lambda x: str(x).replace("\xa0", ""))
    table["Forecast"] = table["Forecast"].apply(lambda x: str(x).replace("\xa0", ""))
    table["Previous"] = table["Previous"].apply(lambda x: str(x).replace("\xa0", ""))
    return table


def find_table(table):
    """find the main table"""

    main_df = pd.DataFrame(
        columns=["Time", "Flag", "Imp", "Event", "Actual", "Forecast", "Previous"]
    )
    for element in table.find_all("tr", class_="js-event-item"):
        element_dict = element.attrs
        id = element_dict["id"].split("_")[1]
        time_ = find_time(element)
        flag = find_flag(element)
        imp_star = find_number_star(element)
        event = find_event(element)
        actual, forecast, previous = find_value(id=id, element=element)
        id_df = pd.DataFrame(
            {
                "Time": time_,
                "Flag": flag,
                "Imp": [imp_star],
                "Event": event,
                "Actual": actual,
                "Forecast": forecast,
                "Previous": previous,
            }
        )
        main_df = pd.concat([main_df, id_df], ignore_index=True)

    return main_df


def find_index(main_df):
    """find text of each data for replace new data in it"""
    index_ = []
    # main_event = persian.keys()
    for ev in range(int(main_df.shape[0])):
        event = main_df.Event[ev]
        for k in "main_event":
            search = re.search(pattern=f"{k}", string=event, flags=0)
            if not search == None:
                index_.append(ev)
    return index_


def final_table(url="https://www.investing.com/economic-calendar"):
    """get USA table from investing.com"""
    try:
        table = connection(url=url)
        table_inf = find_table(table)
        table_inf = clean_df(table_inf)
        usa_df = usa_table(table_inf)
        extreme_data = get_extreme(usa_df)
        print(extreme_data)
        return extreme_data
    except Exception as e:
        return e


def get_event():
    r = Request(
        "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
        headers={"User-Agent": "Mozilla/5.0", "accept-language": "en-US,en;q=0.9"},
        data={},
    )
    response = urlopen(r).read()
    soup = BeautifulSoup(response, "html.parser")
    table = soup.find_all(class_="js-event-item")

    result = []
    base = {}

    for bl in table:
        time = bl.find(class_="first left time js-time").text
        # evento = bl.find(class_ ="left event").text
        currency = bl.find(class_="left flagCur noWrap").text.split(" ")
        event = bl.find(class_="left event").a.text.split("\n")[1]
        intensity = bl.find_all(class_="left textNum sentiment noWrap")
        id_hour = currency[1] + "_" + time

        if id_hour not in base:
            base.update(
                {
                    id_hour: {
                        "currency": currency[1],
                        "event": event,
                        "time": time,
                        "intensity": {"1": 0, "2": 0, "3": 0, "priority": 0},
                    }
                }
            )

        intencity = base[id_hour]["intensity"]

        for intence in intensity:
            _true = intence.find_all(class_="grayFullBullishIcon")
            _false = intence.find_all(class_="grayEmptyBullishIcon")

            if len(_true) == 1:
                intencity["1"] += 1
                intencity["priority"] = 1

            elif len(_true) == 2:
                intencity["2"] += 1
                intencity["priority"] = 2

            elif len(_true) == 3:
                intencity["3"] += 1
                intencity["priority"] = 3

        base[id_hour].update({"intensity": intencity})

    for b in base:
        result.append(base[b])

    return result


def get_flag(currency):
    if currency == "EUR":
        return "🇪🇺"

    elif currency == "USD":
        return "🇺🇸"

    elif currency == "AUD":
        return "🇦🇺"

    elif currency == "NZD":
        return "🇳🇿"

    elif currency == "CAD":
        return "🇨🇦"

    elif currency == "CHF":
        return "🇨🇭"

    elif currency == "JPY":
        return "🇯🇵"
    elif currency == "GBP":
        return "🇬🇧"


if __name__ == "__main__":
    news = get_event()
    print(json.dumps(news, indent=2))
