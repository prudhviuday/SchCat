import json
import requests
from datetime import datetime, timedelta
import pandas as pd
import chartink
import chartengine

#marketidsfile =   "C:\\Users\\prudh\\OneDrive\\Desktop\\prog\\Dustbin\\marketsmithidsall.txt"
marketidsfile =   "data/marketsmithidsall4.xlsx"
databasefile  =   "data/ChartInkQs.xlsx"
#marketidsfile = "notsmith.txt"
MY_CACHE = {}
marketcapcache = {}
industrycache = {}



def normalize(data):
    numdata = [float(item) for item in data]
    #print(numdata)
    maxy = max(numdata)
    miny = min(numdata)
    norm_data = [int(100 * ((float(item)-miny)/(maxy-miny))) for item in numdata]
    return norm_data
    
# -------------------- ROCE --------------------
def fetch_ROCE_from_MS(stock_info):
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/financeDetails.json"
            f"?isConsolidated=false&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+252517161018+-1114664466"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        #print(url)
        data = requests.get(url, headers=headers, timeout=10).json()
        roce_list = [[item["c0"], item["c4"]] for item in data.get("ratiosAnnualData", [])][::-1]
        return roce_list
    except Exception as e:
        print(f"Error fetching ROCE for {stock_name}: {e}")
        return []
        
        
def getExpansionFromMs(stock_info):
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/financeDetails.json"
            f"?isConsolidated=false&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+252517161018+-1114664466"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=10).json()
        
        yearlist = ["01-"+item["c0"] for item in data.get("incQuarterData", [])][::-1]
        #print("c25"  + str([item["c25"] for item in data.get("incQuarterData", [])][::-1]))
        #print("c32"  + str([item["c32"] for item in data.get("incQuarterData", [])][::-1]))
        Exp_list  = [int((float(item["c25"])/float(item["c32"]))*100) for item in data.get("incQuarterData", [])][::-1]
        Exp = [[x, y] for x, y in zip(yearlist, Exp_list)]
        return Exp
    except Exception as e:
        print(f"Error fetching Expansion data for {stock_name}: {e}")
        return []
        
