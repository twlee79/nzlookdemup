﻿# coding: utf-8

"""
DEMSet module
version 6
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

import struct


class DEMReader:
  def __init__(self, dem_path, image_width, image_height, image_x0, image_y0, image_xn, image_yn, data_offset):
    self.dem_path = dem_path
    self.image_width = image_width
    self.image_height = image_height
    self.image_x0 = image_x0
    self.image_y0 = image_y0
    self.image_xn	= image_xn
    self.image_yn = image_yn
    self.data_offset = data_offset
    self.dem_file = None
  def activate(self):
    assert self.dem_file==None # assert to check for double activation
    self.dem_file = file(self.dem_path,"rb")
  def within_bounds(self,x,y):
    return self.image_x0 <= x <= self.image_xn and self.image_y0 < y <= self.image_yn
  def get_value(self,x,y):
    """
    Get height of point ``x,y`` from this DEM.
    Fast version. Does not check bounds or check that file is opened.
    Expected that caller (``DEMSet``) will have handled these.

    x, y : number, integers


    """
    offset = self.data_offset + ( (x-self.image_x0) + (y-self.image_y0) * self.image_width )*4

    self.dem_file.seek(offset)
    buffer = self.dem_file.read(4)
    return struct.unpack('<f', buffer)[0]

  def get_value_safe(self,x,y):
    """
    Get height of point ``x,y`` from this DEM.
    Returns ``None`` if point is out-of-range.

    x, y : number, integers


    """
    if not self.image_x0 <= x <= self.image_xn: raise IndexError("out of DEM bounds")
    if not self.image_y0 <= y <= self.image_yn: raise IndexError("out of DEM bounds")
    offset = self.data_offset + ( (x-self.image_x0) + (y-self.image_y0) * self.image_width )*4

    if self.dem_file is None:
      assert False
      self.activate()

    self.dem_file.seek(offset)
    buffer = self.dem_file.read(4)
    return struct.unpack('<f', buffer)[0]


class DEMSet:
  set0_E = 1012007.5 # central coordinate of top-left pixel in DEM set
  set0_N = 6233992.5
  voxelE = 15.0 # voxel sizes in DEM set
  voxelN = -15.0
  # x and y defined in terms of these coordinates

  DEM_reader_list = [
    # presort this list based on expected use, highest used readers at top
    DEMReader("dem/05-auckland-15m_0001-0001_uncompressed.tif",2845,2651,48000,19956,50844,22606,640),
    DEMReader("dem/04-dargaville-15m_0001-0001_uncompressed.tif",400,2607,47600.0,19950.0,47999.0,22556.0,640)
  ]
  def __init__(self):
    self.active_reader_list = []

  def get_value(self,x,y):
    """
    Get height of point ``x,y`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    x, y : number, integers

    """
    # logic: Check through all readers available in set for one that contains
    #        x,y. Increase efficiency by storing readers that have been previously
    #        used and opened by the set and checking these first.

    for DEM_reader in reversed(self.active_reader_list):
      # iterate over active readers in reverse so that we test last active
      # reader first
      if DEM_reader.within_bounds(x,y):
        ret = DEM_reader.get_value(x,y)
        assert ret!=None
        return ret

    for DEM_reader in self.DEM_reader_list:
      if DEM_reader.within_bounds(x,y):
        DEM_reader.activate()
        self.active_reader_list.append(DEM_reader) # store as an active reader
        ret = DEM_reader.get_value(x,y)
        assert ret!=None
        return ret

    raise IndexError("out of DEM bounds") # no DEMs contain this point

  def nearest_DEM(self,E,N):
    """
    Get height of nearest DEM point to ``E,N`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    E, N: number, float
      map coordinates in grid units
    """

    x = (E-self.set0_E)/self.voxelE
    y = (N-self.set0_N)/self.voxelN

    x = int(round(x)) # round to closest int
    y = int(round(y))

    return self.get_value(x,y)

  def interpolate_DEM(self,E,N):
    """
    Get interpolated height of point ``E,N`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    E, N: number, float
      map coordinates in grid units
    """

    x = (E-self.set0_E)/self.voxelE
    y = (N-self.set0_N)/self.voxelN

    return self.interpolate_DEMxy(x,y)

  def interpolate_DEMxy(self,x,y):
    """
    Get interpolate height of point ``x,y`` from this DEM set.
    Raises ``IndexError`` if point is out-of-range.

    x, y: number, float
      DEM coordinates in pixels
    """

    x1 = int(x // 1) # get surrounding integer points of x,y
    y1 = int(y // 1)
    x2 = x1+1
    y2 = y1+1

    q11 = self.get_value(x1,y1) # lookup DEM
    q21 = self.get_value(x2,y1)
    q12 = self.get_value(x1,y2)
    q22 = self.get_value(x2,y2)

    dx1 = x - x1 # deltas for interpolation
    dy1 = y - y1
    dx2 = 1.0 - dx1
    dy2 = 1.0 - dy1
    return q11*dx2*dy2 + q21*dx1*dy2 + q12*dx2*dy1 + q22*dx1*dy1
