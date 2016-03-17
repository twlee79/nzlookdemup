import csv
import itertools
import logging
import webapp2
from nztm2000 import NZTM2000
import deminterpolater
import struct
import traceback
import cloudstorage
import os
from google.appengine.api import app_identity
import sys
import json
import traceback
import re

#is_devserver = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

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

        self.response_dict = {}
        self.set_status_ok()
        self.response_type = None
        self.latlngs = []
    def handle_exception(self, exception, debug):
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
        self.response_dict['status'] = 'OK'
    def set_status_error(self,status,error_message=None,traceback=None):
        self.is_error = True
        self.response_dict['status'] = status
        if error_message is not None: self.response_dict['error_message'] = error_message
        if traceback is not None: self.response_dict['traceback'] = traceback
    def set_default_headers(self):
        self.response.headers['Access-Control-Allow-Origin'] = 'null'
        self.response.headers['Access-Control-Allow-Headers'] = "Content-Type"
    def get(self):
        self.set_default_headers()
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
        type_str = self.request.get("type", default_value="locations")
        samples_str = self.request.get("samples", default_value=None)
        stepsize_str = self.request.get("stepsize", default_value=None)
        try:
            if self.request.content_type=="application/octet-stream":
                self.read_binary()
            else:
                self.set_status_error("INVALID_REQUEST","Unknown input type")
        except ValueError as e:
            self.set_status_error("INVALID_REQUEST","ValueError processing lat,lng coordinates: "+str(e))
            raise Exception() # propagate to handler, message above will be used in response
        
        if type_str=="path":
            is_path = True
        else:
            is_path = False
            
        if samples_str is not None:
            samples = int(samples_str)
            if samples == -1: samples = None
        else: samples = None

        if stepsize_str is not None:
            stepsize = float(stepsize_str)
            if stepsize == -1: stepsize = None
        else: stepsize = None
            
        try:
            results = []
            if is_path:
                if samples is not None:
                    path = [NZTM2000.latlng_to_NZTM(*latlng) for latlng in self.latlngs]
                    track = deminterpolater.interpolate_path_simple(path, samples=samples)
                    for point in track:
                        result = {}
                        E, N, elevation, index = point
                        if index==0:
                            lat,lng = self.latlngs[0]
                        elif index==samples-1:
                            lat,lng = self.latlngs[-1]
                        else:
                            lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                        result["elevation"] = elevation
                        result["location"] = {"lat":lat,"lng":lng}
                        results.append(result)
                else:
                    latlng2 = None
                    for i, latlng in enumerate(self.latlngs):
                        latlng1 = latlng2
                        latlng2 = latlng
                        if latlng1 is not None:
                            point1 = NZTM2000.latlng_to_NZTM(*latlng1)
                            point2 = NZTM2000.latlng_to_NZTM(*latlng2)
                            track = deminterpolater.interpolate_line_ideal(point1[0], point1[1], point2[0], point2[1])
                            for point in track:
                                result = {}
                                E, N, elevation, index = point
                                if index==0:
                                    #if i>1: continue
                                    #lat,lng = latlng1
                                    result["path_index"] = i-1
                                elif index<0:
                                    #lat,lng = latlng2
                                    result["path_index"] = i

                                lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                                result["elevation"] = elevation
                                result["location"] = {"lat":lat,"lng":lng}
                                results.append(result)

            else:
                for latlng in self.latlngs:
                    lat,lng = latlng
                    point1 = NZTM2000.latlng_to_NZTM(lat,lng)
                    elevation = deminterpolater.demset.interpolate_DEM(*point1)
                    result = {}
                    result["elevation"] = elevation
                    result["location"] = {"lat":lat,"lng":lng}
                    results.append(result)
            self.response_dict['results']=results
            self.set_status_ok()
        except (ValueError,IndexError) as e:
            # can get here if NZTM2000 out of range, or no DEM for coordinates
            tb = traceback.format_exc()
            self.set_status_error("INVALID_REQUEST","Error looking up DEM: "+str(e),tb)
        
        return self.process_response()

    def options(self):
        self.set_default_headers()
        return self.response
    def read_csv(self):
        pass
    
    def read_binary(self):
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
        logging.debug(self.latlngs)
    def process_request_path(self):
        if self.request.path=="/elevation/binary":
            self.response_type = ResponseType.BINARY;
        elif self.request.path=="/elevation/json":
            self.response_type = ResponseType.JSON;
        elif self.request.path=="/elevation/xml":
            # xml requests, not implemented
            self.abort(501)
        else:
            # no other requests specified
            self.abort(404)
    def default(self):
        if self.request.path=="/elevation/json":
            pass
        elif self.request.path=="/elevation/xml":
            # xml requests, not implemented
            self.abort(501)
        else:
            # no other requests specified
            self.abort(404)

        
        locations_str = self.request.get("locations", default_value=None)
        path_str = self.request.get("path", default_value=None)
        samples_str = self.request.get("samples", default_value=None)
        latlngs = []
        try:
            if locations_str is not None: 
                latlngs_str = locations_str
                is_path = False
            elif path_str is not None: 
                latlngs_str = path_str
                is_path = True
            else:
                raise ValueError("no locations or path provided")
            locations = latlngs_str.split("|")
            for location in locations:
                lat,lng = location.split(",")
                lat = float(lat)
                lng = float(lng)
                if lat<-90.0 or lat>+90.0 or lng<-180.0 or lng>+180.0:
                    raise ValueError("lat or lng out of range")
                latlngs.append((lat,lng))
            if samples_str is not None:
                samples = int(samples_str)
                if samples == -1: samples = None
            else: samples = None

        except ValueError as e:
            self.set_status_error("INVALID_REQUEST","ValueError processing lat,lng coordinates: "+str(e))
        except Exception as e:
            tb = traceback.format_exc()
            self.set_status_error("UNKNOWN_ERROR",str(e),tb)
        
        if not self.is_error:
            try:
                results = []
                if is_path:
                    if samples is not None:
                        path = [NZTM2000.latlng_to_NZTM(*latlng) for latlng in latlngs]
                        track = deminterpolater.interpolate_path_simple(path, samples=samples)
                        for point in track:
                            result = {}
                            E, N, elevation, index = point
                            if index==0:
                                lat,lng = latlngs[0]
                            elif index==samples-1:
                                lat,lng = latlngs[-1]
                            else:
                                lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                            result["elevation"] = elevation
                            result["location"] = {"lat":lat,"lng":lng}
                            results.append(result)
                    else:
                        latlng2 = None
                        for i, latlng in enumerate(latlngs):
                            latlng1 = latlng2
                            latlng2 = latlng
                            if latlng1 is not None:
                                point1 = NZTM2000.latlng_to_NZTM(*latlng1)
                                point2 = NZTM2000.latlng_to_NZTM(*latlng2)
                                track = deminterpolater.interpolate_line_ideal(point1[0], point1[1], point2[0], point2[1])
                                for point in track:
                                    result = {}
                                    E, N, elevation, index = point
                                    if index==0:
                                        #if i>1: continue
                                        #lat,lng = latlng1
                                        result["path_index"] = i-1
                                    elif index<0:
                                        #lat,lng = latlng2
                                        result["path_index"] = i

                                    lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                                    result["elevation"] = elevation
                                    result["location"] = {"lat":lat,"lng":lng}
                                    results.append(result)

                else:
                    for latlng in latlngs:
                        lat,lng = latlng
                        point1 = NZTM2000.latlng_to_NZTM(lat,lng)
                        elevation = deminterpolater.demset.interpolate_DEM(*point1)
                        result = {}
                        result["elevation"] = elevation
                        result["location"] = {"lat":lat,"lng":lng}
                        results.append(result)
                self.response_dict['results']=results
                self.set_status_ok()
            except (ValueError,IndexError) as e:
                # can get here if NZTM2000 out of range, or no DEM for coordinates
                tb = traceback.format_exc()
                self.set_status_error("INVALID_REQUEST","Error looking up DEM: "+str(e),tb)
            except Exception as e:
                tb = traceback.format_exc()
                self.set_status_error("UNKNOWN_ERROR",str(e),tb)
            
        response = webapp2.Response()
        response.headers['Content-Type'] = 'application/json'   
        response.out.write(json.dumps(self.response_dict))                
        
        return response
    def process_response(self):
        if self.response_type == ResponseType.BINARY:
            return self.process_response_binary()
        elif self.response_type == ResponseType.JSON:
            return self.process_response_json()
        else:
            raise Exception("Unknown response type")
        
    def process_response_binary(self):
        if self.is_error:
            self.response.headers['Content-Type'] = 'text/plain'  
            self.response.out.write(self.response_dict.get('status',''))
            self.response.out.write("\n")
            self.response.out.write(self.response_dict.get('error_message',''))
            self.response.out.write("\n")
            self.response.out.write(self.response_dict.get('traceback',''))
            self.response.out.write("\n")
        else:
            self.response.headers['Content-Type'] = 'application/octet-stream'  
            if 'results' in self.response_dict:
                for result in self.response_dict['results']:
                    elevation = result["elevation"]
                    lat = result["location"]["lat"]
                    lng = result["location"]["lat"]
                    path_index = result.get("path_index",-1)
                    self.response.write(struct.pack("!4i",lat*1e7,lng*1e7,elevation*1e3,path_index))
        logging.debug(self.response)
        return self.response
        
            
    def process_response_json(self):
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(self.response_dict))                
        logging.debug(self.response)
        return self.response
    
    def process_response_csv(self):
        # return
        pass


