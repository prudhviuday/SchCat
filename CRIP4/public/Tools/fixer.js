const candle_conv = require('candlestick-convert')
var yahooFinance = require('yahoo-finance');
const got = require('got');
const fs = require('fs');
const timeperiod = 6

const getFormattedTime = (dt) => {
    //"2022-07-03-20-00"
    var d = dt.split("-");
    var datum = new Date(Date.UTC(d[0],d[1]-1,d[2],d[3],'00','00'));
    return datum.getTime()/1000;
  };

const getMarketSmithId = (stock) => {
    var stockmsid = 123456
    try {
      const data = fs.readFileSync("C:\\MAIN\\Programming\\Node\\CRIP3\\public\\Tools\\marketsmithids.json", 'utf8');
      const jsonData = JSON.parse(data);
      stockmsid = jsonData[stock.toUpperCase()]
    } catch (err) {
      console.error(err);
    }
    return stockmsid
  };

const goldUrlmaker = () => {
    //"2022-07-03-20-00"
    //20230103
    var today = new Date();
    var ndd = String(today.getDate()).padStart(2, '0');
    var nmm = String(today.getMonth() + 1).padStart(2, '0'); //January is 0!
    var nyyyy = today.getFullYear();

    today.setMonth(today.getMonth()-6)
    var odd = String(today.getDate()).padStart(2, '0');
    var omm = String(today.getMonth() + 1).padStart(2, '0'); //January is 0!
    var oyyyy = today.getFullYear();

    var now = nyyyy+nmm+ndd
    var old = oyyyy+omm+odd
    var u = "https://teletrader-apigateway.fxstreet.com/v1/priceProvider/PriceProviderHistory?request=HISTORY%20tts-170452990%20INTRADAY%20240%201000%20"+old+"%20"+now+"&dataLoader=ttws&timeZone=Etc%2FGMT&fxsCache=false&fxsCandleType=INTRADAY%20240"
    console.log(u)
    return u;
  };

  const stockUrlmaker = (stock, key="60") => {
    if(key < 0){
      var time1 = Math.round((new Date().getTime())/1000) - 364431
      var time2 = Math.round((new Date().getTime())/1000)
      var url = "https://priceapi.moneycontrol.com/techCharts/indianMarket/stock/history?symbol="+stock+"&resolution="+key+"&from="+time1+"&to="+time2+"&countback=329&currencyCode=INR"
      console.log(url)
      return url
    }


    var oldday = new Date();
    
    var url =""
    if(key == "5m"){
      oldday.setMonth(oldday.getMonth()-1)
      url = "https://query1.finance.yahoo.com/v7/finance/chart/"+stock+".NS?&interval=5m&period1="+(Math.round(oldday.getTime()/1000))+"&period2="+Math.round((new Date().getTime())/1000)
    }else if(key = 1000){

      var time1 = Math.round((new Date().getTime())/1000) - 57772677
      var time2 = Math.round((new Date().getTime())/1000)
      url = "https://query1.finance.yahoo.com/v7/finance/chart/"+stock+".NS?&interval=1d&period1="+time1+"&period2="+time2

    }else{
      oldday.setMonth(oldday.getMonth()-6)
      url = "https://query1.finance.yahoo.com/v7/finance/chart/"+stock+".NS?&interval=1h&period1="+Math.round(oldday.getTime()/1000)+"&period2="+Math.round((new Date().getTime())/1000)
    }
    return url
  }


const getStockData22 = async (stock, timeframe) =>{
  var klinedata = ''
  try {  
    var url = stockUrlmaker(stock, timeframe)
    const resp = await got(url)
    console.log(url);
    const d = JSON.parse(resp.body);
  
    klinedata = d["chart"]["result"][0]["timestamp"].map((itm,i) => ({
      time: itm, // 1000,
      open: d["chart"]["result"][0]["indicators"]["quote"][0]["open"][i] * 1,
      high: d["chart"]["result"][0]["indicators"]["quote"][0]["high"][i] * 1,
      low: d["chart"]["result"][0]["indicators"]["quote"][0]["low"][i] * 1,
      close: d["chart"]["result"][0]["indicators"]["quote"][0]["close"][i] * 1,
      volume : d["chart"]["result"][0]["indicators"]["quote"][0]["volume"][i]*1,
   })).filter((candle) => candle.volume !== 0);
   }catch (err) {
    console.log(err);
  }
  
  return klinedata
}




const get15mStockData = async (stock) =>{
  var klinedata = ''
  var newKlineData = [];
        try {  
          var url = stockUrlmaker(stock, "5m")
          console.log(url);
          const resp = await got(url)
          const d = JSON.parse(resp.body);
          
        
          klinedata = d["chart"]["result"][0]["timestamp"].map((itm,i) => ({
            time: itm, // 1000,
            open: d["chart"]["result"][0]["indicators"]["quote"][0]["open"][i] * 1,
            high: d["chart"]["result"][0]["indicators"]["quote"][0]["high"][i] * 1,
            low: d["chart"]["result"][0]["indicators"]["quote"][0]["low"][i] * 1,
            close: d["chart"]["result"][0]["indicators"]["quote"][0]["close"][i] * 1,
            volume : d["chart"]["result"][0]["indicators"]["quote"][0]["volume"][i]*1,
        })).filter((candle) => candle.volume !== 0);

        
        const interval = 3; // Number of 5-minute candles to combine into one 15-minute candle
        
        for (let i = 0; i < klinedata.length; i += interval) {
          const slice = klinedata.slice(i, i + interval);
        
          const time = slice[0].time; // Use the time of the first candle in the slice
          const open = slice[0].open; // Use the open price of the first candle in the slice
          const high = Math.max(...slice.map((candle) => candle.high)); // Find the highest high price within the slice
          const low = Math.min(...slice.map((candle) => candle.low)); // Find the lowest low price within the slice
          const close = slice[slice.length - 1].close; // Use the close price of the last candle in the slice
          const volume = slice.reduce((sum, candle) => sum + candle.volume, 0); // Sum the volumes within the slice
          newKlineData.push({ 
             time : time,
             open : open*1,
             high : high*1, 
             low : low*1, 
             close : close*1, 
             volume : volume*1});
        }
       
        }catch (err) {
          console.log(err);
        }
  
  return newKlineData
}





