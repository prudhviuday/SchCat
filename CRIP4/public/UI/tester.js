import urlParseLax from 'url-parse-lax';
const getData = async () => {
    const address = 'https://geeksforgeeks.org/projects?sort=newest&lang=nodejs';
    let urlObject = parse(address, true);
    console.log(urlObject)

    const link = window.location.href
    //alert(url.arguments)
    
    const resp = await fetch('http://127.0.0.1:3000/HDFCBANK/60');
    const data = await resp.json();
    return data;
  };
  
//getData();
