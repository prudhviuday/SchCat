from bs4 import BeautifulSoup as bs
from concurrent.futures import ThreadPoolExecutor
import json
import pandas as pd
import requests
import pandas as pd 
import sys
import math
from pathlib import Path
from datetime import datetime
import util


market_ids = {}
SectorIds = {}
ALL_DATA = []
chartinkdata = []
MY_CACHE = dict()

query8 = '( {cash} ( market cap > 10000 and ( {cash} ( latest ""123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" /  min( 100 , abs(  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) )" > 0 and latest high > latest ema ( latest close , 13 ) and ( {cash} ( ( {cash} ( latest high > latest ema ( latest close , 13 ) and latest low < latest ema ( latest close , 13 ) ) ) or ( {cash} ( latest "1 - ( ( abs(  close -  open ) ) / (  high -  low ) )" > 0.5 ) ) ) ) and ( {cash} ( latest "ema( ( (  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" - 1 candle ago "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) / abs(  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) ) , 3 ) * 100" < 1 day ago "ema( ( (  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" - 1 candle ago "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) / abs(  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) ) , 3 ) * 100" or latest "ema( ( (  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" - 1 candle ago "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) / abs(  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) ) , 3 ) * 100" < 0 ) ) and ( {cash} ( ( {cash} ( latest ema ( latest close , 13 ) > latest ema ( latest close , 26 ) and latest ema ( latest close , 26 ) > latest ema ( latest close , 200 ) ) ) or ( {cash} ( latest ema ( latest close , 13 ) > 1 day ago ema ( latest close , 13 ) and latest ema ( latest close , 26 ) > 1 day ago ema ( latest close , 26 ) and latest ema ( latest close , 26 ) > latest ema ( latest close , 200 ) ) ) ) ) ) ) ) )   '

query9 = '( {cash} ( market cap > 3000 and weekly count( 7, 1 where weekly "ema( ( (  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" - 1 candle ago "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) / abs(  "123 / ( ( (  ema(  close , 32 ) /  ema(  close , 200 ) ) * 100 ) - 100 )" ) ) , 3 ) * 100" < 0 ) > 0 ) )     ' 

querybig = """select groupcount( {cash} 1 where daily "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) as '4% bull', groupcount( {cash} 1 where daily "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) as '4% bear', ( ( groupcount( {cash} 1 where daily "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 1 day ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) ) + groupcount( {cash} 1 where 2 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 3 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 4 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) ) / ( ( groupcount( {cash} 1 where daily "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 1 day ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 2 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 3 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 4 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) ) ) as '5-day ratio', ( ( groupcount( {cash} 1 where daily "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 1 day ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) ) + groupcount( {cash} 1 where 2 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 3 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 4 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 5 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 6 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 7 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 8 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) + groupcount( {cash} 1 where 9 days ago "close - 1 candle ago close / 1 candle ago close * 100" > 4 ) ) / ( ( groupcount( {cash} 1 where daily "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 1 day ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 2 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 3 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 4 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 5 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 6 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 7 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 8 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) + groupcount( {cash} 1 where 9 days ago "close - 1 candle ago close / 1 candle ago close * 100" < -4 ) ) ) as '10-day ratio', groupcount( {cash} 1 where 100 * ( daily close - daily min( 65 , daily close ) / daily min( 65 , daily close ) ) >= 25 ) as 'Q25 bull', groupcount( {cash} 1 where 100 * ( daily close - daily max( 65 , daily close ) / daily max( 65 , daily close ) ) <= -25 ) as 'Q25 bear', groupcount( {cash} 1 where 100 * ( daily close - 20 days ago close ) / 20 days ago close >= 25 ) as 'M25 bull', groupcount( {cash} 1 where 100 * ( daily close - 20 days ago close ) / 20 days ago close <= -25 ) as 'M25 bear', groupcount( {cash} 1 where 100 * ( daily close - 20 days ago close ) / 20 days ago close >= 50 ) as 'M50 bull', groupcount( {cash} 1 where 100 * ( daily close - 20 days ago close ) / 20 days ago close <= -50 ) as 'M50 bear', groupcount( {cash} 1 where 100 * ( daily close - daily min( 34 , daily close ) ) / daily min( 34 , daily close ) >= 13 ) as '34/13 bull', groupcount( {cash} 1 where 100 * ( daily close - daily max( 34 , daily close ) ) / daily max( 34 , daily close ) <= -13 ) as '34/13 bear' WHERE( {cash} ( daily close >= 20 and daily close <= 20000 and weekly sma( weekly buyer initiated trades , 10 ) > 200 ) ) ORDER BY 1 desc    """


def chartinkold(query):
    SCAN = {'scan_clause': query+'   '}
    with requests.session() as s:
        r_data = s.get("https://chartink.com/screener/process")
        soup = bs(r_data.content, "lxml")
        meta = soup.find("meta", {"name" : "csrf-token"})["content"]

        header = {"x-csrf-token" : meta}
        data = s.post("https://chartink.com/backtest/process", headers=header, data=SCAN).json()

        date = data["metaData"][0]["tradeTimes"]
        stock = data["aggregatedStockList"]

        final_data = []
        reqdata = dict()
        for i in range(0, len(date)):
            stk = []
            if stock[i] != []:
                for j in range(len(stock[i])):
                    if j % 3 == 0:
                        stk.append(stock[i][j])
                final_data.append({
                    "Date" : datetime.fromtimestamp(date[i]/1000),
                    "Stock" : stk
                })
                reqdata[datetime.fromtimestamp(date[i]/1000).strftime("%d-%m-%Y")] = stk
        #answer = reqdata[backdate] if backdate != "all" else reqdata
        i = 0
        #print(list(reqdata.keys())[-1])
        #print(set(reqdata[list(reqdata.keys())[-1]]))
        #print(reqdata)
        return list((set(reqdata[list(reqdata.keys())[-1]])))
        #engine(reqdata[list(reqdata.keys())[-1]])
        
