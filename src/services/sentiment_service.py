import pandas as pd
from cachetools import TTLCache, cached

SENTIMENT_DATA = "~/Documents/ai-agents-for-trading/src/data/sentiment_history.csv"


# Cache for 15 minutes
@cached(cache=TTLCache(maxsize=1, ttl=900))
def get_sentiment_data() -> pd.DataFrame:
    return pd.read_csv(SENTIMENT_DATA)


def get_latest_sentiment() -> str:
    data = get_sentiment_data()
    latest_entry = data.iloc[-1]
    timestamp = latest_entry["timestamp"]
    sentiment_score = latest_entry["sentiment_score"]
    num_tweets = latest_entry["num_tweets"]
    sentiment_color = "🟢" if sentiment_score > 0 else "🔴"
    message = (
        f"Time: {timestamp}\n"
        f"Sentiment Score: {sentiment_score:.2f} {sentiment_color}\n"
        f"Number of Tweets: {num_tweets}"
        f"\n\nNote: Scores range from -1 to 1, with -1 being very negative and 1 being very positive."
    )
    return message
