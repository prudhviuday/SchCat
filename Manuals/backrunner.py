import json
import requests
from datetime import datetime, timedelta
import pandas as pd

#marketidsfile =   "C:\\Users\\prudh\\OneDrive\\Desktop\\prog\\Dustbin\\marketsmithidsall.txt"
marketidsfile =   "AllStocks.xlsx"

MY_CACHE = {}
marketcapcache = {}


insid_url ="https://marketsmithindia.com/gateway/simple-api/ms-india/instr/srch.json?text=rv&lang=en&listID=-1&ver=2"

def load_market_ids():
    try:
        with open(marketidsfile) as f:
            df = pd.read_excel(marketidsfile)
            #print("using list : "+marketidsfile)
            original_format = [i[0] for i in df.values.tolist()]
            return original_format
    except Exception as e:
        print(f"Error loading market IDs: {e}")
        return {}
        


def fetch_EPS_from_MS():
    alldata = []
    stocklist = load_market_ids()
    for stock_name in stocklist:
        try:
            url = (
                f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/srch.json?text={stock_name}&lang=en&listID=-1&ver=2"
            )
            headers = {'User-Agent': 'Mozilla/5.0'}
            data = requests.get(url, headers=headers, timeout=10).json()
            
            stocksymbolgot= str(data.get("response", {}).get("results", {})[0].get("symbol", 0000))
            insid = str(data.get("response", {}).get("results", {})[0].get("instrumentId", 0000))
            
            print(stock_name+" : "+stocksymbolgot+" insid:"+str(insid))
            alldata.append([stock_name, insid])
            #yearlist = [int(item["c0"]) for item in data.get("ratiosAnnualData", [])][::-1]
            #epslist  = [item["c20"] for item in data.get("ratiosAnnualData", [])][::-1]
            #print(yearlist)
            #print(epslist)
            
            #rev_list = [[item["c0"], item["c3"]] for item in data.get("incAnnualData", [])][::-1]
            
        except Exception as e:
            print(f"Error fetching EPS Data for {stock_name}: {e}")
            
    df = pd.DataFrame(alldata)
    df.to_excel("output.xlsx", index=False, header=False)
    return []
            
fetch_EPS_from_MS()