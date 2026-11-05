import json
import requests
from datetime import datetime, timedelta
import pandas as pd
import sys, os


import util

#marketidsfile =   "C:\\Users\\prudh\\OneDrive\\Desktop\\prog\\Dustbin\\marketsmithidsall.txt"
marketidsfile =   "Data\\marketsmithidsall4.xlsx"

MY_CACHE = {}
marketcapcache = {}


insid_url ="https://marketsmithindia.com/gateway/simple-api/ms-india/instr/srch.json?text=rv&lang=en&listID=-1&ver=2"

        
def load_market_data2():
    try:
        df = pd.read_excel(marketidsfile)

        # Convert entire dataframe to list of lists
        data = df.values.tolist()

        return data

    except Exception as e:
        print(f"Error loading market data: {e}")
        return []

def clamp(value, min_val=0, max_val=100):
    return max(min_val, min(value, max_val))


def growth_score(sales_growth_list):
    """
    sales_growth_list: last 4 quarter YoY % growth
    Example: [110, 39, 5, 29]
    """

    weights = [0.4, 0.3, 0.2, 0.1]

    weighted_growth = sum(g * w for g, w in zip(sales_growth_list, weights))

    # Convert to score (centered around 50)
    score = 50 + (weighted_growth * 2)

    return clamp(score)


def roce_score(roce):
    """
    ROCE in %
    """

    if roce < 10:
        return 20
    elif roce < 15:
        return 40
    elif roce < 20:
        return 60
    elif roce < 25:
        return 75
    elif roce < 30:
        return 90
    else:
        return 100


def pb_score(pb):
    """
    Price to Book ratio
    Lower is better, but capped
    """

    if pb < 1:
        return 100
    elif pb < 2:
        return 90
    elif pb < 4:
        return 75
    elif pb < 6:
        return 55
    elif pb < 8:
        return 35
    else:
        return 20


def final_score(sales_growth_list, roce, pb):
    g = growth_score(sales_growth_list)
    r = roce_score(roce)
    v = pb_score(pb)

    final = 0.45 * g + 0.35 * r + 0.20 * v

    return {
        "Growth Score": round(g, 2),
        "ROCE Score": r,
        "PB Score": v,
        "Final Score": round(final, 2)
    }        

def processsales(salespc):
    if len(salespc)>=4:
        sp = [sp for qrtr, sp in salespc]
        return sp[-4:][::-1]
    if len(salespc)<4:
        sp = [sp for qrtr, sp in salespc]
        sp2 = ([0]*(4-len(sp)))+sp
        return sp2[::-1]
    return [0, 0, 0, 0]

def process():
    alldata = []
    stocklist = load_market_data2()
    updatedstocklist = [["StockSymbol",	"InstrumentId",	"MarketCap",	"sector",	"industry",	"P/B",	"ROCE",	"Nik-Score"]]
    #print(stocklist)
    for StockSymbol, InstrumentId, MarketCap, sector, industry, PB_old,	ROCE_old, NikScore_old  in stocklist:
        try:
           sales = util.fetch_Sales_acc_from_MS([StockSymbol, InstrumentId]) 
           sales = processsales(sales)
           #print(StockSymbol+" "+str(sales))
           stockData = util.fetch_stock_data_from_MS([StockSymbol, InstrumentId])
           PB = float(stockData.get("PB",1000))
           #print(StockSymbol+" "+str(PB))
           ROCE = float(util.fetch_ROCE_from_MS([StockSymbol, InstrumentId])[-1][1])
           #print(StockSymbol+" "+str(ROCE))
           #print(final_score(sales, ROCE, PB))
           #print("*****************************************")
           nikscore = final_score(sales, ROCE, PB).get("Final Score")
           updatedstocklist.append([StockSymbol, InstrumentId, MarketCap, sector, industry, PB,	ROCE, nikscore])
        except Exception as e:
            print(f"Error updating Listupdater for {StockSymbol}: {e}")
            updatedstocklist.append([StockSymbol, InstrumentId, MarketCap, sector, industry, 100,	0, 0])
    
    #print(updatedstocklist)        
    df = pd.DataFrame(updatedstocklist)
    df.to_excel(marketidsfile, index=False, header=False)
    return []
            
#print(load_market_data2())
process()