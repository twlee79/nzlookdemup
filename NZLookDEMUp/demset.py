# coding: utf-8

"""
DEMSet module
version 9
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

import cloudstorage
from collections import deque
from itertools import izip
from google.appengine.api import app_identity
import os
import struct

bucket_name = '/' + os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())

class DEMReader:
    buffer_size = 4 * 1024 * 1024 # need manual buffer for cloud storage, this does not support buffered random i/o (sequential only)
    def __init__(self, field_dict, cloud=False):
        self.dem_path = field_dict["path"]
        self.image_width = field_dict["image_width"]
        self.image_height = field_dict["image_height"]
        self.image_x0 = field_dict["image_x0"]
        self.image_y0 = field_dict["image_y0"]
        self.image_xn = field_dict["image_xn"]
        self.image_yn = field_dict["image_yn"]
        self.data_offset = field_dict["data_offset"]

        self.cloud = cloud
        self.dem_file = None
        self.deactivate()
    def is_active(self):
        return self.dem_file is not None
    def activate(self):
        print "Activating: ",self.dem_path
        assert self.dem_file is None # assert to check for double activation
        if not self.cloud:
            file_path = 'nztmdem_1000x1000/' + self.dem_path
            self.dem_file_size = os.stat(file_path).st_size
            self.dem_file = file(file_path, "rb")
        else:
            bucket_path = bucket_name + '/nztmdem_1000x1000/' + self.dem_path
            self.dem_file_size = cloudstorage.stat(bucket_path).st_size
            self.dem_file = cloudstorage.open(bucket_path, "r", read_buffer_size=self.buffer_size)
    def deactivate(self):
        if self.is_active(): print "Deactivating: ",self.dem_path
        self.dem_file = None
        self.buffer = None
        self.buffer_start = None
        self.buffer_end = None
    def within_bounds(self, x, y):
        return self.image_x0 <= x <= self.image_xn and self.image_y0 <= y <= self.image_yn
    def buffered_read(self, offset, size):
        if offset > self.buffer_start and offset + size < self.buffer_end and self.buffer is not None:
            pass # in buffer
        else:
            self.buffer_start = min(offset - self.buffer_size / 2, self.dem_file_size - self.buffer_size)
            if self.buffer_start < 0: self.buffer_start = 0
            self.dem_file.seek(self.buffer_start)
            self.buffer = self.dem_file.read(self.buffer_size)
            self.buffer_end = self.buffer_start + len(self.buffer)
            print 'Buffer read from {} to {}'.format(self.buffer_start, self.buffer_end)
        offset_in_buffer = offset-self.buffer_start
        assert offset_in_buffer > 0 and offset_in_buffer < self.buffer_size
        data = self.buffer[offset_in_buffer:offset_in_buffer + size]
        assert len(data) == size
        return data
        
    def get_value(self, x, y):
        """
        Get height of point ``x,y`` from this DEM.
        Fast version. Does not check bounds or check that file is opened.
        Expected that caller (``DEMSet``) will have handled these.

        x, y : number, integers


        """
        x = int(x)
        y = int(y)
        offset = self.data_offset + ((x-self.image_x0) + (y-self.image_y0) * self.image_width) * 4

        packed = self.buffered_read(offset, 4)
        return struct.unpack('<f', packed)[0]

    def get_value_safe(self, x, y):
        """
        Get height of point ``x,y`` from this DEM.
        Returns ``None`` if point is out-of-range.

        x, y : number, integers


        """
        x = int(x)
        y = int(y)
        if not self.image_x0 <= x <= self.image_xn: raise IndexError("out of DEM bounds")
        if not self.image_y0 <= y <= self.image_yn: raise IndexError("out of DEM bounds")
        offset = self.data_offset + ((x-self.image_x0) + (y-self.image_y0) * self.image_width) * 4

        if self.dem_file is None:
            assert False
            self.activate()

        packedr = self.buffered_read(offset, 4)
        return struct.unpack('<f', packed)[0]


class DEMSet:
    set0_E = 1012007.5 # central coordinate of top-left pixel in DEM set
    set0_N = 6233992.5
    voxelE = 15.0 # voxel sizes in DEM set
    voxelN = -15.0
    # x and y defined in terms of these coordinates
  
    max_active_readers = 10
    DEM_reader_grid_resolution = 200

    DEM_list_path = "geotiff summary 1000x1000 no overlap.txt"

    def __init__(self):
        self.active_reader_deque = deque()
        self.DEM_grid = []
        self.read_list()

    def read_list(self):
        """
        Read list of DEMs from text file.

        """
        # logic: All DEMs should be spaced in discrete non-overlapping grid.
        #        Fill this grid with DEM_reader objects for quick lookup.
        DEM_list = open(self.DEM_list_path)

        field_names = None
        for line in DEM_list:
          if line[0]=='#': continue
          tokens = line.strip().split('\t')
          if field_names is None:
            field_names = tokens
            continue
          value_dict = {}
          for field_name,field_value in izip(field_names,tokens):
            if field_name == "image_E0" or field_name == "image_N0":
              field_value = float(field_value)
            elif field_name == "path":
              pass
            else:
              field_value = int(field_value)
            value_dict[field_name] = field_value

          DEM_reader = DEMReader(value_dict,True)
          image_grid_x0 = DEM_reader.image_x0/self.DEM_reader_grid_resolution
          image_grid_y0 = DEM_reader.image_y0/self.DEM_reader_grid_resolution
          image_grid_xn = DEM_reader.image_xn/self.DEM_reader_grid_resolution
          image_grid_yn = DEM_reader.image_yn/self.DEM_reader_grid_resolution
          if DEM_reader.image_x0 - image_grid_x0*self.DEM_reader_grid_resolution!=0 or \
             DEM_reader.image_y0 - image_grid_y0*self.DEM_reader_grid_resolution!=0 or \
             DEM_reader.image_xn+1 - (image_grid_xn+1)*self.DEM_reader_grid_resolution!=0 or \
             DEM_reader.image_yn+1 - (image_grid_yn+1)*self.DEM_reader_grid_resolution!=0:
              raise Exception("{path} is does not completely fill grid".format(**value_dict))

          while len(self.DEM_grid)<image_grid_yn+1: self.DEM_grid.append([])
          for image_grid_y in range(image_grid_y0,image_grid_yn+1):
            DEM_grid_row = self.DEM_grid[image_grid_y]
            while len(DEM_grid_row)<image_grid_xn+1: DEM_grid_row.append(None)
            for image_grid_x in range(image_grid_x0,image_grid_xn+1):
              if DEM_grid_row[image_grid_x] is None:
                DEM_grid_row[image_grid_x] = DEM_reader
              else:
                raise Exception('>1 DEM for grid {}x{}'.format(image_grid_x,image_grid_y))

        DEM_list.close()

    def get_value(self, x, y, raise_exception = False):
        """
        Get height of point ``x,y`` from this DEM set.
        If ``raise_exception`` is ``true``, 
        raises ``IndexError`` if point is out-of-range.
        Otherwise, return ``nan``.

        x, y : number, integers

        """
        # logic: Find correct reader from grid. Maintain deque of active readers
        #        and deactivate oldest if >max number of allowed max readers.
        image_grid_x = x/self.DEM_reader_grid_resolution
        image_grid_y = y/self.DEM_reader_grid_resolution
        try:
            DEM_reader = self.DEM_grid[image_grid_y][image_grid_x]
            if DEM_reader is not None:
                assert(DEM_reader.within_bounds(x, y))
                if not DEM_reader.is_active():
                    DEM_reader.activate()
                    self.active_reader_deque.appendleft(DEM_reader) # store as an active reader
                ret = DEM_reader.get_value(x, y)
                assert ret != None
                if len(self.active_reader_deque) > self.max_active_readers:
                    oldest_reader = self.active_reader_deque.pop() # remove oldest if too many active readers
                    oldest_reader.deactivate()
                return ret
        except IndexError:
            pass

        if not raise_exception: return float('nan')
        raise IndexError("out of DEM bounds") # no DEMs contain this point

    def nearest_DEM(self, E, N):
        """
        Get height of nearest DEM point to ``E,N`` from this DEM set.
        Raises ``IndexError`` if point is out-of-range.

        E, N: number, float
          map coordinates in grid units
        """

        x = (E-self.set0_E) / self.voxelE
        y = (N-self.set0_N) / self.voxelN

        x = int(round(x)) # round to closest int
        y = int(round(y))

        return self.get_value(x, y)

    def interpolate_DEM(self, E, N):
        """
    Get interpolated height of point ``E,N`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    E, N: number, float
      map coordinates in grid units
    """

        x = (E-self.set0_E) / self.voxelE
        y = (N-self.set0_N) / self.voxelN

        return self.interpolate_DEMxy(x, y)

    def interpolate_DEMxy(self, x, y):
        """
    Get interpolate height of point ``x,y`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    x, y: number, float
      DEM coordinates in pixels
    """

        x1 = int(x // 1) # get surrounding integer points of x,y
        y1 = int(y // 1)
        x2 = x1 + 1
        y2 = y1 + 1

        q11 = self.get_value(x1, y1) # lookup DEM
        q21 = self.get_value(x2, y1)
        q12 = self.get_value(x1, y2)
        q22 = self.get_value(x2, y2)

        dx1 = x - x1 # deltas for interpolation
        dy1 = y - y1
        dx2 = 1.0 - dx1
        dy2 = 1.0 - dy1
        return q11 * dx2 * dy2 + q21 * dx1 * dy2 + q12 * dx2 * dy1 + q22 * dx1 * dy1