def chartink(query):
    SCAN = {'scan_clause': query+'   '}
    with requests.session() as s:
        r_data = s.get("https://chartink.com/screener/process")
        soup = bs(r_data.content, "lxml")
        meta = soup.find("meta", {"name" : "csrf-token"})["content"]

        header = {"x-csrf-token" : meta}
        data = s.post("https://chartink.com/screener/process", headers=header, data=SCAN).json()
        finalfilter = [item['nsecode'] for item in data["data"]]
        
        return finalfilter
        #engine(reqdata[list(reqdata.keys())[-1]])
        
def chartinkHistory(query):
    SCAN = {'scan_clause': query+'   '}
    with requests.session() as s:
        r_data = s.get("https://chartink.com/screener/process")
        soup = bs(r_data.content, "lxml")
        meta = soup.find("meta", {"name" : "csrf-token"})["content"]

        header = {"x-csrf-token" : meta}
        data = s.post("https://chartink.com/backtest/process", headers=header, data=SCAN).json()

        date = data["metaData"][0]["tradeTimes"]
        stock = data["aggregatedStockList"]

        final_data = []
        reqdata = dict()
        for i in range(0, len(date)):
            stk = []
            if stock[i] != []:
                for j in range(len(stock[i])):
                    if j % 3 == 0:
                        stk.append(stock[i][j])
                final_data.append({
                    "Date" : datetime.fromtimestamp(date[i]/1000),
                    "Stock" : stk
                })
                reqdata[datetime.fromtimestamp(date[i]/1000).strftime("%d-%m-%Y")] = stk
        #answer = reqdata[backdate] if backdate != "all" else reqdata
        i = 0
        #print(list(reqdata.keys())[-1])
        #print(set(reqdata[list(reqdata.keys())[-1]]))
        #print(reqdata)
        totalhistory = []
        process = [totalhistory.extend(reqdata.get(key)) for key in reqdata.keys()]
        #print(set(totalhistory))
        return set(totalhistory)
        
def chartinkDashboard(query=None):

    SCAN = {
        'query': querybig,
        'use_live': '1',
        'limit': '6',
        'size': '375',
    }
    
    with requests.session() as s:
        r_data = s.get("https://chartink.com/screener/process")
        soup = bs(r_data.content, "lxml")
        meta = soup.find("meta", {"name" : "csrf-token"})["content"]

        header = {"x-csrf-token" : meta}
        data = s.post("https://chartink.com/widget/process", headers=header, data=SCAN).json()
        
        dates = data['metaData'][0]['tradeTimes']
        results = data['groupData'][0]['results']
        p4bull = results[0].get("4% bull")
        p4bear = results[1].get("4% bear")
        
        d5_ratio = results[2].get("5-day ratio")
        d10_ratio = results[3].get("10-day ratio")
        
        q25_bull = results[4].get("q25 bull")
        q25_bear = results[5].get("q25 bear")
        
        m25_bull = results[6].get("m25 bull")
        m25_bear = results[7].get("m25 bear")
        
        m50_bull = results[8].get("m50 bull")
        m50_bear = results[9].get("m50 bear")
        
        l3413_bull = results[10].get("34/13 bull")
        l3413_bear = results[11].get("34/13 bear")
        ALL_DATA = []

        for i in range(len(p4bull)):
            ALL_DATA.append([datetime.utcfromtimestamp(dates[i] / 1000).strftime('%d-%m-%Y'), p4bull[i], p4bear[i], round(d5_ratio[i],1), round(d10_ratio[i],1), q25_bull[i], q25_bear[i], m25_bull[i], m25_bear[i], m50_bull[i], m50_bear[i], l3413_bull[i],  l3413_bear[i]])
        
#        for j in ALL_DATA[::-1]:
#            print(j)
        return ALL_DATA[::-1]
        
def run_multiple_queries(queries: list[str]) -> list[str]:
    """Return intersection of results from all selected queries."""
    results = []
    for q in queries:
        res = chartink(q)
        if res:
            results.append(set(res))
    if not results:
        return []
    return list(set.intersection(*results))

if __name__ == "__main__":
    #print(chartinkDashboard(querybig))
    
    print("NP :"  + str(util.getPortfolio()))
    #print("NP :"  + str(util.get_market_cap_of("RELIANCE")))
    #print("NP :"  + str(util.get_market_cap_of("DELTACORP")))
    #print("ans :"  + str(util.fetch_closexvol_for_stock(["TATAPOWER", 3159563])))
    #util.getInstitutionOwnershipFromMs(["RVNL", 3159563])
    #util.getInstitutionCostFromMs(["RVNL", 3159563])
    #print(util.fetch_DeliveryPerc_from_NSE(["RVNL", 3159563], False))
    #chartinkHistory(query8)
    pass
