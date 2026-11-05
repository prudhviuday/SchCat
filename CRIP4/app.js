const { log, error } = console;
const express = require('express');
const app = express();
const server = app.listen(3000, log('Proxy server is running on port 3000'));
const got = require('got');
const cors = require('cors');
const path    = require("path");
const tool = require('./public/Tools/fixer');
const globe = require('./public/Tools/globe');

app.use(express.static(path.join(__dirname, '/public/UI')));

//Tulind Functions
const {
  sma_inc,
  ema_inc,
  rsi_inc,
  ultm_inc,
} = require('./indicators');

app.use(cors());
app.get('/:symbol/:interval', async (req, res) => {
    const { symbol, interval } = req.params;
    try {    
        klinedata = []
        if(interval == 240){
          klinedata = await tool.getStockData22(symbol, interval);
          klinedata = tool.stockOnetofour24(klinedata)
        }else if(interval == 15){
          klinedata = tool.get15mStockData(symbol)
        }else{
          klinedata = await tool.getStockData22(symbol, interval);
        }
        
        //console.log(klinedata)
        klinedata = await sma_inc(klinedata, 50, "sma");
        klinedata = await ema_inc(klinedata, 50, "ema50");
        klinedata = await ema_inc(klinedata, 200, "ema200");
        klinedata = await rsi_inc(klinedata);
      //const gold = await globe.getGoldData();
       //klinedata = globe.stockGoldMerger2(klinedata, gold);
       // console.log(klinedata);
        klinedata = await ultm_inc(klinedata, 12, 120); //-----CHECK HERE AFTER
      //klinedata = tool.makeSTockGold(klinedata) //PFTG
      //klinedata = await ema_inc(klinedata, 50, "sgema50", "stcokgold");
      //klinedata = await ema_inc(klinedata, 200, "sgema200", "stcokgold");
        

        //var y = klinedata.map((d) => d.time)
        res.status(200).send(klinedata);
    } catch (err) {
      res.status(500).send(err);
      }
});

app.get('/:symbol/:interval/:sd/:bigsd/ai', async (req, res) => {
  const { symbol, interval, sd, bigsd } = req.params;
  try {    
      klinedata = []
      if(interval == 240){
        klinedata = await tool.getStockData22(symbol, interval);
        klinedata = tool.stockOnetofour24(klinedata)
      }else if(interval == 15){
        klinedata = tool.get15mStockData(symbol)
      }else{
        klinedata = await tool.getStockData22(symbol, interval);
      }
    
      klinedata = await ema_inc(klinedata, 50, "ema50");
      klinedata = await ema_inc(klinedata, 200, "ema200");

      const gold = await globe.getGoldData()
      klinedata = globe.stockGoldMerger2(klinedata, gold);
      klinedata = await ultm_inc(klinedata, sd, bigsd);
      klinedata = tool.makeSTockGold(klinedata)
      klinedata = await ema_inc(klinedata, 50, "sgema50", "stcokgold");
      klinedata = await ema_inc(klinedata, 200, "sgema200", "stcokgold");
      //console.log(klinedata)
      //klinedata = klinedata.map((d) =>  ({time : d["time"], ultm : d["ultm"],}))
      var response = ({ time : klinedata.map((d) => d.time), 
                        ultm : klinedata.map((d) => Math.round(d.ultm*100)/100), 
                        volume : klinedata.map((d) => d.volume),
                        
                        close : klinedata.map((d) => d.close),
                        open : klinedata.map((d) => d.open),
                        ema50 : klinedata.map((d) => d.ema50),
                        ema200 : klinedata.map((d) => d.ema200),

                        sgclose : klinedata.map((d) => d.sgclose),
                        sgopen : klinedata.map((d) => d.sgopen),
                        sgema50 : klinedata.map((d) => d.sgema50),
                        sgema200 : klinedata.map((d) => d.sgema200),
                      })
      res.status(200).send(response);
  } catch (err) {
    res.status(500).send(err);
    }
});


app.get('/:symbol/:interval/:sd/:bigsd/ultm', async (req, res) => {
  const { symbol, interval, sd, bigsd } = req.params;
  try {    
      klinedata = []
      if(interval == 240){
        klinedata = await tool.getStockData22(symbol, interval);
        klinedata = tool.stockOnetofour24(klinedata)
      }else if(interval == 15){
        klinedata = await tool.get15mStockData(symbol)
      }else if(interval == 1000){
        klinedata = await tool.getStockData22(symbol, "1d")
        console.log("requesting daily data")
      }else{
        klinedata = await tool.getStockData22(symbol, interval);
        
      }
    
      klinedata = await ultm_inc(klinedata, sd, bigsd);
      klinedata = await sma_inc(klinedata, 6, "sma5");
      klinedata = await ema_inc(klinedata, 50, "ema50");
      //console.log(klinedata)
      //klinedata = klinedata.map((d) =>  ({time : d["time"], ultm : d["ultm"],}))
      var response = ({ time : klinedata.map((d) => d.time),
                        ultm : klinedata.map((d) => Math.round(d.ultm*100)/100), 
                        close: klinedata.map((d) => Math.round(d.close*100)/100),
                        open: klinedata.map((d) => Math.round(d.open*100)/100),
                        //ema50: klinedata.map((d) => Math.round(d.ema50*100)/100),
                        volume : klinedata.map((d) => d.volume) 
                      })
      res.status(200).send(response);
  } catch (err) {
    res.status(500).send(err);
    }
});