def getInstitutionOwnershipFromMs(stock_info, donormalize = True):
    stock_name, stock_id = stock_info
    #print("here 1")
    try:
        url = (
            f"https://msi-gcloud-prod.appspot.com/gateway/simple-api/ms-india/instr/0/{stock_id}/symboldetails.json"
            f"?s=20190810&e=20250810&text={stock_name}&lang=en&isConsolidated=0"
            f"&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+243117050847+-891152561"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        if stock_name in MY_CACHE:
            data = MY_CACHE[stock_name]
        else:
            data = requests.get(url, headers=headers, timeout=10).json()
            MY_CACHE[stock_name] = data
        #print("here 2")
        #print("getting institution ownership data for : "+stock_name)
        r = data.get("response", {}) 
        price = int(r.get('detailsGeneralInformationHeader',{}).get('currentPrice','0'))
        data = r.get("quarterlySalesAndEarningsInternational", {}).get("quarterlySalesAndEarningsOrigin", [])
        funds   = [item.get("totSharesHeldByFunds", 0) if item.get("totSharesHeldByFunds", 0) is not None else 0 for item in data][::-1]
        yearlist = ["01-"+item["prdYear"] for item in data][::-1]
        #print("here 3 donormalize:"+str(donormalize))
        nfunds = normalize(funds) if donormalize else funds
        #print(nfunds)
        ans = [[x, y] for x, y in zip(yearlist, nfunds)]
        return ans
    except Exception as e:
        print(f"Error fetching Institutional ownership for {stock_name}: {e}")
        return []
        
def getInstitutionCostFromMs(stock_info, donormalize = False):
    stock_name, stock_id = stock_info
    #print("here 1")
    try:
        url = (
            f"https://msi-gcloud-prod.appspot.com/gateway/simple-api/ms-india/instr/0/{stock_id}/symboldetails.json"
            f"?s=20190810&e=20250810&text={stock_name}&lang=en&isConsolidated=0"
            f"&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+243117050847+-891152561"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        if stock_name in MY_CACHE:
            data = MY_CACHE[stock_name]
        else:
            data = requests.get(url, headers=headers, timeout=10).json()
            MY_CACHE[stock_name] = data
        #print("here 2")
        #print("getting institution ownership data for : "+stock_name)
        r = data.get("response", {}) 
        price = int(r.get('detailsGeneralInformationHeader',{}).get('currentPrice','0'))
        data = r.get("quarterlySalesAndEarningsInternational", {}).get("quarterlySalesAndEarningsOrigin", [])
        funds   = [int(item.get("totSharesHeldByFunds", 0)*price/1000000000) if item.get("totSharesHeldByFunds", 0) is not None else 0 for item in data][::-1]
        yearlist = ["01-"+item["prdYear"] for item in data][::-1]
        #print("here 3 donormalize:"+str(donormalize))
        nfunds = normalize(funds) if donormalize else funds
        #print(nfunds)
        ans = [[x, y] for x, y in zip(yearlist, nfunds)]
        return ans
    except Exception as e:
        print(f"Error fetching Institutional ownership for {stock_name}: {e}")
        return []


def fetch_Revenue_from_MS(stock_info, donormalize = True):
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/financeDetails.json"
            f"?isConsolidated=false&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+252517161018+-1114664466"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=10).json()
        
        yearlist = [int("20"+item["c0"].split("-")[1]) for item in data.get("incAnnualData", [])][::-1]
        revlist  = [item["c3"] for item in data.get("incAnnualData", [])][::-1]
        #print(yearlist)
        #print(revlist)
        nrev = normalize(revlist) if donormalize else revlist
        rev_list = [[x, y] for x, y in zip(yearlist, nrev)]

        #rev_list = [[item["c0"], item["c3"]] for item in data.get("incAnnualData", [])][::-1]
        return rev_list
    except Exception as e:
        print(f"Error fetching Revenue for {stock_name}: {e}")
        return []

def fetch_closexvol_for_stock(stock_info, donormalize = True):
    stock_name, stock_id = stock_info
    try:
        chartdf = chartengine.fetch_chart_data(stock_name, "1W")
        #print(chartdf)
        close_volume_list = (chartdf['close'] * chartdf['volume']/1000000000).round(2).tolist()
        #print(list(chartdf['close']))
        #x = []
        #for i in range(len(chartdf['close'])):
        #    x.append([int(chartdf['close'][i]), int(chartdf['volume'][i]), round(chartdf['close'][i] * chartdf['volume'][i]/1000000000, 2)])
        #print(x)
        yearlist = [timestamp.strftime('%Y-%m-%d') for timestamp in chartdf.index]
        rev_list = [[x, y] for x, y in zip(yearlist, close_volume_list)][::-1][0:30][::-1]

        #rev_list = [[item["c0"], item["c3"]] for item in data.get("incAnnualData", [])][::-1]
        return rev_list
    except Exception as e:
        print(f"Error fetching Stock data for {stock_name}: {e}")
        return []

def fetch_EPS_from_MS(stock_info):
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/financeDetails.json"
            f"?isConsolidated=false&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+252517161018+-1114664466"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=10).json()
        
        yearlist = [int(item["c0"]) for item in data.get("ratiosAnnualData", [])][::-1]
        epslist  = [item["c20"] for item in data.get("ratiosAnnualData", [])][::-1]
        #print(yearlist)
        #print(epslist)
        eps_list = [[x, y] for x, y in zip(yearlist, normalize(epslist))]

        #rev_list = [[item["c0"], item["c3"]] for item in data.get("incAnnualData", [])][::-1]
        return eps_list
    except Exception as e:
        print(f"Error fetching EPS Data for {stock_name}: {e}")
        return []
        
