// top-level namespace
var nztwlee = nztwlee || {};

// create nztwlee.demlookup namespace
nztwlee.demlookup = {};

// status values as per google.maps.ElevationStatus
nztwlee.demlookup.ElevationStatus = {
    OK : 'OK',
    INVALID_REQUEST : 'INVALID_REQUEST',
    OVER_QUERY_LIMIT : 'OVER_QUERY_LIMIT',
    REQUEST_DENIED : 'REQUEST_DENIED',
    UNKNOWN_ERROR : 'UNKNOWN_ERROR'
};

// constructor for ElevationService
nztwlee.demlookup.ElevationService = function () {
    this.lastErrorMessage = null;
};

nztwlee.demlookup.ElevationService.prototype.convertElevationStatusCode = function(statusCode) {
    switch (statusCode) {
        case 'OK':
            return nztwlee.demlookup.ElevationStatus.OK;
        case 'INVALID_REQUEST':
            return nztwlee.demlookup.ElevationStatus.INVALID_REQUEST;
        case 'OVER_QUERY_LIMIT':
            return nztwlee.demlookup.ElevationStatus.OVER_QUERY_LIMIT;
        case 'REQUEST_DENIED':
            return nztwlee.demlookup.ElevationStatus.REQUEST_DENIED;
        default:
            return nztwlee.demlookup.ElevationStatus.UNKNOWN_ERROR;
    }
};

nztwlee.demlookup.ElevationService.prototype.getElevationForLocations = function(request, callback) {
    this.sendElevationRequest(false,request,callback);
};

nztwlee.demlookup.ElevationService.prototype.getElevationAlongPath = function(request, callback) {
    this.sendElevationRequest(true,request,callback);
};
    
nztwlee.demlookup.ElevationService.prototype.sendElevationRequest = function(ispath, request, callback) {
    // 
    // LocationElevationRequest contains {locations[]: LatLng}
    // callback(results, status) where results is [] of ElevationResults and status is status
    // how to return extended error information?
  
    var xhr = new XMLHttpRequest();
    var self = this;
    
    callbackError = function(status,error_message) {
        elevationStatus = status;
        self.error_message = error_message;
        console.log("XHR Error, status :"+status+"\nmessage: "+error_message)
        callback(elevationResult,elevationStatus);
    }

    xhr.ontimeout = function () {
        callbackError(nztwlee.demlookup.ElevationStatus.UNKNOWN_ERROR,'XMLHttpRequest timeout');
    };

    xhr.onerror = function(e) {
        callbackError(nztwlee.demlookup.ElevationStatus.UNKNOWN_ERROR,'XMLHttpRequest error: '+e);
    };

    xhr.onreadystatechange = function() {
//        console.log("onrsc");
//        console.log(xhr.readyState);
//        console.log(xhr.status);
//        console.log(xhr.getResponseHeader('content-type'));
        if (xhr.readyState === 2) { // HEADERS_RECEIVED
            if (xhr.getResponseHeader('content-type')==="application/octet-stream") {
                xhr.responseType = "arraybuffer";
            }
        }
    };

    xhr.onload = function() {
            //console.log("onload");
            //console.log(xhr.readyState);
            //console.log(xhr.status);
            //console.log(xhr.getResponseHeader('content-type'));
            if (xhr.readyState === 4) { // DONE
                    if (xhr.status === 200) { // SUCCESS
                        if (xhr.responseType==="arraybuffer") {
                            // got binary data: OK response
                            var respBuffer = xhr.response;
                            if (!respBuffer) {
                                callbackError(nztwlee.demlookup.ElevationStatus.UNKNOWN_ERROR,'Invalid response buffer');
                            }
                            var respView = new DataView(respBuffer);
                            var parsedData = [];
                            for (var i = 0; i < respBuffer.byteLength; i += 16) {
                                
                                var lat = respView.getInt32(i)*1.0e-7;
                                var lng = respView.getInt32(i+4)*1.0e-7;
                                var q = respView.getInt32(i+8)*1.0e-3;
                                var index = respView.getInt32(i+12);
                                var latLng = new google.maps.LatLng(lat,lng);
                                var result = {location:latLng, elevation:q};
                                parsedData.push(result);
                                //latLng.height = q;
                                //latLng.index = index;
                                //console.log(i,lat,lng,q,index);
                                //parsedData.push(latLng);
                            }
                            callback(parsedData,nztwlee.demlookup.ElevationStatus.OK);
                                    
                        } else {
                            // non-binary data: error
                            responseStrings = xhr.responseText.split('\n');
                            var elevationStatus = self.convertElevationStatusCode(responseStrings[0]);
                            var error_message = responseStrings[1];
                            var traceback = responseStrings[2];
                            callbackError(elevationStatus,error_message);
                            
                        }
                    } else {
                        callbackError(nztwlee.demlookup.ElevationStatus.UNKNOWN_ERROR,'XMLHttpRequest failure');
                    }
            }
    };

    // set up request
    //var url = "http://localhost:9080/elevation/binary";
    var url = "https://nz-twlee-demlookup.appspot.com/elevation/binary";

    var pointArray;
    if (ispath) {
        if (!(request.path instanceof Array)) { 
            callbackError(nztwlee.demlookup.ElevationStatus.INVALID_REQUEST,
                          'Request object does not contain an path array');
        }
        url = url + "?type=path";
        if (request.samples) url = url + "&samples=" + request.samples;
        else if (request.stepsize) url = url + "&stepsize=" + request.stepsize;
        pointArray = request.path;
    } else {
        if (!(request.locations instanceof Array)) { 
            callbackError(nztwlee.demlookup.ElevationStatus.INVALID_REQUEST,
                          'Request object does not contain an array of locations');
        }
        url = url + "?type=locations";
        pointArray = request.locations;
    }
    
    // for storing results
    var elevationResult = [];
    var elevationStatus = nztwlee.demlookup.ElevationStatus.OK;
    this.lastErrorMessage = null;
    
    // process input data
    var numPoints = pointArray.length;
    var reqBuffer = new ArrayBuffer(numPoints * 8);
    var reqView = new DataView(reqBuffer);
    for (var i=0; i<numPoints; i++) {
        // pack as 32-bit ints, after multiplying by 1e7
        var latLng = pointArray[i];
        reqView.setInt32(i*8, latLng.lat * 1.0e7);
        reqView.setInt32(i*8 + 4, latLng.lng * 1.0e7);
    }
    
    // send request
    xhr.open("POST", url, true);
    xhr.timeout = 30000;
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.send(reqBuffer);

};