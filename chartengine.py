import json
import requests
from datetime import datetime, timedelta
import pandas as pd
import chartink
import util


MY_CACHE = {}


def fetch_chart_data(stock_name: str, timeframe: str = "1D") -> pd.DataFrame:
    """
    Fetch OHLCV + indicators data for given stock from local API.
    
    Example:
        df = fetch_chart_data("TCS", "1D")
    """
    # You can map timeframe to endpoint if you have multiple
    # For now, your endpoint seems to be fixed pattern: /<symbol>/6
    # You can adjust if needed (e.g. "6" means 1D data)
    urlkey = {"1W": "700", "1D": "100", "1H": "60", "5m": "5"}
    url = f"http://127.0.0.1:3000/{stock_name}/"+urlkey.get(timeframe)

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data:
            print(f"No data received for {stock_name}")
            return pd.DataFrame()

        # Convert list of dicts → DataFrame
        df = pd.DataFrame(data)

        # Convert UNIX timestamp to datetime
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], unit="s")

        # Sort by time (ascending)
        df.sort_values("time", inplace=True)

        # Optional: Set 'time' as index
        df.set_index("time", inplace=True)

        # Keep only relevant columns if you like
        columns_to_keep = ["time", "open", "high", "low", "close", "volume", "ema50", "ema200", "rsi", "ultm"]
        df = df[[col for col in columns_to_keep if col in df.columns]]

        return df

    except requests.exceptions.RequestException as e:
        print(f"⚠️ Network error while fetching {stock_name}: {e}")
        return pd.DataFrame()
    except ValueError as e:
        print(f"⚠️ JSON parse error for {stock_name}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Unexpected error fetching {stock_name}: {e}")
        return pd.DataFrame()

def fetch_closexvol_for_stock(stock_info, donormalize = True):
    stock_name, stock_id = stock_info
    try:
        chartdf = fetch_chart_data(stock_name, "1W")
        #print(chartdf)
        close_volume_list = (chartdf['close'] * chartdf['volume']/1000000000).round(2).tolist()
        #print(chartdf.columns)
        yearlist = [timestamp.strftime('%Y-%m-%d') for timestamp in chartdf.index]
        rev_list = [[x, y] for x, y in zip(yearlist, close_volume_list)][::-1][0:30][::-1]

        #rev_list = [[item["c0"], item["c3"]] for item in data.get("incAnnualData", [])][::-1]
        return rev_list
    except Exception as e:
        print(f"Error fetching Stock data for {stock_name}: {e}")
        return []

        
if __name__ == "__main__":
    print(util.fetch_stock_data_from_MS(["RVNL", 3159563]))
    pass
    #print("Starting ...")
    #print("NP :"  + str(util.load_market_ids()+"/n")
    #print(util.fetch_stock_data_from_MS(["RVNL", 3159563]))
    #print("getExpansionFromMs :"  + str(util.fetch_Revenue_from_MS(["RVNL", 3159563]))+"/n")
    #print("ans :"  + str(util.fetch_stock_data_from_MS(["INDHOTEL", 3022475])))
    #print("ans :"  + str(util.fetch_stock_data_from_MS(["SUNTV", 3072042])))
    #print("ans :"  + str(util.fetch_stock_data_from_MS(["MUTHOOTFIN", 3117646])))
    #print(util.fetch_Revenue_from_MS(["RVNL", 3159563]))
    #print(util.getExpansionFromMs(["RVNL", 3159563]))
#   print(chartink(query8))
    
    
