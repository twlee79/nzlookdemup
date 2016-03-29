# coding: utf-8

"""
nzlookdemup app
version 0.9-2
Copyright (c) 2014-2016 Tet Woo Lee
"""

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import csv
import logging
import webapp2
from nztm2000 import NZTM2000
import deminterpolater
import struct
import traceback
import json
import traceback
import re
from urlparse import urlparse

is_debug = True

class BaseHandler(webapp2.RequestHandler):
    pass
"""
Output data modes:
    json
    csv
        should this be just simple csv, or csv of input decorated with elevation?
        simple csv is probably adequate
    binary
    xml - don't implement yet
how to store output status? 
json 'status'
csv 
    if OK, just produce CSV
    if not OK, # status, message
binary: lead with status/newline

data input modes:
    GET url, ala google elevation
    POST binary
    POST csv, parse lat/lng or simple pairs
        how to tell apart? re match [0-9]+,[0-9]+ in first line = assume pairs,
        else assume 
    json? don't bother implementing for now
how to specify input mode? could use parameter when GETing

output modes:
locations
path, submodes:
    fixed # samples, ala google elevation, does not interpolate all original points in path
    fixed x distance, will interpolate all original points in path plus additional points every x distance
    'ideal' will return all significant elevation points in path

output modes and input data type not linked

estimated sizes (11 samples):
json: 1118 bytes, say 100 bytes/sample

limits:
?10MB per request = 100k for json
may be a limit of 10k elevation points/request


"""

class ResponseType:
    JSON = 'json'
    BINARY = 'binary'
    CSV = 'csv'

