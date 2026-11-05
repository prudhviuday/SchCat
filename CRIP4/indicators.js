// indicators.js
const { log, error } = console;
// replaced tulind with fast-technical-indicators
const fti = require('fast-technical-indicators');

const tool = require('./public/Tools/fixer');
const globe = require('./public/Tools/globe');
const { promisify } = require('util'); // kept for compatibility with your original structure

// --- Wrappers that mimic tulind's async API shape ---
// Original code awaited functions like: await sma_async([d1], [period]) and used results[0]
// These wrappers return the same shape: an array whose first element is the numeric array

const sma_async = async (inputs, params) => {
  const values = inputs && inputs[0] ? inputs[0] : [];
  const period = params && params[0] ? params[0] : 0;
  // fast-technical-indicators: SMA.calculate({ period, values })
  const res = fti.SMA.calculate({ period, values }) || [];
  return [res];
};

const ema_async = async (inputs, params) => {
  //console.log("inputs : " ,inputs)
  //console.log("params : " ,params)
  const values = inputs && inputs[0] ? inputs[0] : [];
  const period = params && params[0] ? params[0] : 0;
  const res = fti.EMA.calculate({ period, values }) || [];
  //console.log("[res] : " ,res)
  return [res];
};

const rsi_async = async (inputs, params) => {
  const values = inputs && inputs[0] ? inputs[0] : [];
  const period = params && params[0] ? params[0] : 14;
  const res = fti.RSI.calculate({ period, values }) || [];
  return [res];
};

// ----------------- your original functions (unchanged except tulind -> fti wrappers) -----------------



const rsi_inc = async (data) => {
  const d1 = data.map((d) => d.close);
  const d2 = (await rsi_async([d1], [21]))[0];
  //const d2 = results[0];
  const diff = data.length - d2.length;
  const emptyArray = [...new Array(diff)].map((d) => '');
  const d3 = [...emptyArray, ...d2];
  data = data.map((d, i) => ({ ...d, rsi: d3[i] }));
  return data;
};

const sma_inc = async (data, samplesize, key) => {
  const d1 = data.map((d) => d.close);
  const results = await sma_async([d1], [samplesize]);
  const d2 = results[0];
  const diff = data.length - d2.length;
  const emptyArray = [...new Array(diff)].map((d) => '');
  const d3 = [...emptyArray, ...d2];
  //data = data.map((d, i) => ({ ...d, sma: d3[i] }));
  data = eval("data.map((d, i) => ({ ...d, "+key+": d3[i] }));")
  return data;
};

const ema_inc = async (data, length, key, name="stock") => {
  var d1 = data.map((d) => d.close);
  if(name == "stcokgold")
      {d1 = data.map((d) => d.sgclose);}
  const results = await ema_async([d1], [length]);
  const d2 = results[0];
  //console.log("d2 ",d2)
  const diff = data.length - d2.length;
  const emptyArray = [...new Array(diff)].map((d) => '');
  const d3 = [...emptyArray, ...d2];
  //console.log("d3 ",d3)
  data = eval("data.map((d, i) => ({ ...d, "+key+": d3[i] }));")
  //console.log("key ",key)
  //console.log("data ",data)
  return data;
};

const touch_inc = async (data) => {
  const sgema50 = data.map((d) => d.sgema50);
  const sgema200 = data.map((d) => d.sgema200);
  const d2 = (await rsi_async([d1], [21]))[0];
  //const d2 = results[0];
  const diff = data.length - d2.length;
  const emptyArray = [...new Array(diff)].map((d) => '');
  const d3 = [...emptyArray, ...d2];
  data = data.map((d, i) => ({ ...d, rsi: d3[i] }));
  return data;
};


const ultm_inc = async (stockdata, SD, BigSD) => { 
  const stockclose = stockdata.map((d) => d.close);
  const semaSD = (await ema_async([stockclose], [SD]))[0];
  const semaBSD = (await ema_async([stockclose], [BigSD]))[0];

  var ATPs = semaSD.map((d, i) => (d/semaBSD[i])*100)
  
  var rev = ATPs.map((d, i) => d-100)//ATPg[i])
  var ratio = stockdata.map((d) => 1)
  var ultimator = ratio.map((d, i) => (d/rev[i])*123)
  ultimator[0]=ultimator[1]
  stockdata = stockdata.map((d, i) => ({ ...d, ultm: ultimator[i] }));
  
  return stockdata;
};

const ultm_incbkp = async (stockdata, SD, BigSD) => { 
  const golddata = stockdata.map((d) => d.gold) 
  const stockclose = stockdata.map((d) => d.close);
  const semaSD = (await ema_async([stockclose], [SD]))[0];
  const semaBSD = (await ema_async([stockclose], [BigSD]))[0];

  const gemaSD = (await ema_async([golddata], [SD]))[0];
  const gemaBSD = (await ema_async([golddata], [BigSD]))[0];
  //const ATPs = (semaSD/bemaSD)*100
  //console.log(gemaSD.length+" "+gemaBSD.length)
  var ATPs = semaSD.map((d, i) => (d/semaBSD[i])*100)
  var ATPg = gemaSD.map((d, i) => (d/gemaBSD[i])*100)

  var rev = ATPs.map((d, i) => d-100)//ATPg[i])
  rev[0] = 0.001
  var ratio = stockdata.map((d) => d["close"]/d["gold"])
  var ultimator = ratio.map((d, i) => d/rev[i])
  stockdata = stockdata.map((d, i) => ({ ...d, ultm: ultimator[i] }));

  return stockdata;
};

const ATP_inc = async (stockdata, SD, BigSD) => { 
  const golddata = stockdata.map((d) => d.gold) 
  const stockclose = stockdata.map((d) => d.close);
  const semaSD = (await ema_async([stockclose], [SD]))[0];
  const semaBSD = (await ema_async([stockclose], [BigSD]))[0];

  const gemaSD = (await ema_async([golddata], [SD]))[0];
  const gemaBSD = (await ema_async([golddata], [BigSD]))[0];
  //const ATPs = (semaSD/bemaSD)*100
  //console.log(gemaSD.length+" "+gemaBSD.length)
  var ATPs = semaSD.map((d, i) => (d/semaBSD[i])*100)
  var ATPg = gemaSD.map((d, i) => (d/gemaBSD[i])*100)
  //console.log(ATPs)
  stockdata = stockdata.map((d, i) => ({ ...d, ultmS: ATPs[i] }));
  stockdata = stockdata.map((d, i) => ({ ...d, ultmG: ATPg[i] }));

  //stockdata.map((d) => {d.push({key: "gold",value: dt[d["time"]]});})
  
  return stockdata;
};



module.exports = { sma_inc, ema_inc, rsi_inc, ATP_inc, ultm_inc };
