# coding: utf-8

"""
DEMInterpolater module
version 14
Copyright (c) 2014 Tet Woo Lee
"""
#TODO: Rationalise calling simple/ideal algorithm with either E/N or x/y coords
#TODO: Check for indentation issues

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

demset = DEMSet()

"""
Path interpolation algorithm:

for each leg calculate cumuldist up to start, legdist
calc total cumuldist
stepsize = cumultdist/(steps-1)
for each step:
    stepdist = step_i*stepsize
    while stepdist>=legstart and stepdist<=legstart+legdist: next leg
        # gets leg for this stepdist
    legdistfraction = (stepdist-legstart)/legdist
    assert legdistfraction>=0.0 and legdistfraction<=1.0
    dx = leg_dx*legdistfraction
    dy = leg_dy*legdistfraction
    interpolate for leg_x+dx, leg_y+dy

"""

def interpolate_line_simple(E1, N1, E2, N2, samples=11):
    """
    Simple algorithm that returns a DEM profile along a line
    by simply interpolation. Starts at
    ``x1, y1``, and moves toward ``x2, y2`` in step distances
    until reaching or going past ``x2, y2``.

    Returns a list of ``(E, N, q, index)`` tuples, where ``E, N`` are
    easting/northing coordinates of interpolation points, ``q`` is DEM height
    and ``index`` is the index of the point; the first point has an index
    of 0 and the last point has an index of -2

    Does not catch IndexErrors from failed DEM lookups, so these
    will be propagated to the caller.

    E1, N1, E2, N2 : numbers
      NZTM2000 coordinates of line to interpolate
    samples : number
      number of samples
    """

    # find starting and ending x/y coordinates
    x1 = (E1-set0_E) / voxelE
    y1 = (N1-set0_N) / voxelN
    x2 = (E2-set0_E) / voxelE
    y2 = (N2-set0_N) / voxelN

    # determine x, y step sizes
    dx = x2-x1
    dy = y2-y1
    stepx = dx / (samples-1) # -1 because we want to include first/last points
    stepy = dy / (samples-1)

    # start at x1, y1
    x = x1
    y = y1
    track = []
    index = 0 # index of interpolated point

    if dx > 0 and dy > 0: # different end point check depending on dx/dy direction
        while x < x2 and y < y2:
            q = demset.interpolate_DEMxy(x, y)
            dist = ((x-x1) ** 2 + (y-y1) ** 2) ** 0.5
            E = x * voxelE + set0_E
            N = y * voxelN + set0_N
            #track.append((x, y, q, dist))
            track.append((E, N, q, index))
            index += 1
            x += stepx
            y += stepy
    elif dx > 0 and dy < 0:
        while x < x2 and y > y2:
            q = demset.interpolate_DEMxy(x, y)
            #dist = ((x-x1)**2 + (y-y1)**2)**0.5
            E = x * voxelE + set0_E
            N = y * voxelN + set0_N
            #track.append((x, y, q, dist))
            track.append((E, N, q, index))
            index += 1
            x += stepx
            y += stepy
    elif dx < 0 and dy > 0:
        while x > x2 and y < y2:
            q = demset.interpolate_DEMxy(x, y)
            #dist = ((x-x1)**2 + (y-y1)**2)**0.5
            E = x * voxelE + set0_E
            N = y * voxelN + set0_N
            #track.append((x, y, q, dist))
            track.append((E, N, q, index))
            index += 1
            x += stepx
            y += stepy
    elif dx < 0 and dy < 0:
        while x > x2 and y > y2:
            q = demset.interpolate_DEMxy(x, y)
            #dist = ((x-x1)**2 + (y-y1)**2)**0.5
            E = x * voxelE + set0_E
            N = y * voxelN + set0_N
            #track.append((x, y, q, dist))
            track.append((E, N, q, index))
            index += 1
            x += stepx
            y += stepy
    else:
        assert False
    x = x2
    y = y2
    q = demset.interpolate_DEMxy(x, y)
    E = x * voxelE + set0_E
    N = y * voxelN + set0_N
    index = -2 # last point has index -2
    #track.append((x, y, q, dist))
    #track.append((E, N, q,"simple"))
    track.append((E, N, q, index))
    return track