const stockOnetofour24 = (series) =>{
  //https://www.npmjs.com/package/candlestick-convert -- UUUUUUUU SSSSSSSSSSS EEEEEEEEE THIS
   try{  
    var len = series.length///4
    var lastel = series[series.length-1]
    //console.log(lastel)
    var ans = []
    series.push({"time":lastel["time"]+3600,"open":lastel["close"],"high":lastel["close"],"low":lastel["close"],"close":lastel["close"],"volume":0})
    series.push({"time":lastel["time"]+7200,"open":lastel["close"],"high":lastel["close"],"low":lastel["close"],"close":lastel["close"],"volume":0})
    series.push({"time":lastel["time"]+10800,"open":lastel["close"],"high":lastel["close"],"low":lastel["close"],"close":lastel["close"],"volume":0})
    series.push({"time":lastel["time"]+14400,"open":lastel["close"],"high":lastel["close"],"low":lastel["close"],"close":lastel["close"],"volume":0})
    var hg = Number.MIN_VALUE;
    var lw = Number.MAX_VALUE;

    for (let i = 0; i < len; i++) {
        if((series[i]["time"]%86400 == 13500)){
          ans.push({
            time : series[i]["time"],
            close : series[i+3]["close"],
            open : series[i]["open"],
            high : Math.max(series[i]["high"], series[i+1]["high"], series[i+2]["high"], series[i+3]["high"]),
            low  : Math.min(series[i]["low"], series[i+1]["low"], series[i+2]["low"], series[i+3]["low"]),
            volume : series[i]["volume"]+series[i+1]["volume"]+series[i+2]["volume"]+series[i+3]["volume"],
          })
        }
        if((series[i]["time"]%86400 == 27900)){
          ans.push({
            time : series[i]["time"],
            close : series[i+2]["close"],
            open : series[i]["open"],
            high : Math.max(series[i]["high"], series[i+1]["high"], series[i+2]["high"]),
            low  : Math.min(series[i]["low"], series[i+1]["low"], series[i+2]["low"]),
            volume : series[i]["volume"]+series[i+1]["volume"]+series[i+2]["volume"],
          })
        }
    } 
  }catch (err) {
    console.log(err)
    res.status(500).send(err);

  }
    //series = series.filter((d) =>{return (d["time"]%86400 == 14400) || (d["time"]%86400 == 28800)})
    return ans
}


const makeSTockGold = (klinedata) => {
  //"2022-07-03-20-00"
  var glinedata = []
  var k1 = klinedata[klinedata.length-1]["open"]
  var k2 = klinedata[klinedata.length-1]["goldo"]
  var investment = 50.0

  var n1 = investment/k1
  var n2 = investment/k2

  for (let i = 0; i < klinedata.length; i++) {
    var SUM = n1*(klinedata[i]["close"]-k1) - n2*(klinedata[i]["gold"]-k2)
    var SUMO = n1*(klinedata[i]["open"]-k1) - n2*(klinedata[i]["goldo"]-k2)
    var SUMH = n1*(klinedata[i]["high"]-k1) - n2*(klinedata[i]["goldh"]-k2)
    var SUML = n1*(klinedata[i]["low"]-k1) - n2*(klinedata[i]["goldl"]-k2)
    klinedata[i]["sgclose"] = SUM
    klinedata[i]["sgopen"]  = SUMO
    klinedata[i]["sglow"] = SUML
    klinedata[i]["sghigh"] = SUMH

    //glinedata.push({close:SUM , open:SUMO, high:SUMH, low:SUML, time:klinedata[i]["time"]})
  }

  //console.log(klinedata)
  return klinedata;
};


const getMsStockDataWeekly = async (stock, timeframe) =>{
  var klinedata = ''
  try {  

    const date = new Date();
    var currentdate  = `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;
    var olddate =`${date.getFullYear()-5}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;
    //console.log(currentdate+" "+olddate);


    var marketsmithid = getMarketSmithId(stock)

    var url = "https://msi-gcloud-prod.appspot.com/gateway/simple-api/ms-india/instr/0/"+marketsmithid+"/details.json?symbol="+stock+"&p=1&s="+olddate+"&e="+currentdate+"&b=0INNSE50&ie=0&iq=0&rs=N&em=0&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+231213210607+971796693"
    
    console.log(url);
    const resp = await got(url)
    const d = JSON.parse(resp.body);

    klinedata = d["chart"]["prices"].reverse().map((itm,i) => ({
      time: d["chart"]["prices"][i]["priceDate"] / 1000, // 1000,
      open: d["chart"]["prices"][i]["open"] * 1,
      high: d["chart"]["prices"][i]["high"] * 1,
      low: d["chart"]["prices"][i]["low"] * 1,
      close: d["chart"]["prices"][i]["close"] * 1,
      volume : d["chart"]["prices"][i]["volume"]*1,
   }));
  
   }catch (err) {
    console.log(err);
  }
  return klinedata
}


module.exports = {getFormattedTime, goldUrlmaker, getStockData22, get15mStockData, stockOnetofour24, makeSTockGold, getMarketSmithId, getMsStockDataWeekly}