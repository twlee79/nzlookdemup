import cgi
import csv
import itertools
import logging
import webapp2
from nztm2000 import NZTM2000
import deminterpolater
import struct
import traceback

class BaseHandler(webapp2.RequestHandler):
    """
    Base handler objection which implements basic error handling.
    """
    pass
##    def handle_exception(self, exception, debug):
##        # Log the error.
##        logging.exception(exception)
##
##        # Set a custom message.
##        response.write('An error occurred : {}'.format(exception.message))
##
##        # If the exception is a HTTPException, use its error code.
##        # Otherwise use a generic 500 error code.
##        if isinstance(exception, webapp2.HTTPException):
##            self.response.set_status(exception.code)
##        else:
##            self.response.set_status(500)

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
        self.response.headers['Access-Control-Allow-Origin'] = 'null'
        self.response.write(self.request.headers)
        self.response.write(self.request.body)
        return
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

        for row in csv_reader:
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
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write("lat,lng,elev\n")
        for item in all_tracks:
          latlng = NZTM2000.NZTM_to_latlng(item[0],item[1])
          self.response.write("{:.6f},{:.6f},{:.1f}\n".format(latlng[0],latlng[1],item[2]))
          #if len(item)>3:
          #  self.response.write(item[3])

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



application = webapp2.WSGIApplication([
    ('/', UploadForm),
    ('/process_csv', ProcessCSV),
    ('/process_binary', ProcessBinary),
], debug=True)