class ElevationRequestHandler(webapp2.RequestHandler):
    def __init__(self, request, response):
        # Set self.request, self.response and self.app.
        self.initialize(request, response)

        self.allowed_origin_hostnames = {'null' : True, 'localhost' : True}
            #: list of hostnames allowed to access this handler
        
        self.set_status_ok()
        self.response_type = None
        self.latlngs = []
        self.is_path = False
        self.samples = None
        self.stepsize = None
        self.results = []
    def handle_exception(self, exception, debug):
        logging.warning(exception)
        if isinstance(exception, webapp2.HTTPException):
            # If the exception is a HTTPException, let base class handle it
            webapp2.RequestHandler.handle_exception(self, exception, debug)
        else:
            # Otherwise, process as a response, which will return error to accordingly
            if not self.is_error:
                tb = traceback.format_exc()
                self.set_status_error("UNKNOWN_ERROR",str(exception),tb)
            self.process_response()
    def set_status_ok(self):
        self.is_error = False
        self.status = 'OK'
        self.error_message = None
        self.error_traceback = None
    def set_status_error(self,status,error_message=None,traceback=None):
        self.is_error = True
        self.status = status
        self.error_message = error_message
        self.error_traceback = traceback
    def set_default_headers(self):
        request_origin = self.request.headers['origin']
        request_hostname = urlparse(request_origin).hostname
        if request_hostname is None: request_hostname = 'null'
            # may get origin 'null' if opening file locally, this has no hostname
        if request_hostname in self.allowed_origin_hostnames:
            self.response.headers['Access-Control-Allow-Origin'] = request_origin
        self.response.headers['Access-Control-Allow-Headers'] = "Content-Type"
    def get(self):
        self.set_default_headers()
        self.process_request_path()

        # for GET, locations or path are provided in parameters
        locations_str = self.request.get("locations", default_value=None)
        path_str = self.request.get("path", default_value=None)
        try:
            if locations_str is not None: 
                latlngs_str = locations_str
                self.is_path = False
            elif path_str is not None: 
                latlngs_str = path_str
                self.is_path = True
            else:
                raise ValueError("no locations or path provided")
            locations = latlngs_str.split("|")
            for location in locations:
                lat,lng = location.split(",")
                lat = float(lat)
                lng = float(lng)
                if lat<-90.0 or lat>+90.0 or lng<-180.0 or lng>+180.0:
                    raise ValueError("lat or lng out of range")
                self.latlngs.append((lat,lng))

        except ValueError as e:
            self.set_status_error("INVALID_REQUEST","ValueError processing lat,lng coordinates: "+str(e))
            raise Exception() # propagate to handler, message above will be used in response
        
        self.process_default_params()
        self.generate_result()
        return self.process_response()
    """
    /elevation/binary, json, xml etc for output type
    
    For POST request, need to correctly set Content-Type in XMLHttpRequest
        application/octet-stream = binary
        text/csv = csv
        application/json = json
        etc.
        This will determine how to parse input.
    Setting Content-Type header will cause the browser to issue an OPTIONS 
    request first, need to respond to this correctly.

    Parameters with POST:
        type=path | locations (default)
        samples=number (optional, defaults to None)
        stepsize=number (optional, defaults to None)
    """
    def post(self):
        self.set_default_headers()
        self.process_request_path()
        try:
            if self.request.content_type=="application/octet-stream":
                # read binary data
                if self.request.content_length % 4 != 0:
                     raise ValueError("Expected data packed as 32-bit ints, got %i bytes."%self.request.content_length)
                num_packed_ints = self.request.content_length/4
                if num_packed_ints % 2 != 0:
                     raise ValueError("Expected pairs of input values, got %i."%num_packed_ints)

                unpacked_ints = struct.unpack('!%ii'%num_packed_ints, self.request.body)

                it = iter(unpacked_ints)
                for lat in it:
                    lng = next(it)
                    self.latlngs.append((lat*1.0e-7,lng*1.0e-7))
            elif self.request.content_type == "multipart/form-data":
                # read CSV data
                if self.request.POST.get("fileupload")=='':
                    # no file uploaded
                    content = self.request.get("content")
                else:
                    filename = self.request.POST.get("fileupload").filename
                    content = self.request.POST.get("fileupload").file.read()
                csv_data = content
                if re.match("\s*[\-+0-9.]+,\s*[\-+0-9.]+(?:[,\r\n])", csv_data):
                    # data is raw numbers with no headings
                    csv_reader = csv.reader(csv_data.splitlines())
                    for row in csv_reader:
                        if len(row)==0: continue
                        if len(row)<2: raise Exception("Less than 2 columns while reading plain CSV file")
                        latlng = (float(row[0]), float(row[1]))
                        self.latlngs.append(latlng)
                else:
                    # assume have headings, look for right columns
                    csv_reader = csv.DictReader(csv_data.splitlines())
                    lngname = latname = None
                    for fieldname in csv_reader.fieldnames:
                      if latname is None and (fieldname=='latitude' or fieldname=='lat'):
                        latname = fieldname
                      if lngname is None and (fieldname=='longitude' or fieldname=='lng'):
                        lngname = fieldname
                    if lngname is None or latname is None: 
                        raise Exception('Invalid CSV file, no lat/latitude or lng/longitude headings')
                    for row in csv_reader:
                        latlng = (float(row[latname]), float(row[lngname]))
                        self.latlngs.append(latlng)
            else:
                self.set_status_error("INVALID_REQUEST","Unknown input type")
        except ValueError as e:
            self.set_status_error("INVALID_REQUEST","ValueError processing lat,lng coordinates: "+str(e))
            raise Exception() # propagate to handler, message above will be used in response
        
        type_str = self.request.get("type", default_value="locations")
        if type_str=="path":
            self.is_path = True
        else:
            self.is_path = False
            
        self.process_default_params()
        self.generate_result()
        return self.process_response()

    def options(self):
        self.set_default_headers()
        return self.response
    def process_request_path(self):
        if self.request.path=="/elevation/binary":
            self.response_type = ResponseType.BINARY;
        elif self.request.path=="/elevation/json":
            self.response_type = ResponseType.JSON;
        elif self.request.path=="/elevation/csv":
            self.response_type = ResponseType.CSV;
        elif self.request.path=="/elevation/xml":
            # xml requests, not implemented
            self.abort(501)
        elif self.request.path=="/elevation":
            # used by form
            output_str = self.request.get("output", default_value=None)
            if output_str == "csv":
                self.response_type = ResponseType.CSV;
            elif output_str == "json":
                self.response_type = ResponseType.JSON;
            else:
                self.abort(501)
            
        else:
            # no other requests specified
            self.abort(404)
    def process_default_params(self):
        samples_str = self.request.get("samples")
        stepsize_str = self.request.get("stepsize")
        if samples_str != '':
            self.samples = int(samples_str)
            if self.samples == -1: self.samples = None
        else: self.samples = None

        if stepsize_str != '':
            self.stepsize = float(stepsize_str)
            if self.stepsize <= 0: self.stepsize = None
        else: self.stepsize = None
    def generate_result(self):
        try:
            if self.is_path:
                if self.samples is not None:
                    path = [NZTM2000.latlng_to_NZTM(*latlng) for latlng in self.latlngs]
                    track = deminterpolater.interpolate_path_bysamples(path, samples=self.samples)
                    for j,point in enumerate(track):
                        E, N, elevation = point
                        if j==0:
                            path_index = 0
                        elif j==len(track)-1:
                            path_index = len(self.latlngs)-1
                        else: path_index = None
                        lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                        self.results.append((lat,lng,elevation,path_index))
                else:
                    latlng2 = None
                    for i, latlng in enumerate(self.latlngs):
                        latlng1 = latlng2
                        latlng2 = latlng
                        if latlng1 is not None:
                            point1 = NZTM2000.latlng_to_NZTM(*latlng1)
                            point2 = NZTM2000.latlng_to_NZTM(*latlng2)
                            if self.stepsize is None:
                                track = deminterpolater.interpolate_line_smart(point1[0], point1[1], point2[0], point2[1])
                            else:
                                track = deminterpolater.interpolate_line_bysteps(point1[0], point1[1], point2[0], point2[1], stepsize=self.stepsize)
                            for j,point in enumerate(track):
                                E, N, elevation = point
                                if j==0:
                                    if i>1: continue
                                    path_index = i-1
                                elif j==len(track)-1:
                                    path_index = i
                                else: path_index = None
                                lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                                self.results.append((lat,lng,elevation,path_index))

            else:
                for i,latlng in enumerate(self.latlngs):
                    lat,lng = latlng
                    point1 = NZTM2000.latlng_to_NZTM(lat,lng)
                    elevation = deminterpolater.demset.interpolate_DEM(*point1)
                    self.results.append((lat,lng,elevation,i))
            self.set_status_ok()
        except (ValueError,IndexError) as e:
            # can get here if NZTM2000 out of range, or no DEM for coordinates
            tb = traceback.format_exc()
            self.set_status_error("INVALID_REQUEST","Error looking up DEM: "+str(e),tb)
    def process_response(self):
        if self.response_type == ResponseType.BINARY:
            return self.process_response_binary()
        elif self.response_type == ResponseType.JSON:
            return self.process_response_json()
        elif self.response_type == ResponseType.CSV:
            return self.process_response_csv()
        else:
            raise Exception("Unknown response type")
        
    def process_response_binary(self):
        if self.is_error:
            self.response.headers['Content-Type'] = 'text/plain'  
            self.response.out.write(self.status)
            self.response.out.write("\n")
            if self.error_message: self.response.out.write(self.error_message)
            self.response.out.write("\n")
            if self.error_traceback: self.response.out.write(self.error_traceback)
            self.response.out.write("\n")
        else:
            self.response.headers['Content-Type'] = 'application/octet-stream'  
            for result in self.results:
                lat,lng,elevation,path_index = result
                if path_index is None: path_index = -1
                self.response.write(struct.pack("!4i",lat*1e7,lng*1e7,elevation*1e3,path_index))
        #logging.debug(self.response)
        return self.response
        
            
    def process_response_json(self):
        response_dict = {
            'status': self.status}
        if self.error_message is not None: 
            response_dict['error_message'] = self.error_message
        if self.error_traceback is not None: 
            response_dict['traceback'] = self.error_traceback
        outresults = []
        for result in self.results:
            lat,lng,elevation,path_index = result
            outresult = {}
            outresult["elevation"] = elevation
            outresult["location"] = {"lat":lat,"lng":lng}
            if path_index is not None:
                outresult["path_index"] = path_index
            outresults.append(outresult)
        response_dict['results'] = outresults
        
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(response_dict, indent=4, sort_keys=True))                
        #logging.debug(self.response)
        return self.response
    
    def process_response_csv(self):
        self.response.headers['Content-Type'] = 'text/plain'  
        if self.is_error:
            self.response.out.write("#")
            self.response.out.write(self.status)
            self.response.out.write(",")
            if self.error_message: self.response.out.write(self.error_message)
            self.response.out.write(",")
            if self.error_traceback: self.response.out.write(self.error_traceback.replace("\n","   "))
            self.response.out.write("\n")
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write("lat,lng,elevation{}\n".format(',path_index' if self.is_path else ''))
            for result in self.results:
                lat,lng,elevation,path_index = result
                if path_index is None: path_index = ""
                self.response.write("{:.7f},{:.7f},{:.2f}{}\n".format(lat,lng,elevation, 
                    ',{}'.format(path_index) if self.is_path else ''))
        #logging.debug(self.response)
        return self.response


#Elevation Statuses

#OK indicating the service request was successful
#INVALID_REQUEST indicating the service request was malformed
#OVER_QUERY_LIMIT indicating that the requestor has exceeded quota
#REQUEST_DENIED indicating the service did not complete the request, likely because on an invalid parameter
#UNKNOWN_ERROR indicating an unknown error

# For advanced interpolation, should return an index or something to indicate original points


application = webapp2.WSGIApplication([
    ('/elevation',ElevationRequestHandler),
    ('/elevation/binary',ElevationRequestHandler),
    ('/elevation/csv',ElevationRequestHandler),
    ('/elevation/json',ElevationRequestHandler),
    ('/elevation/xml',ElevationRequestHandler)
   
], debug=is_debug)