//import Url from "url";
const { log, error } = console;

//const tool = require('./public/Tools/fixer');
//const url = require('url');
//import path from "path";
var chart = null;
var chartProperties = null;
var candleseries = null;
var stockGoldSeries = null;
var sma_series = null;
var ema50_series = null;
var ema200_series = null;
var ultm_series = null;
var rsi_series = null;
var zero_series = null;
var klinedata = null;
var goldlinedata = null
var domElement = document.getElementById('tvchart');

const getData = async (stock) => {
  
  const link = window.location.href
  //alert(url.arguments)
  
  const resp = await fetch('http://127.0.0.1:3000/'+stock+'/60');
  const data = await resp.json();
  return data;
};

// getData();



const makeSTockGold = () => {
  //"2022-07-03-20-00"
  var glinedata = klinedata.map((d) => ({close : d.sgclose, open : d.sgopen, high: d.sghigh, low :d.sglow, time:d.time}))
  return glinedata;
};

const replaceStockToChart = async (stock) =>{
  chart.remove()
  renderChart(stock)

}

const initStockToChart = async (stock) =>{
  chartProperties = {
    timeScale: {
      timeVisible: true,
      secondsVisible: true,
    },
    pane: 0,
  };
  chart = LightweightCharts.createChart(domElement, chartProperties);

  candleseries = chart.addCandlestickSeries();
  sma_series = chart.addLineSeries({ color: 'red', lineWidth: 1 });
  ema50_series = chart.addLineSeries({ color: 'red', lineWidth: 1 });
  ema200_series = chart.addLineSeries({ color: 'green', lineWidth: 1 });
  ultm_series = chart.addLineSeries({ color: 'green', lineWidth: 1, pane: 2, });
  rsi_series = chart.addLineSeries({ color: 'purple', lineWidth: 1, pane: 1, });
  zero_series = chart.addLineSeries({ color: 'black', lineWidth: 1, pane: 2, });
  stockGoldSeries = chart.addCandlestickSeries({pane: 3, });
  sg50ema_series = chart.addLineSeries({ color: 'red', lineWidth: 1, pane: 3, });
  sg200ema_series = chart.addLineSeries({ color: 'green', lineWidth: 1, pane: 3, });
  
}

const workStockToChart = async (stock) =>{
  klinedata = await getData(stock);
  goldlinedata = await makeSTockGold();
  candleseries.setData(klinedata);
  stockGoldSeries.setData(goldlinedata);
  //SMA
  const sma_data = klinedata.filter((d) => d.sma).map((d) => ({ time: d.time, value: d.sma }));
  sma_series.setData(sma_data);
  
  //EMA
  const ema50_data = klinedata.filter((d) => d.ema50).map((d) => ({ time: d.time, value: d.ema50 }));
  const ema200_data = klinedata.filter((d) => d.ema200).map((d) => ({ time: d.time, value: d.ema200 }));
  ema50_series.setData(ema50_data);
  ema200_series.setData(ema200_data);

  //SG EMA
  const sgema50_data = klinedata.filter((d) => d.sgema50).map((d) => ({ time: d.time, value: d.sgema50 }));
  const sgema200_data = klinedata.filter((d) => d.sgema200).map((d) => ({ time: d.time, value: d.sgema200 }));
  sg50ema_series.setData(sgema50_data);
  sg200ema_series.setData(sgema200_data);

  //ULTM
  const ultm_data = klinedata.filter((d) => d.ultm).map((d) => ({ time: d.time, value: d.ultm }));
  ultm_series.setData(ultm_data);


  //zero series
  const zero_data = klinedata.filter((d) => d.ultm).map((d, i) => ({ time: d.time, value: i%2 }));
  zero_series.setData(zero_data);
  
  //RSI
  const rsi_data = klinedata.filter((d) => d.rsi).map((d) => ({ time: d.time, value: d.rsi }));
  rsi_series.setData(rsi_data);
  //ULTIM --MACD FAST
}

const addStockToChart = async (stock) =>{
  initStockToChart(stock)
  workStockToChart(stock)
}



const renderChart = async (stock) => {  
  addStockToChart(stock);
};

renderChart("ICICIBANK");
//replaceStockToChart("HDFCBANK")



var form = document.getElementById("stockform");
form.addEventListener("submit", function(event) {  
    event.preventDefault();
    var stock = document.getElementById("stock").value;
    replaceStockToChart(stock)
    alert(stock+" - added")
});