def get_interpolation_vertex(x1, y1, dx, dy, q11, q21, q12, q22):
    """
    Return vertex (i.e. min or max value) of linear
    interpolation for line defined by ``x1, y1, dx, dy`` given
    corner points ``q11, q21, q12, q22``, which represent values at
    ``x, y`` coordinates ``0, 0``; ``1, 0``; ``0, 1`` and ``1, 0``.
    (``x1, y1`` should thefore be defined  in terms of the same coordinate system)

    Returns tuple ``x, y, maxmin, ismax`` where ``x, y`` is x, y coordinate
    of the vertex, ``maxmin`` is the interpolated ``q`` value of the
    vertex and ``ismax`` is ``True`` if vertex represents a maximum
    (``False`` if minimum).

    Only 'internal' vertices are returned, i.e. if vertex
    is outside range ``0, 0`` to ``1, 1``, returns ``None``.
    """
    if abs(dx) >= abs(dy): # chose a formula depending on relative dx/dy, to avoid divide by 0
        # y = mx + y0
        m = dy / dx
        y0 = y1-m * x1
        q_sum = q11 - q21 - q12 + q22
        a = q_sum * m
        b = (-q11 + q12) * m + q_sum * y0 + (-q11 + q21)
        c = q11 - q11 * y0 + q12 * y0
        if a == 0.0: return None # possible if q is flat
        x = -b / (2 * a)
        y = m * x + y0
        maxmin = (4 * a * c-b * b) / (4 * a)
    else:
        # x = ny + x0
        n = dx / dy
        x0 = x1-n * y1
        q_sum = q11 - q21 - q12 + q22
        a = q_sum * n
        b = (-q11 + q21) * n + q_sum * x0 + (-q11 + q12)
        c = q11 - q11 * x0 + q21 * x0
        if a == 0.0: return None
        y = -b / (2 * a)
        x = n * y + x0
        maxmin = (4 * a * c-b * b) / (4 * a)
    if x < 0 or y < 0 or x > 1.0 or y > 1.0: return None # not within bounds
    return x, y, maxmin, a < 0

def interpolate_line_ideal(E0, N0, E1, N1, min_grade_delta=0.01, force_minmax=True):
    """
    Given a continuous line that passes through a discrete DEM image, will
    interpolate height values from the DEM using linear interpolation.

    If ``samples`` is not None, will interpolate with given number of samples
    along line. Otherwise,advanced line interpolation algorithm than will 
    produce a simplified but maximal resolution line interpolated in height 
    (``q``) direction.

    How it works:
    1) Assume line is running through an x/y grid of DEM points.
    2) At any point in line, immediately surrounding DEM points will contribute
    to linear interpolate height at that point.
    3) To obtain maximal resolution of
    line, determine height as line enters each new x/y location in the grid.
    4) It is also possible for a local maximum/minimum along the line to occur between a
    certain series of surrounding points. Whether such a point exists and its location
    can be calculated solving the quadratic equation defined by the linear
    interpolation to find the presence of a vertex.
    5) Each interpolated point (x, y, q) contributes to a new segment on the path.
    6) If the grade of that segment is similar to the last segment (grade_delta),
    combine the two segments to simplify the path. This produces a path with a
    smaller number of segments but still maintaining most height information in the
    line. Maximum/minimum points on the line (where grade sign changes) will always
    be kept if ``force_minmax`` is True

    E0, N0, E1, N1 : numbers
      NZTM2000 coordinates of line to interpolate
    min_grade_delta : number
      min delta between two grade segments to keep segments separate, if delta
      is less than this the segments will be merged to simplify the interpolated
      line
    force_minmax : boolean
      whether to force min/max points on line to be kept regardless of grade_delta

    returns a list of (E, N, q, index) tuples, where

    E, N : easting and northig of interpolated point
    dist : distance of this point from start in grid units
    q : height of point
    grade : grade of from last point to this point (d_q/d_dist), None in first segment
    d_dist : delta of dist from last point, None in first segment
    d_q : delta of q from last point, None in first segment
    index : increasing index number of the point(up to last point), may not be sequential
    but first point   will always be ``0`` and last point will be <0 (-1 if this algorithm
    used, -2 if simple algorithm used because line was too long)


    Does not catch IndexErrors from failed DEM lookups, so these
    will be propagated to the caller.

    If line length is more than 300 voxels in one direction,
    simple algorithm will be used instead.
    """

    # find starting and ending x/y coordinates
    x0 = (E0-set0_E) / voxelE
    y0 = (N0-set0_N) / voxelN
    x1 = (E1-set0_E) / voxelE
    y1 = (N1-set0_N) / voxelN

    # find deltas
    dx = x1-x0
    dy = y1-y0
    abs_dx = abs(dx)
    abs_dy = abs(dy)

    if abs_dx > 300 or abs_dy > 300:
        # line length for this algorithm exceeded
        # use simple algorithm
        return interpolate_line_simple(E0, N0, E1, N1)

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
        #track.append((E, N, dist, q, grade, d_dist, d_q))
        #track.append((E, N, q,"ideal"))
        track.append((E, N, q, index))


        if x == x1 and y == y1:
            # reached end point
            if index != -1:
                # ensure always add a -1 point
                # may get here if point0 == point1
                track.append((E, N, q, -1))
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