class UploadForm(BaseHandler):
    def get(self):
        self.response.write("Not implemented")

class ProcessCSV(BaseHandler):
##    def handle_exception(self, exception, debug):
##        # Log the error.
##        logging.exception(exception)
##
##        # Set a custom message.
##        self.response.write('An error occurred : {}'.format(exception.message))
##
##        if isinstance(exception, webapp2.HTTPException):
##            # If the exception is a HTTPException, use its error code.
##            self.response.set_status(exception.code)
##        elif isinstance(exception, ValueError) or isinstance(exception, IndexError):
##            # Use 422 for errors due to requests outside DEM range
##            self.response.set_status(422)
##        else:
##            # 400 for improper request data
##            self.response.set_status(400)

    def options(self):
        self.response.headers['Access-Control-Allow-Origin'] = 'null'
        self.response.headers['Access-Control-Allow-Headers'] = 'content-type'
    def post(self):
    #self.response.headers['Access-Control-Allow-Origin'] = 'null'
        #self.response.write(self.request.headers)
        #self.response.write(self.request.body)
        #return
        if self.request.content_type == "text/plain":
          csv_data = self.request.body
        elif self.request.content_type == "application/x-www-form-urlencoded":
          csv_data = self.request.get('content')
        else:
          raise Exception("Invalid input.")
        csv_reader = csv.DictReader(csv_data.splitlines())
        #self.response.write(csv_reader.fieldnames)
        point1 = point2 = None
        #output = ''
        #cumul_dist = 0.0
        lngname = latname = None
        for fieldname in csv_reader.fieldnames:
          if latname is None and (fieldname=='latitude' or fieldname=='lat'):
            latname = fieldname
          if lngname is None and (fieldname=='longitude' or fieldname=='lng'):
            lngname = fieldname
        if lngname is None or latname is None: raise Exception('Invalid CSV file')

        all_tracks = []
        last_item = None

        for i,row in enumerate(csv_reader):
          latlng = (float(row[latname]), float(row[lngname]))
          point2 = NZTM2000.latlng_to_NZTM(*latlng)
          if point1 is not None:
            #print "Got segment: {}-{}".format(point1, point2)
            dE = point2[0]-point1[0]
            dN = point2[1]-point1[1]
            dist = (dE**2 + dN**2) ** 0.5
            track = deminterpolater.interpolate_line_ideal(point1[0], point1[1], point2[0], point2[1])
            #print 'first', point1, demset.interpolate_DEM(*point1)
            #print ",".join(reader.dem_path for reader in demset.active_reader_list)
            last_item_index = len(track)-1
            for item in itertools.islice(track,last_item_index):
              all_tracks.append(item) # don't add immediately last item, as it repeats with first from next
            last_item = track[last_item_index] # store for possibly adding to end
              #output+="%.2f\t%.2f\t%.3f\t%.3f\t%r\t%r\t%r"%item
              #output+='\t%f\n'%cumul_dist
              #print 'track', item

            #print 'second', point2, demset.interpolate_DEM(*point2)
            #cumul_dist+=dist
            
          point1 = point2
        all_tracks.append(last_item)
        print "Generating response"
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write("lat,lng,elev\n")
        for item in all_tracks:
          latlng = NZTM2000.NZTM_to_latlng(item[0],item[1])
          self.response.write("{:.6f},{:.6f},{:.1f}\n".format(latlng[0],latlng[1],item[2]))
          #if len(item)>3:
          #  self.response.write(item[3])
        print "done"
        sys.stdout.flush()