def fetch_RS_graph_from_MS(stock_info, marketcapNorm = False):
    stock_name, stock_id = stock_info
    try:
        url = (         
        f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/details.json?symbol={stock_name}&p=1&s=20220416&e=20260404&b=0INNSE50&ie=0&iq=0&rs=N&em=1775280900000&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+260022160337+-2641794027"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=10).json()
        
        RawRSList = [item["rlst"] for item in data.get("chart").get("prices", [])]
        templist = list(filter(lambda a: a != None, RawRSList))
        avgRs = int(sum(templist)/(len(templist) if len(templist)>0 else 1))
        
        marketcap = get_market_cap_of(stock_name) if marketcapNorm else 1
        RSList = [(item if item else avgRs)*marketcap for item in RawRSList][::-1]
        #print(RawRSList)
        #print("*************************")
        #print(RSList)
        #yearlist = [int(item["c0"]) for item in data.get("ratiosAnnualData", [])][::-1]
        #epslist  = [item["c20"] for item in data.get("ratiosAnnualData", [])][::-1]
        #print(yearlist)
        #print(epslist)
        #eps_list = [[x, y] for x, y in zip(yearlist, normalize(epslist))]

        #rev_list = [[item["c0"], item["c3"]] for item in data.get("incAnnualData", [])][::-1]
        return RSList
    except Exception as e:
        print(f"Error fetching EPS Data for {stock_name}: {e}")
        return []
        
# -------------------- Delivery % --------------------
def fetch_DeliveryPerc_from_NSE(stock_info, donormalize = False):
    stock_name, stock_id = stock_info
    try:
        fromdate = (datetime.today() - timedelta(days=300)).strftime('%d-%m-%Y')
        todate = datetime.today().strftime('%d-%m-%Y')

        url = (
            f"https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData"
            f"?from={fromdate}&to={todate}&symbol={stock_name}&type=priceVolumeDeliverable&series=ALL"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=10).json()

        delivery_list = [
            [item["mTIMESTAMP"], int(item["CH_TOT_TRADED_VAL"]*item["COP_DELIV_PERC"]/10000000), int(item["CH_TOT_TRADED_VAL"]/100000), item["COP_DELIV_PERC"]]
            for item in data.get("data", [])
            if item.get("COP_DELIV_PERC") is not None
        ][::-1]
        df = pd.DataFrame(delivery_list, columns=["date", "delval", "totalval","delvperc"])
        interval = 5
        df["delval"] = df["delval"].rolling(window=interval).mean()
        df["totalval"] = df["totalval"].rolling(window=interval).mean()
        return df.iloc[interval:].values.tolist()
    except Exception as e:
        print(f"Error fetching Delivery % for {stock_name}: {e}")
        return []
        
        
# -------------------- EPS acc --------------------
def fetch_EPS_acc_from_MS(stock_info):
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/symboldetails.json?lang=en&isConsolidated=0&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+254121141012+357971843"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        #print(url)
        data = requests.get(url, headers=headers, timeout=10).json()
        #print(data.get("response").get("quarterlySalesAndEarningsInternational").get("quarterlySalesAndEarningsOrigin"))
        eps_list = [[item["prdYear"], max(min(int(item["epsPct"] or 0), 200), -200)] for item in data.get("response").get("quarterlySalesAndEarningsInternational").get("quarterlySalesAndEarningsOrigin")][::-1]
        return eps_list
    except Exception as e:
        print(f"Error fetching EPS% for {stock_name}: {e}")
        return []
        
        
# -------------------- sales acc --------------------
def fetch_Sales_acc_from_MS(stock_info):  #<-- give % of sales
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/symboldetails.json?lang=en&isConsolidated=0&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+254121141012+357971843"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        #print(url)
        data = requests.get(url, headers=headers, timeout=10).json()
        #print(data.get("response").get("quarterlySalesAndEarningsInternational").get("quarterlySalesAndEarningsOrigin"))
        sales_list = [[item["prdYear"], max(min(int(item["salesPct"] or 0), 200), -200)] for item in data.get("response").get("quarterlySalesAndEarningsInternational").get("quarterlySalesAndEarningsOrigin")][::-1]
        return sales_list
    except Exception as e:
        print(f"Error fetching Sales% for {stock_name}: {e}")
        return []

def fetch_Sales_acc_from_full_MS(stock_info):  #<-- give actual of sales
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://marketsmithindia.com/gateway/simple-api/ms-india/instr/0/{stock_id}/symboldetails.json?lang=en&isConsolidated=0&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+254121141012+357971843"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        #print(url)
        data = requests.get(url, headers=headers, timeout=10).json()
        #print(data.get("response").get("quarterlySalesAndEarningsInternational").get("quarterlySalesAndEarningsOrigin"))
        sales_list = [[item["prdYear"], item["sales"]] for item in data.get("response").get("quarterlySalesAndEarningsInternational").get("quarterlySalesAndEarningsOrigin")][::-1]
        return sales_list
    except Exception as e:
        print(f"Error fetching Sales% for {stock_name}: {e}")
        return []

def getepssalesrating(stockname, jssalesepsdata):
    #print(jssalesepsdata)
    score = 0
    if len(jssalesepsdata)>=3:
        epspct   = [item.get("epsPct", 0) if item.get("epsPct", 0) is not None else 0 for item in jssalesepsdata][0:3]
        salespct = [item.get("salesPct", 0) if item.get("salesPct", 0) is not None else 0 for item in jssalesepsdata][0:3]
        #print("here"+str(epspct)+str(salespct))
        Neps = [1 if item > 70 else 0 for item in epspct]
        Nsales = [1 if item > 70 else 0 for item in salespct]
        eup = 3 * (1 if epspct[0]>epspct[2] else 0) + 2 * (1 if epspct[0]>epspct[1] and epspct[1]>epspct[2] else 0)
        sup = 3 * (1 if salespct[0]>salespct[2] else 0) + 2 * (1 if salespct[0]>salespct[1] and salespct[1]>salespct[2] else 0)
        score = Neps[0]*5+Neps[1]*3+Neps[2]*2  +   Nsales[0]*5+Nsales[1]*3+Nsales[2]*2   + eup + sup
        #print(str(stockname)+" "+str(Neps)+" "+str(Nsales)+" "+str(score)+" "+str(eup)+" "+str(sup))
    return score
    

# -------------------- Stock Details --------------------
def fetch_stock_data_from_MS(stock_info):
    stock_name, stock_id = stock_info
    try:
        url = (
            f"https://msi-gcloud-prod.appspot.com/gateway/simple-api/ms-india/instr/0/{stock_id}/symboldetails.json"
            f"?s=20190810&e=20250810&text={stock_name}&lang=en&isConsolidated=0"
            f"&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+243117050847+-891152561"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        #print(url)
        if stock_name in MY_CACHE:
            data = MY_CACHE[stock_name]
        else:
            data = requests.get(url, headers=headers, timeout=10).json()
            MY_CACHE[stock_name] = data
        #print(data)

        r = data.get("response", {})
        g = r.get("detailsGeneralInformationHeader", {})
        b = r.get("detailsGeneralInformationHeaderBlock", {})
        
        revpct = r.get("quarterlySalesAndEarningsInternational", {}).get("quarterlySalesAndEarningsOrigin", [])
        rating = getepssalesrating(stock_name, revpct)
        peratio = int(g.get("pe", "0") if g.get("pe", "0") else 0)
        epsgrowthrate = b.get("epsGrowthRate", "1") or 5
        #print(stock_name," epsgrowthrate ", epsgrowthrate, " peratio ",peratio)
        PEG = round(peratio/epsgrowthrate, 2) or 5
        print(stock_name," epsgrowthrate ", epsgrowthrate, " peratio ",peratio, " peg ratio ", PEG)

        return {
            "Stock": stock_name,
            "Industry": get_stock_data_from_xl(stock_name, "Industry"), #g.get("industryName", "").replace("NSE-", ""),
            "GroupRank": g.get("industryGroupRank", ""),
            "RS": int(g.get("rsNumericGrade", 0)),
            "EPS": g.get("epsRank", ""),
            "MasterScore": g.get("masterScore", ""),
            "AccDis": g.get("accDisRating", ""),
            "ROE": g.get("roe", ""),
            "PE": peratio,
            "PEG" : PEG,
            "FScore": rating,
            "EPSGrowth": b.get("epsGrowthRate", ""),
            "Stability": b.get("earningsStability", ""),
            "PB":b.get("bookVal", ""),
            "ROCE":get_stock_data_from_xl(stock_name, "ROCE"),
            "NikScore":get_stock_data_from_xl(stock_name, "NikScore"),
            "CashFlow": b.get("cashFlow", ""),
        }

    except Exception as e:
        print(f"Error fetching stock data for {stock_name}: {e}")
        return {
            "Stock": stock_name,
            "Industry": "",
            "GroupRank": "",
            "RS": 0,
            "EPS": "",
            "MasterScore": "",
            "AccDis": "",
            "ROE": "",
            "PE": "",
            "PEG" : 5,
            "FScore": "0",
            "EPSGrowth": "0",
            "Stability": "0",
            "PB":"1000",
            "ROCE":1,
            "CashFlow": "0",
        }

# -------------------- Load Market IDs --------------------
def load_market_ids2():
    try:
        with open(marketidsfile) as f:
            data = json.load(f)
            return {i[0]: i[1] for i in data.get('marketids', [])}
    except Exception as e:
        print(f"Error loading market IDs: {e}")
        return {}
        
def load_market_ids():
    try:
        with open(marketidsfile) as f:
            df = pd.read_excel(marketidsfile)
            print("using list : "+marketidsfile)
            original_format = df.values.tolist()
            #print(original_format)
            return {i[0]: i[1] for i in original_format}
    except Exception as e:
        print(f"Error loading market IDs: {e}")
        return {}
     
     
def get_market_cap_of(stock):
    global marketcapcache
    try:
        if len(marketcapcache)>0:
            print("[*] loading market from cache ...")
            return marketcapcache.get(stock, 1)
        with open(marketidsfile) as f:
            df = pd.read_excel(marketidsfile)
            print("using list : "+marketidsfile)
            original_format = df.values.tolist()
            #print(original_format)
            marketcapcache = {i[0]: i[2] for i in original_format}
            return marketcapcache.get(stock, 1)
        return 1
    except Exception as e:
        print(f"Error loading market IDs: {e}")
        return {}
        
def get_stock_data_from_xl(stock, element = "ROCE"):
    global industrycache
    try:
        if len(industrycache)>0:
            #print("[*] loading market from cache ...")
            return industrycache.get(stock, 1).get(element)
        with open(marketidsfile) as f:
            df = pd.read_excel(marketidsfile)
            print("using list : "+marketidsfile)
            original_format = df.values.tolist()
            industrycache = {i[0]: {"Industry":i[4], "PB":i[5], "ROCE":i[6], "NikScore":i[7]} for i in original_format}
            #print(industrycache)
            return industrycache.get(stock, 1).get(element)
        return 1
    except Exception as e:
        print(f"Error loading market IDs: {e}")
        return {}

def getAllQueries():
    #print(pd.ExcelFile('ChartInkQs.xlsx').sheet_names)
    df = pd.read_excel(databasefile, sheet_name='QUERIES')
    column_data = df['Name'].tolist()
    allquerydata = dict(zip(df.iloc[:, 1], df.iloc[:, 2]))
    return allquerydata
    # util.getAllQueries()[1]("Fundamental")
  
def getCIfromQuery(query):
    #print(pd.ExcelFile('ChartInkQs.xlsx').sheet_names)
    stocks = chartink.chartink(query)
    return stocks
    
def getHistoryfromQuery(query):
    #print(pd.ExcelFile('ChartInkQs.xlsx').sheet_names)
    stocks = chartink.chartinkHistory(query)
    return stocks
   
def getAllWatchlists():
    #print(pd.ExcelFile('ChartInkQs.xlsx').sheet_names)
    df = pd.read_excel(databasefile, sheet_name='Watchlist')
    return df.to_dict('list')
    
def getPortfolio():
    #print(pd.ExcelFile('ChartInkQs.xlsx').sheet_names)
    df = pd.read_excel(databasefile, sheet_name='Portfolio')
    #print(df)
    return df.values.tolist()
    
def addStToWatchlists(watchlist, stock):
    df = pd.read_excel(databasefile, sheet_name='Watchlist')
    non_null_count = df[watchlist].count()
    df.loc[non_null_count, watchlist] = stock
    #df.to_excel('ChartInkQs.xlsx', sheet_name='Watchlist', index=False)
    with pd.ExcelWriter(databasefile, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name='Watchlist', index=False)
    return stock
   