app.get('/:symbol/:sd/:bigsd/weekultm', async (req, res) => {
  const { symbol, interval, sd, bigsd } = req.params;
  try {   
      klinedata = await tool.getMsStockDataWeekly(symbol, interval);
      console.log(sd+" "+bigsd)
      klinedata = await ema_inc(klinedata, 50, "ema50");
      klinedata = await ema_inc(klinedata, 200, "ema200");

    
      klinedata = await ultm_inc(klinedata, sd, bigsd);
      klinedata = tool.makeSTockGold(klinedata)
      
      
      //klinedata = klinedata.map((d) =>  ({time : d["time"], ultm : d["ultm"],}))
      var response = ({ time : klinedata.map((d) => d.time), 
                        ultm : klinedata.map((d) => Math.round(d.ultm*100)/100), 
                        volume : klinedata.map((d) => d.volume),
                        
                        close : klinedata.map((d) => d.close),
                        open : klinedata.map((d) => d.open),
                        ema50 : klinedata.map((d) => d.ema50),
                        ema200 : klinedata.map((d) => d.ema200),

                      })
      res.status(200).send(response);
  } catch (err) {
    res.status(500).send(err);
    }
});







app.get('/gold', async (req, res) => {
  try {
    const { symbol, interval } = req.params;
    const resp = await got(
      tool.goldUrlmaker()
    );
    const data = resp.body
    const result = data.split(/\r?\n/);
    result.shift()
    result.pop()
    //console.log(klinedata)
    var temp = result.map(d => d.split(';'))
    
    var goldkline = temp.map((d)=>({
      time: tool.getFormattedTime(d[0])-900, // 1000,
      open: d[1] * 1,
      high: d[2] * 1,
      low: d[3] * 1,
      close: d[4] * 1,
    }));

    goldkline = goldkline.filter((d) =>{return (d["time"]%86400 == 13500) || (d["time"]%86400 == 27900)})
  
    var y = goldkline.map((d) => d.time)
    res.status(200).send(goldkline);
  } catch (err) {
    res.status(500).send(err);
  }
});


app.get('/gold2', async (req, res) => {
  try {

    var response2 = await investing('currencies/eur-usd', 'P1M', 'P1D');

    console.log(response2)

    const data = resp.body
    const time = data["t"]
    var goldkline = time.map((d,i) => ({
      time: time[i],
      open : data["o"][i],
      high : data["h"][i],
      low : data["l"][i],
      close : data["c"][i],
    }))
    res.status(200).send(goldkline);
  } catch (err) {
    res.status(500).send(err);
  }
});

app.get('/intro', function(req, res) {
  const { symbol, interval} = req.params;
  res.sendFile(path.join(path.join(__dirname, '/public/UI'), '/index.html'));
});


app.get('/:symbol/:interval/:sd/:bigsd/weekultm', async (req, res) => {
  const { symbol, interval, sd, bigsd } = req.params;
  try {    
      klinedata = await tool.getStockData22(symbol, interval);
      
      klinedata = await ema_inc(klinedata, 50, "ema50");
      klinedata = await ema_inc(klinedata, 200, "ema200");

      const gold = await globe.getGoldData()
      klinedata = globe.stockGoldMerger2(klinedata, gold);
      klinedata = await ultm_inc(klinedata, sd, bigsd);
      klinedata = tool.makeSTockGold(klinedata)
      klinedata = await ema_inc(klinedata, 50, "sgema50", "stcokgold");
      klinedata = await ema_inc(klinedata, 200, "sgema200", "stcokgold");
      //console.log(klinedata)
      //klinedata = klinedata.map((d) =>  ({time : d["time"], ultm : d["ultm"],}))
      var response = ({ time : klinedata.map((d) => d.time), 
                        ultm : klinedata.map((d) => Math.round(d.ultm*100)/100), 
                        volume : klinedata.map((d) => d.volume),
                        
                        close : klinedata.map((d) => d.close),
                        open : klinedata.map((d) => d.open),
                        ema50 : klinedata.map((d) => d.ema50),
                        ema200 : klinedata.map((d) => d.ema200),

                        sgclose : klinedata.map((d) => d.sgclose),
                        sgopen : klinedata.map((d) => d.sgopen),
                        sgema50 : klinedata.map((d) => d.sgema50),
                        sgema200 : klinedata.map((d) => d.sgema200),
                      })
      res.status(200).send(response);
  } catch (err) {
    res.status(500).send(err);
    }
});