class ProcessBinary(BaseHandler):
    def handle_exception(self, exception, debug):
        # Log the error.
        logging.exception(exception)

        # Set a custom message.
        self.response.write('An error occurred : {}'.format(exception.message))
        self.response.write(traceback.format_exc())


        if isinstance(exception, webapp2.HTTPException):
            # If the exception is a HTTPException, use its error code.
            self.response.set_status(exception.code)
        elif isinstance(exception, ValueError) or isinstance(exception, IndexError):
            # Use 422 for errors due to requests outside DEM range
            self.response.set_status(422)
        else:
            # 400 for improper request data
            self.response.set_status(400)

##    def options(self): # needed if receing content type apart from application/x-www-form-urlencoded, multipart/form-data, or text/plain.
##        self.response.headers['Access-Control-Allow-Origin'] = 'null'
##        self.response.headers['Access-Control-Allow-Headers'] = 'content-type'
    def post(self):
        self.response.headers['Access-Control-Allow-Origin'] = 'null'
        expected_ints = self.request.content_length/4
        if expected_ints!=2 and expected_ints%4 != 0:
             raise Exception("Expected two input values or in multiples of 4, got %i."%expected_ints)
        num_pairs = expected_ints/2

        input_values = struct.unpack('!%ii'%expected_ints, self.request.body)

        full_track = [] # whole track for all points

        self.response.headers['Content-Type'] = 'application/octet-stream'
        if expected_ints == 2:
          # single point requested, interpolate it and return height
          latlng1 = (input_values[0]*1.0e-7,input_values[1]*1.0e-7)
          point1 = NZTM2000.latlng_to_NZTM(*latlng1)
          q = deminterpolater.demset.interpolate_DEM(*point1)
          self.response.write(struct.pack("!i",q*1e3))
          return
        for i in xrange(0,expected_ints,4):
          latlng1 = (input_values[i+0]*1.0e-7,input_values[i+1]*1.0e-7)
          latlng2 = (input_values[i+2]*1.0e-7,input_values[i+3]*1.0e-7)
          point1 = NZTM2000.latlng_to_NZTM(*latlng1)
          point2 = NZTM2000.latlng_to_NZTM(*latlng2)
          dE = point2[0]-point1[0]
          dN = point2[1]-point1[1]
          dist = (dE**2 + dN**2) ** 0.5
          track = deminterpolater.interpolate_line_ideal(point1[0], point1[1], point2[0], point2[1])
          full_track += track

        for item in full_track:
          index = item[3]
          latlng = NZTM2000.NZTM_to_latlng(item[0],item[1])
          self.response.write(struct.pack("!4i",latlng[0]*1e7,latlng[1]*1e7,item[2]*1e3,item[3]))

