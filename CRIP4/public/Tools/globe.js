const getGoldData = async () => {
    const resp = await fetch('http://127.0.0.1:3000/gold');
    const data = await resp.json();
    return data;
  };


  const stockGoldMerger2 = (stock, gold) => {
    try{
        const tgold = {}
        for(let z=0; z<gold.length;z++){
          tgold[gold[z]["time"]] = [gold[z]["open"], gold[z]["high"], gold[z]["low"], gold[z]["close"]]
        }

        for(let i=0; i<stock.length; i++){
            if(tgold[stock[i]["time"]] !== undefined){
              stock[i]["goldo"] = tgold[stock[i]["time"]][0]
              stock[i]["goldh"] = tgold[stock[i]["time"]][1]
              stock[i]["goldl"] = tgold[stock[i]["time"]][2]
              stock[i]["gold"]  = tgold[stock[i]["time"]][3]
            }
            if(stock[i]["gold"] == undefined){
              if(i==0){
                stock[i]["goldo"] = gold[0]["open"]
                stock[i]["goldh"] = gold[0]["high"]
                stock[i]["goldl"] = gold[0]["low"]
                stock[i]["gold"]  = gold[0]["close"]
              }else{
                stock[i]["goldo"] = stock[i-1]["goldo"]
                stock[i]["goldh"] = stock[i-1]["goldh"]
                stock[i]["goldl"] = stock[i-1]["goldl"]
                stock[i]["gold"]  = stock[i-1]["gold"]
              }
            }
        }
    }catch (err) { console.log(err);}
    //console.log(tgold);
    return stock;
  };


module.exports = {getGoldData, stockGoldMerger2,}