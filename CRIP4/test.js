var http = require('http'); 

var serv = http.createServer(function (req, res) {  

    if (req.url == '/') { 
 

      const request = require('request');

      let url = "https://advcharts.investing.com/advinion2016/advanced-charts/56/56/23/GetRecentHistory?strSymbol=68&iTop=1500&strPriceType=bid&strFieldsMode=allFields&strExtraData=lang_ID=56&strTimeFrame=60M";
      
      let options = {json: true};
      
      
      
      request(url, options, (error, res, body) => {
          console.log("here "+res.statusCode)
          if (error) {
              return  console.log(error)
          };
      
          if (!error && res.statusCode == 200) {
              // do something with JSON, using the 'body' variable
              console.log(json+body);
          };
      });
      
      res.write("test ing it");
      res.end();
  
  }
});

serv.listen(5000); //3 - listen for any incoming requests

console.log('Node.js web server at port 5000 is running..')