class LookupDEM(BaseHandler):
    pass

#set0_E = 1012007.5 # central coordinate of top-left pixel in DEM set
#set0_N = 6233992.5
#voxelE = 15.0 # voxel sizes in DEM set
#voxelN = -15.0
# x and y defined in terms of these coordinates

class TestGCS(BaseHandler):
    def get(self):
        bucket_name = '/'+os.environ.get('BUCKET_NAME',
                                 app_identity.get_default_gcs_bucket_name())
        self.list_bucket(bucket_name)
    def list_bucket(self, bucket):
      """Create several files and paginate through them.

      Production apps should set page_size to a practical value.

      Args:
        bucket: bucket.
      """
      self.response.write(bucket+' Listbucket result:\n')

      page_size = 1
      stats = cloudstorage.listbucket(bucket + '/', max_keys=page_size)
      while True:
        count = 0
        for stat in stats:
          count += 1
          self.response.write(repr(stat))
          self.response.write('\n')

        if count != page_size or count == 0:
          break
        # pylint: disable=undefined-loop-variable
        stats = cloudstorage.listbucket(bucket + '/', max_keys=page_size,
                               marker=stat.filename)

#Elevation Statuses

#OK indicating the service request was successful
#INVALID_REQUEST indicating the service request was malformed
#OVER_QUERY_LIMIT indicating that the requestor has exceeded quota
#REQUEST_DENIED indicating the service did not complete the request, likely because on an invalid parameter
#UNKNOWN_ERROR indicating an unknown error

# For advanced interpolation, should return an index or something to indicate original points

