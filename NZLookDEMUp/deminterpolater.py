# coding: utf-8

"""
DEMInterpolater module
version 15
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

from demset import DEMSet
import math

set0_E = 1012007.5 # central coordinate of top-left pixel in DEM set
set0_N = 6233992.5
voxelE = 15.0 # voxel sizes in DEM set
voxelN = -15.0
# x and y defined in terms of these coordinates

# convert E,N coords to x,y in DEM grid and vice versa
EN_to_xy = lambda EN: ((EN[0]-set0_E) / voxelE, (EN[1]-set0_N) / voxelN )
xy_to_EN = lambda xy: ( xy[0] * voxelE + set0_E, xy[1] * voxelN + set0_N )

demset = DEMSet()

class HardLimits:
    """
    Sets hard limits for interpolation algorithms.
    """
    max_line_steps = 1000 #: Max number of steps per line segment
    max_path_steps = 10000 #: Max number of steps for a path
    max_linedist_smart = 5000 #: Max line segment distance for smart interpolation algorithm (otherwise simple algorithm used) 

def pairs(it):
    """
    Return pairs of items for an iterator.
    By Glenn Maynard, see
    http://stackoverflow.com/questions/3929039/python-for-loop-how-to-find-next-valueobject
    """
    it = iter(it)
    prev = next(it)
    for v in it:
        yield prev, v
        prev = v

def interpolate_path_bysamples(path, samples=11):
    """
    Simple algorithm that returns a DEM profile along a path by simple 
    interpolation. Divides path into ``samples-1`` steps then interpolates 
    elevation at each step starting from first point in ``path`` and ending
    at last point in ``path``. Note the elevation for internal points in ``path``
    is not interpolated directly.
    
    Does not catch exceptions from failed DEM lookups, so these will be 
    propagated to the caller.

    Arguments:
        
        path : list of (float,float) tuples
            list of NZTM2000 E,N coordinates
        samples : integer
            number of samples to interpolate from path
    
    Return:
        out : list of (float,float,float) tuples
            List of points in interpolated path as ``(E,N,elevation)`` 
            tuples. ``E,N`` are NZTM coordinates of interpolated point and 
            ``elevation`` is elevation of interpolated point above sea-level in
            metres.

    """
    samples = min(HardLimits.max_path_steps,samples)
    samples = max(samples,2)

    # convert to x,y in DEM grid
    path_xy = map(EN_to_xy,path)
    
    # calculate parameters for start of each leg
    cumul_dxy = 0
    legs = []
    for ((x1,y1),(x2,y2)) in pairs(path_xy):
        dx = x2 - x1
        dy = y2 - y1
        dxy = ( dx**2 + dy**2 ) ** 0.5
        legs.append((x1,y1,dx,dy,dxy,cumul_dxy))
        cumul_dxy += dxy
        
    # interpolate along path
    stepxy = cumul_dxy / (samples-1)
    leg = 0
    track = []
    for sample in range(samples):
        if sample==0: # first sample = first coord in path
            x,y = path_xy[0]
            E,N = path[0]
        elif sample==samples-1: # last sample = last coord in path
            x,y = path_xy[-1]
            E,N = path[-1]
        else:
            # other sample, interpolate along path
            sample_dxy = sample*stepxy # expected distance
            while True:
                # find correct leg to interpolate this point from
                leg_x,leg_y,leg_dx,leg_dy,leg_dxy,leg_cumul_dxy = legs[leg]
                if sample_dxy>=leg_cumul_dxy and \
                   sample_dxy<=leg_cumul_dxy+leg_dxy: break
                leg+=1
            leg_fraction = (sample_dxy - leg_cumul_dxy) / leg_dxy
            assert leg_fraction>=0.0 and leg_fraction<=1.0
            x = leg_x + (leg_dx*leg_fraction)
            y = leg_y + (leg_dy*leg_fraction)
            E,N = xy_to_EN((x,y))
        q = demset.interpolate_DEMxy(x, y)
        track.append((E, N, q))
    return track


def interpolate_line_bysamples(E0, N0, E1, N1, samples=11):
    """
    Simple algorithm that returns a DEM profile along a line by simple 
    interpolation. Algorithm will return a total of ``samples`` points 
    with elevation along the line segment, inclusive of ``x0,y0`` and ``x1,y1``.
    
    Does not catch exceptions from failed DEM lookups, so these will be 
    propagated to the caller.

    Arguments:
        
        E0, N0, E1, N1 : floats
            NZTM2000 coordinates of line to interpolate
        samples : integer
            number of samples to interpolate along line
    
    Return:
        out : list of (float,float,float) tuples
            List of points in interpolated path as ``(E,N,elevation)`` 
            tuples. ``E,N`` are NZTM coordinates of interpolated point and 
            ``elevation`` is elevation of interpolated point above sea-level in
            metres.

    """
    
    samples = min(HardLimits.max_line_steps,samples)
    samples = max(samples,2)

    # find starting and ending x/y coordinates
    x0,y0 = EN_to_xy((E0,N0))
    x1,y1 = EN_to_xy((E1,N1))

    # determine deltas
    dx = x1-x0
    dy = y1-y0

    # interpolate
    track = []
    for sample in range(samples):
        if sample==0: # first sample = first coord
            x,y = x0,y0
            E,N = E0,N0
        elif sample==samples-1: # last sample = last coord
            x,y = x1,y1
            E,N = E1,N1
        else:
            fraction = float(sample)/(samples-1)
            x = x0 + fraction*dx
            y = y0 + fraction*dy
            E,N = xy_to_EN((x,y))
        q = demset.interpolate_DEMxy(x, y)
        track.append((E, N, q))

    return track

def interpolate_line_bysteps(E0, N0, E1, N1, stepsize = 100.0):
    """
    Simple algorithm that returns a DEM profile along a line by simple 
    interpolation. Starts at ``x0, y0``, and moves toward ``x1, y1`` in 
    ``stepsize`` distances until reaching ``x1, y1``. Elevation at ``x0, y0``
    and ``x1, y1`` are always returned as first and last points, respectively.

    Does not catch exceptions from failed DEM lookups, so these will be 
    propagated to the caller.

    Arguments:
        
        E0, N0, E1, N1 : floats
            NZTM2000 coordinates of line to interpolate
        stepsize : float
            size of each step (NZTM2000 metres) to interpolate along line
    
    Return:
        out : list of (float,float,float) tuples
            List of points in interpolated path as ``(E,N,elevation)`` 
            tuples. ``E,N`` are NZTM coordinates of interpolated point and 
            ``elevation`` is elevation of interpolated point above sea-level in
            metres.

    """

    # find starting and ending x/y coordinates
    print E0,N0
    print E1,N1
    x0,y0 = EN_to_xy((E0,N0))
    x1,y1 = EN_to_xy((E1,N1))

    # determine deltas
    dE = E1-E0
    dN = N1-N0
    dNE = ( dE**2 + dN**2) ** 0.5
    dx = x1-x0
    dy = y1-y0
    dxy = ( dx**2 + dy**2 ) ** 0.5
    
    # determine point scale factor
    # unnecessary to be this precise
    #k = NZTM2000.NZTM_k(E0,N0)
    #dNE*=k # multiply distance by point scale
    
    # ensure stepsize does cause # samples to exceed limit
    stepsize = abs(stepsize) # negative stepsizes will cause infinite loop
    stepsize = max(stepsize,dxy/HardLimits.max_line_steps)

    # interpolate
    track = []
    sample_dNE = 0.0
    done = False
    while not done:
        print sample_dNE,dNE
        if sample_dNE==0.0: # first sample = first coord
            x,y = x0,y0
            E,N = E0,N0
        else:
            fraction = sample_dNE/dNE
            if fraction>=1.0: # exceeded total distance, i.e last sample = last coord
                x,y = x1,y1
                E,N = E1,N1
                done = True
            else:
                x = x0 + fraction*dx
                y = y0 + fraction*dy
                E,N = xy_to_EN((x,y))
        q = demset.interpolate_DEMxy(x, y)
        track.append((E, N, q))
        sample_dNE += stepsize
 
    return track

def get_interpolation_vertex(x1, y1, dx, dy, q00, q10, q01, q11):
    """
    Return vertex (i.e. min or max value) of linear interpolation for line 
    defined by ``x1, y1, dx, dy`` given corner points ``q00, q10, q01, q11``, 
    which represent values at ``x, y`` coordinates ``0, 0``; ``1, 0``; ``0, 1`` 
    and ``1, 0``. (``x1, y1`` should therefore be defined in terms of the same 
    coordinate system).

    Only 'internal' vertices are returned, otherwise ``None``.

    Arguments:
        
        x1, y1, dx, dy : floats
            parameters of a line
        q00, q10, q01, q11 : floats
            values defined at coordinates ``0, 0``; ``1, 0``; ``0, 1``  and 
            ``1, 0``
    
    Return:
    
        out : (x, y, maxmin, ismax) tuple
            Returns tuple ``x, y, maxmin, ismax`` where ``x, y`` is 
            x, y coordinate of the vertex, ``maxmin`` is the interpolated ``q``
            value of the vertex and ``ismax`` is ``True`` if vertex represents a 
            maximum (``False`` if minimum). Return is ``None`` if no vertices
            in the range [``0, 0`` to ``1, 1``] are present.

    """
    if abs(dx) >= abs(dy): # chose a formula depending on relative dx/dy, to avoid divide by 0
        # y = mx + y0
        m = dy / dx
        y0 = y1-m * x1
        q_sum = q00 - q10 - q01 + q11
        a = q_sum * m
        b = (-q00 + q01) * m + q_sum * y0 + (-q00 + q10)
        c = q00 - q00 * y0 + q01 * y0
        if a == 0.0: return None # possible if q is flat
        x = -b / (2 * a)
        y = m * x + y0
        maxmin = (4 * a * c-b * b) / (4 * a)
    else:
        # x = ny + x0
        n = dx / dy
        x0 = x1-n * y1
        q_sum = q00 - q10 - q01 + q11
        a = q_sum * n
        b = (-q00 + q10) * n + q_sum * x0 + (-q00 + q01)
        c = q00 - q00 * x0 + q10 * x0
        if a == 0.0: return None
        y = -b / (2 * a)
        x = n * y + x0
        maxmin = (4 * a * c-b * b) / (4 * a)
    if x < 0 or y < 0 or x > 1.0 or y > 1.0: return None # not within bounds
    return x, y, maxmin, a < 0

def interpolate_line_smart(E0, N0, E1, N1, min_grade_delta=0.01, force_minmax=True):
    """
    Given a continuous line that passes through a discrete DEM image, will
    interpolate height values from the DEM using linear interpolation. This
    function uses a smart algorithm to produce a simplified but high resolution 
    line interpolated in height (``q``) direction.

    How it works:
    
        1) Assume line is running through an x/y grid of DEM points.
        
        2) At any point in line, immediately surrounding DEM points will 
           contribute to (bi)linear interpolate height at that point.
        
        3) A 'maximal' resolution interpolation of the line will interpolate
           for each point in the DEM grid, e.g. determine height as line enters 
           each new x/y location in the grid.
          
        4) It is also possible for a local maximum/minimum along the line to 
           occur between a certain series of surrounding points. Whether such a 
           point exists and its location can be calculated solving the quadratic 
           equation defined by the linear interpolation to find the presence of 
           a vertex.
           
        5) Each interpolated point (x, y, q) contributes to a new segment on the
           path.
           
        6) This will produce a large number of interpolated points for. To remove
           redundant or practically-redundant points, filter these according to
           changes in grade. If the grade of that segment is similar to the last 
           segment (difference in grade < ``min_grade_delta``), then combine the 
           two segments to simplify the path. This produces a path with a
           smaller number of segments but still maintaining most height 
           information in the line. Maximum/minimum points on the line (where 
           grade sign changes) will always be kept if ``force_minmax`` is ``True``.
           
    Does not catch exceptions from failed DEM lookups, so these will be 
    propagated to the caller. If length of line is more than hard limit, by steps
    algorithm will be used instead.

    Arguments:

        E0, N0, E1, N1 : floats
          NZTM2000 coordinates of line to interpolate
        min_grade_delta : float
          min delta between two grade segments to keep segments separate, if delta
          is less than this the segments will be merged to simplify the interpolated
          line
        force_minmax : boolean
          whether to force min/max points on line to be kept regardless of grade_delta

    Return:
        out : list of (float,float,float) tuples
            List of points in interpolated path as ``(E,N,elevation)`` 
            tuples. ``E,N`` are NZTM coordinates of interpolated point and 
            ``elevation`` is elevation of interpolated point above sea-level in
            metres.
 
    """

    # find starting and ending x/y coordinates
    x0,y0 = EN_to_xy((E0,N0))
    x1,y1 = EN_to_xy((E1,N1))

    # find deltas
    dx = x1-x0
    dy = y1-y0
    dxy = ( dx**2 + dy**2 ) ** 0.5
    abs_dx = abs(dx)
    abs_dy = abs(dy)

    if dxy > HardLimits.max_linedist_smart:
        # line length for this algorithm exceeded
        # use simple algorithm
        return interpolate_line_bysteps(E0, N0, E1, N1)

    #start at point 0
    x = x0
    y = y0

    # define 1 unit change with direction
    dx1 = +1 if dx >= 0 else -1
    dy1 = +1 if dy >= 0 else -1

    # find numbers to add to floor to give minus and plus points surrounding current point
    xm = + 1 if dx < 0 else 0 # if x is decreasing, 'minus' point is ahead of current point (floor+1), else behind (floor+0)
    ym = + 1 if dy < 0 else 0
    xp = + 1 if dx >= 0 else 0 # if x is increasing, 'plus' point is ahead of current point (floor+1), else behind (floor+0)
    yp = + 1 if dy >= 0 else 0

    # find surrounding whole points for first point
    x_int_m = int(x // 1) + xm
    x_int_p = int(x // 1) + xp
    y_int_m = int(y // 1) + ym
    y_int_p = int(y // 1) + yp

    # find terminating whole points
    x1_int_m = int(x1 // 1) + xm
    y1_int_m = int(y1 // 1) + ym

    #print x0,",", y0,"to", x1,",", y1
    #print "delta", dx, dy

    # lookup q values of surrounding points
    qmm = demset.get_value(x_int_m, y_int_m)
    qpm = demset.get_value(x_int_p, y_int_m)
    qmp = demset.get_value(x_int_m, y_int_p)
    qpp = demset.get_value(x_int_p, y_int_p)

    # determine deltas for interpolation
    dxm = abs(x - x_int_m)
    dxp = abs(x_int_p - x)
    dym = abs(y - y_int_m)
    dyp = abs(y_int_p - y)

    # interpolate first point
    q = qmm * dxp * dyp + qpm * dxm * dyp + qmp * dxp * dym + qpp * dxm * dym

    # track to produce with interpolated q values
    track = []

    # variables updated in script
    q_m1 = dist_m1 = None # minus 1 values (penultimate)
    q_0 = dist_0 = grade_0 = None # zero/last values
    grade = d_q = d_dist = None # current values

    check_vertex = True # True if should check if vertex is present

    index = 0 # index of interpolated point

    while True:
        expect_q = qmm * dxp * dyp + qpm * dxm * dyp + qmp * dxp * dym + qpp * dxm * dym
        #print x, y
        assert abs(q-expect_q) < 1e-10, "{} vs {}".format(q, expect_q)
        dist = ((voxelE * (x-x0)) ** 2 + (voxelN * (y-y0)) ** 2) ** 0.5 # calculate distance in map units
        if q_0 is not None: # if last point is present
            d_q = q-q_0 # find deltas to last
            d_dist = dist-dist_0
            grade = d_q / d_dist

            # strategy: always add new point to track,
            # but remove last from track if it is redundant

            # should we add a new point to track?
            if (grade_0 is None or # not enough previous points, must keep point
                (force_minmax and grade * grade_0 < 0) or # grade sign change, always keep last point
                abs(grade-grade_0) >= min_grade_delta): # grade delta more than cutoff
                # yes, add current point to track
                q_m1 = q_0 # push zero to -1
                dist_m1 = dist_0
            else:
                # no, replace last point
                track.pop()
                # point 0 is now effectively invalidated, -1 unchanged
                # new point is now 0, and calc'd from -1
                d_q = q-q_m1
                d_dist = dist-dist_m1
                grade = d_q / d_dist
            grade_0 = grade
        q_0 = q # current point is now 0
        dist_0 = dist

        E = x * voxelE + set0_E
        N = y * voxelN + set0_N
        track.append((E, N, q))


        if x == x1 and y == y1:
            # reached end point
            if index != -1:
                # ensure always add last point
                # may get here if point0 == point1
                track.append((E, N, q))
            break

        index += 1

        # vertex is a point on the line than may give a maximum or minimum value of
        # q in the linear interpolation algorithm
        if check_vertex: # if looking for a vertex, will be False if found a vertex in last iteration

            vertex = get_interpolation_vertex(dxm, dym, abs_dx, abs_dy, qmm, qpm, qmp, qpp)
                # vertex finding algorithm assumes x, y are defined in terms of
                # 0, 1 coordinates of qmm-qpp
                # vertex algorithm will return correct values if
                # given absolute x, y, dx, dy values, if q values
                # defined in line direction (i.e. qmm closest to origin
                # of line)
                # vertex algorithm will return a vertex if present within 0-1 bounds

            if vertex is not None: # got a vertex
                vertex_x, vertex_y, vertex_q, vertex_ismax = vertex
                vertex_x = x_int_m + math.copysign(vertex_x, dx) # calculate x, y in image scale
                vertex_y = y_int_m + math.copysign(vertex_y, dy)

                # check if vertex is within line bounds (may be less than 0-1 bounds of
                # qmm-qpp, if out of bounds, skip processing vertex
                if dx >= 0   and (vertex_x < x0 or vertex_x > x1): pass
                elif dx < 0  and (vertex_x > x0 or vertex_x < x1): pass
                elif dy >= 0 and (vertex_y < y0 or vertex_y > y1): pass
                elif dy < 0  and (vertex_y > y0 or vertex_y < y1): pass
                else:
                    check_vertex = False # don't look for vertex in next iteration
                    x = vertex_x # process x, y point at top of point
                    y = vertex_y
                    q = vertex_q
                    #print vertex
                    dxm = abs(x - x_int_m)
                    dxp = abs(x_int_p - x)
                    dym = abs(y - y_int_m)
                    dyp = abs(y_int_p - y)
                    continue

        if x_int_m == x1_int_m and y_int_m == y1_int_m: # reached terminating whole points
            # if got here, next point should be endpoint
            # jump to exact endpoint
            x = x1
            y = y1
            dxm = abs(x - x_int_m)
            dxp = abs(x_int_p - x)
            dym = abs(y - y_int_m)
            dyp = abs(y_int_p - y)
            q = qmm * dxp * dyp + qpm * dxm * dyp + qmp * dxp * dym + qpp * dxm * dym
            index = -1 # mark last point with index -1
        else:
            check_vertex = True # well be incrementing qmm-qpp points, check a vertex next iteration

            # should we increment x or increment y?
            dx_next = x_int_p - x # determine distance to next whole x/y points
            dy_next = y_int_p - y

            if dx_next / dx <= dy_next / dy: # closer to a whole x point
                x_int_m = x_int_p # move along one whole point in x direction
                x_int_p = x_int_p + dx1
                x = x_int_m # start at whole x location
                y = y0 + (x-x0) / dx * dy # determine y at this whole x

                # reassign/get/calculate q and delta values
                qmm = qpm
                qmp = qpp
                qpm = demset.get_value(x_int_p, y_int_m)
                qpp = demset.get_value(x_int_p, y_int_p)
                dxm = 0.0
                dxp = 1.0
                dym = abs(y - y_int_m)
                dyp = abs(y_int_p - y)

                q = qmm * dyp + qmp * dym # interpolate y at whole x point

            else:  # closer to a whole y point
                y_int_m = y_int_p # move along one whole point in y direction
                y_int_p = y_int_p + dy1
                y = y_int_m # start at whole y location
                x = x0 + (y-y0) / dy * dx # determine x at this whole y

                # reassign/get/calculate q and delta values
                qmm = qmp
                qpm = qpp
                qmp = demset.get_value(x_int_m, y_int_p)
                qpp = demset.get_value(x_int_p, y_int_p)
                dxm = abs(x - x_int_m)
                dxp = abs(x_int_p - x)
                dym = 0.0
                dyp = 1.0

                q = qmm * dxp + qpm * dxm # interpolate y at whole x point
    return track
