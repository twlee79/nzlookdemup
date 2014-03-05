function test3() {
  var outputDiv = document.getElementById("output");
  //outputDiv.innerText = "here";
  
  var xhr = new XMLHttpRequest();
  xhr.ontimeout = function () {
    console.error("The request timed out.");
  };
  
  xhr.onload = function() {
    if (xhr.readyState === 4) { 
      if (xhr.status === 200) {
        //outputDiv.innerText = xhr.responseText;
        outputDiv.innerHTML = "";
        var respBuffer = xhr.response; 
        if (respBuffer) {
          var view = new DataView(respBuffer);
          //console.log(respBuffer.byteLength);
          for (var i = 0; i < respBuffer.byteLength; i+=12) {
            var lat = view.getInt32(i)*1.0e-7;
            var lng = view.getInt32(i+4)*1.0e-7;
            var q = view.getInt32(i+8)*1.0e-3;
            outputDiv.innerHTML+=lat.toFixed(6)+","+lng.toFixed(6)+","+q.toFixed(1)+"<BR>";
            //var q = view.getInt32(i)*1.0e-3;
            //outputDiv.innerHTML+=q.toFixed(6);
          } 
        }
      }
    }
  };
  xhr.onerror = function (e) {
    console.error(xhr.statusText);
  };
  
  var url = "http://localhost:9080/process_binary";
  
  xhr.open("POST", url, true);
  //xhr.setRequestHeader('Content-Type', 'application/octet-stream');
  //xhr.setRequestHeader('Content-Type', 'text/plain');
  var buf = new ArrayBuffer(8*4);
  xhr.responseType = "arraybuffer";
  
  // float-32 will give precision of ~0.00002 at 180, this is around 2.2m
  //
  var dv = new DataView(buf);
  dv.setInt32(0,-36.885150*1e7);
  dv.setInt32(4,174.748030*1e7);
  
  dv.setInt32(8,-36.886430*1e7);
  dv.setInt32(12,174.753750*1e7);
  dv.setInt32(16,-36.885010*1e7);
  dv.setInt32(20,174.754221*1e7);
  dv.setInt32(24,-36.885345*1e7);
  dv.setInt32(28,174.755895*1e7);
  
  xhr.timeout = 5000;
  xhr.send(buf);
  
}


function test2() {
  var outputDiv = document.getElementById("output");
  //outputDiv.innerText = "here";
  
  var xhr = new XMLHttpRequest();
  xhr.ontimeout = function () {
    console.error("The request timed out.");
  };
  
  xhr.onload = function() {
    if (xhr.readyState === 4) { 
      if (xhr.status === 200) {
        //outputDiv.innerText = xhr.responseText;
        outputDiv.innerHTML = "";
        var respBuffer = xhr.response; 
        if (respBuffer) {
          var view = new DataView(respBuffer);
          //console.log(respBuffer.byteLength);
          for (var i = 0; i < respBuffer.byteLength; i+=12) {
            //var lat = view.getInt32(i)*1.0e-7;
            //var lng = view.getInt32(i+4)*1.0e-7;
            //var q = view.getInt32(i+8)*1.0e-3;
            //outputDiv.innerHTML+=lat.toFixed(6)+","+lng.toFixed(6)+","+q.toFixed(1)+"<BR>";
            var q = view.getInt32(i)*1.0e-3;
            outputDiv.innerHTML+=q.toFixed(6);
          } 
        }
      }
    }
  };
  xhr.onerror = function (e) {
    console.error(xhr.statusText);
  };
  
  var url = "http://localhost:9080/process_binary";
  
  xhr.open("POST", url, true);
  //xhr.setRequestHeader('Content-Type', 'application/octet-stream');
  //xhr.setRequestHeader('Content-Type', 'text/plain');
  var buf = new ArrayBuffer(2*4);
  xhr.responseType = "arraybuffer";
  
  // float-32 will give precision of ~0.00002 at 180, this is around 2.2m
  //
  var dv = new DataView(buf);
  dv.setInt32(0,-36.885150*1e7);
  dv.setInt32(4,174.748030*1e7);
  //dv.setInt32(8,-36.886430*1e7);
  //dv.setInt32(12,174.753750*1e7);
  
  xhr.timeout = 5000;
  xhr.send(buf);
  
}
function test() {
  var outputDiv = document.getElementById("output");
  //outputDiv.innerText = "here";
  
  var xhr = new XMLHttpRequest();
  xhr.ontimeout = function () {
    console.error("The request timed out.");
  };
  
  xhr.onload = function() {
    if (xhr.readyState === 4) { 
      if (xhr.status === 200) {
        outputDiv.innerText = xhr.responseText;
      } else {
        console.error(xhr.statusText);
      }
    }
  };
  xhr.onerror = function (e) {
    console.error(xhr.statusText);
  };
  
  var url = "http://localhost:9080/process_csv";
  
  xhr.open("POST", url, true);
  xhr.setRequestHeader('Content-Type', 'text/plain');
  xhr.timeout = 5000;
  xhr.send("#,latitude,longitude,type,dist\n0,-36.885150,174.748030,HOME,0.0\n1,-36.886430,174.753750,MANUAL,528.9\n");
  
}

window.onload = function(e){ 
 
  var testButton = document.getElementById("TestButton");
  testButton.addEventListener("click", test3, false);   
}