class ElevationGet(webapp2.RequestHandler):
    def __init__(self, request, response):
        # Set self.request, self.response and self.app.
        self.initialize(request, response)

        self.response_dict = {}
        self.is_error = False
    def set_status_ok(self):
        self.is_error = False
        self.response_dict['status'] = 'OK'
    def set_status_error(self,status,error_message=None,traceback=None):
        self.is_error = True
        self.response_dict['status'] = status
        if error_message is not None: self.response_dict['error_message'] = error_message
        if traceback is not None: self.response_dict['traceback'] = traceback
    def get(self):
        if self.request.path=="/elevation/json":
            pass
        elif self.request.path=="/elevation/xml":
            # xml requests, not implemented
            self.abort(501)
        else:
            # no other requests specified
            self.abort(404)

        
        locations_str = self.request.get("locations", default_value=None)
        path_str = self.request.get("path", default_value=None)
        samples_str = self.request.get("samples", default_value=None)
        latlngs = []
        try:
            if locations_str is not None: 
                latlngs_str = locations_str
                is_path = False
            elif path_str is not None: 
                latlngs_str = path_str
                is_path = True
            else:
                raise ValueError("no locations or path provided")
            locations = latlngs_str.split("|")
            for location in locations:
                lat,lng = location.split(",")
                lat = float(lat)
                lng = float(lng)
                if lat<-90.0 or lat>+90.0 or lng<-180.0 or lng>+180.0:
                    raise ValueError("lat or lng out of range")
                latlngs.append((lat,lng))
            if samples_str is not None:
                samples = int(samples_str)
                if samples == -1: samples = None
            else: samples = None

        except ValueError as e:
            self.set_status_error("INVALID_REQUEST","ValueError processing lat,lng coordinates: "+str(e))
        except Exception as e:
            tb = traceback.format_exc()
            self.set_status_error("UNKNOWN_ERROR",str(e),tb)
        
        if not self.is_error:
            try:
                results = []
                if is_path:
                    if samples is not None:
                        path = [NZTM2000.latlng_to_NZTM(*latlng) for latlng in latlngs]
                        track = deminterpolater.interpolate_path_simple(path, samples=samples)
                        for point in track:
                            result = {}
                            E, N, elevation, index = point
                            if index==0:
                                lat,lng = latlngs[0]
                            elif index==samples-1:
                                lat,lng = latlngs[-1]
                            else:
                                lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                            result["elevation"] = elevation
                            result["location"] = {"lat":lat,"lng":lng}
                            results.append(result)
                    else:
                        latlng2 = None
                        for i, latlng in enumerate(latlngs):
                            latlng1 = latlng2
                            latlng2 = latlng
                            if latlng1 is not None:
                                point1 = NZTM2000.latlng_to_NZTM(*latlng1)
                                point2 = NZTM2000.latlng_to_NZTM(*latlng2)
                                track = deminterpolater.interpolate_line_ideal(point1[0], point1[1], point2[0], point2[1])
                                for point in track:
                                    result = {}
                                    E, N, elevation, index = point
                                    if index==0:
                                        #if i>1: continue
                                        #lat,lng = latlng1
                                        result["path_index"] = i-1
                                    elif index<0:
                                        #lat,lng = latlng2
                                        result["path_index"] = i

                                    lat,lng = NZTM2000.NZTM_to_latlng(E,N)
                                    result["elevation"] = elevation
                                    result["location"] = {"lat":lat,"lng":lng}
                                    results.append(result)

                else:
                    for latlng in latlngs:
                        lat,lng = latlng
                        point1 = NZTM2000.latlng_to_NZTM(lat,lng)
                        elevation = deminterpolater.demset.interpolate_DEM(*point1)
                        result = {}
                        result["elevation"] = elevation
                        result["location"] = {"lat":lat,"lng":lng}
                        results.append(result)
                self.response_dict['results']=results
                self.set_status_ok()
            except (ValueError,IndexError) as e:
                # can get here if NZTM2000 out of range, or no DEM for coordinates
                tb = traceback.format_exc()
                self.set_status_error("INVALID_REQUEST","Error looking up DEM: "+str(e),tb)
            except Exception as e:
                tb = traceback.format_exc()
                self.set_status_error("UNKNOWN_ERROR",str(e),tb)
            
        response = webapp2.Response()
        response.headers['Content-Type'] = 'application/json'   
        response.out.write(json.dumps(self.response_dict))                
        
        return response

application = webapp2.WSGIApplication([
    ('/', UploadForm),
    ('/process_csv', ProcessCSV),
    ('/process_binary', ProcessBinary),
    ('/test_gcs', TestGCS),
    ('/elevation/json',ElevationGet),
    ('/elevation/xml',ElevationGet),
    ('/elevation/binary',ElevationRequestHandler)
    
], debug=True)