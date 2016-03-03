# coding: utf-8

"""
DEMSet module
version 8
Copyright (c) 2014 Tet Woo Lee
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
from google.appengine.api import app_identity
import os
import struct

bucket_name = '/' + os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())


class DEMReader:
    buffer_size = 4 * 1024 * 1024 # need manual buffer for cloud storage, this does not support buffered random i/o (sequential only)
    def __init__(self, dem_path, image_width, image_height, image_x0, image_y0, 
                 image_xn, image_yn, data_offset, cloud=False):
        self.dem_path = dem_path
        self.image_width = image_width
        self.image_height = image_height
        self.image_x0 = image_x0
        self.image_y0 = image_y0
        self.image_xn	= image_xn
        self.image_yn = image_yn
        self.data_offset = data_offset
        self.dem_file = None
        self.cloud = cloud
        self.buffer = None
        self.buffer_start = None
        self.buffer_end = None
    def activate(self):
        #print "Activating: ",self.dem_path
        assert self.dem_file == None # assert to check for double activation
        if not self.cloud:
            self.dem_file = file(self.dem_path, "rb")
        else:
            self.dem_file = cloudstorage.open(bucket_name + '/' + self.dem_path, "r", read_buffer_size=self.buffer_size)
    def within_bounds(self, x, y):
        return self.image_x0 <= x <= self.image_xn and self.image_y0 < y <= self.image_yn
    def buffered_read(self, offset, size):
        if offset > self.buffer_start and offset + size < self.buffer_end and self.buffer is not None:
            pass # in buffer
        else:
            self.buffer_start = offset - self.buffer_size / 2
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
  
    max_active_readers = 5
  
    DEM_reader_list_path = "DEMs"

    DEM_reader_list = [
        # presort this list based on expected use, highest used readers at top
        #DEMReader("dem/05-auckland-15m-1-0001-0001_uncompressed.tif",8000,12000,48000,19200,55999,31199,639,True),
        #DEMReader("dem/05-auckland-15m-1-0001-0001_uncompressed.tif",8000,12000,48000,19200,55999,31199,639)
        #DEMReader("updem/05-auckland-15m_0001-0001_uncompressed.tif",2845,2651,48000,19956,50844,22606,640),
#    DEMReader("subset_dem/05-auckland-15m-subset01-1x1.tif",2000,3000,48000,19200,49999,22199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset02-1x2.tif",2000,3000,50000,19200,51999,22199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset03-1x3.tif",2000,3000,52000,19200,53999,22199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset04-1x4.tif",2000,3000,54000,19200,55999,22199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset05-2x1.tif",2000,3000,48000,22200,49999,25199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset06-2x2.tif",2000,3000,50000,22200,51999,25199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset07-2x3.tif",2000,3000,52000,22200,53999,25199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset08-2x4.tif",2000,3000,54000,22200,55999,25199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset09-3x1.tif",2000,3000,48000,25200,49999,28199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset10-3x2.tif",2000,3000,50000,25200,51999,28199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset11-3x3.tif",2000,3000,52000,25200,53999,28199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset12-3x4.tif",2000,3000,54000,25200,55999,28199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset13-4x1.tif",2000,3000,48000,28200,49999,31199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset14-4x2.tif",2000,3000,50000,28200,51999,31199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset15-4x3.tif",2000,3000,52000,28200,53999,31199,639),
#    DEMReader("subset_dem/05-auckland-15m-subset16-4x4.tif",2000,3000,54000,28200,55999,31199,639),
    DEMReader("subset_dem/05-auckland-15m-subset01-1x1.tif", 2000, 3000, 48000, 19200, 49999, 22199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset02-1x2.tif", 2000, 3000, 50000, 19200, 51999, 22199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset03-1x3.tif", 2000, 3000, 52000, 19200, 53999, 22199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset04-1x4.tif", 2000, 3000, 54000, 19200, 55999, 22199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset05-2x1.tif", 2000, 3000, 48000, 22200, 49999, 25199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset06-2x2.tif", 2000, 3000, 50000, 22200, 51999, 25199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset07-2x3.tif", 2000, 3000, 52000, 22200, 53999, 25199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset08-2x4.tif", 2000, 3000, 54000, 22200, 55999, 25199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset09-3x1.tif", 2000, 3000, 48000, 25200, 49999, 28199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset10-3x2.tif", 2000, 3000, 50000, 25200, 51999, 28199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset11-3x3.tif", 2000, 3000, 52000, 25200, 53999, 28199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset12-3x4.tif", 2000, 3000, 54000, 25200, 55999, 28199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset13-4x1.tif", 2000, 3000, 48000, 28200, 49999, 31199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset14-4x2.tif", 2000, 3000, 50000, 28200, 51999, 31199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset15-4x3.tif", 2000, 3000, 52000, 28200, 53999, 31199, 639, True),
    DEMReader("subset_dem/05-auckland-15m-subset16-4x4.tif", 2000, 3000, 54000, 28200, 55999, 31199, 639, True),
    #DEMReader("dem/04-dargaville-15m_0001-0001_uncompressed.tif",400,2607,47600,19950,47999,22556,640)
]
    def __init__(self):
        self.active_reader_deque = deque()

    def get_value(self, x, y):
        """
    Get height of point ``x,y`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    x, y : number, integers

    """
        # logic: Check through all readers available in set for one that contains
        #        x,y. Increase efficiency by storing readers that have been previously
        #        used and opened by the set and checking these first.

        for DEM_reader in self.active_reader_deque:
            # iterate over active readers
            if DEM_reader.within_bounds(x, y):
                ret = DEM_reader.get_value(x, y)
                assert ret != None
                return ret

        for DEM_reader in self.DEM_reader_list:
            if DEM_reader.within_bounds(x, y):
                DEM_reader.activate()
                self.active_reader_deque.appendleft(DEM_reader) # store as an active reader
                if len(self.active_reader_deque) > self.max_active_readers:
                    self.active_reader_deque.pop() # remove oldest if too many active readers
                ret = DEM_reader.get_value(x, y)
                assert ret != None
                return ret

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

