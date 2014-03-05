# coding: utf-8

"""
NZTM2000 module
version 3
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

import math

class NZTM2000:
  """
  Converts lat/lng to New Zealand Transverse Mercator 2000 map coordinates.
  Formula source: http://www.linz.govt.nz/geodetic/conversion-coordinates/projection-conversions/transverse-mercator-preliminary-computations#lbl1
  
  Details of NZTM2000 projection:
    source: http://www.linz.govt.nz/geodetic/datums-projections-heights/projections/new-zealand-transverse-mercator-2000
    
    Name: New Zealand Transverse Mercator 2000
    Abbreviation: NZTM2000
    Projection type: Transverse Mercator
    Reference ellipsoid: GRS80
    Datum: NZGD2000
    Origin latitude: 0° 00' 00" South
    Origin longitude: 173° 00' 00" East
    False Northing: 10,000,000 metres North
    False Easting: 1,600,000 metres East
    Central meridian scale factor: 0.9996

    source: http://spatialreference.org/ref/epsg/2193/
    EPSG:2193
    NZGD2000 / New Zealand Transverse Mercator 2000 
    WGS84 Bounds: 166.3300, -47.4000, 178.6000, -34.0000
    Projected Bounds: 983515.7211, 4728776.8709, 2117458.3527, 6223676.2306
  
  Details of NZGD2000 Datum:
    source: http://www.linz.govt.nz/geodetic/datums-projections-heights/geodetic-datums/new-zealand-geodetic-datum-2000
    NZGD2000 is essentially coincident with the World Geodetic System 1984 (WGS84). 
  
  Reference ellipsoide details:
    Ellipsoid   Semi-major axis (m)   Inverse flattening
    GRS80       6,378,137             298.257 222 101
    WGS84       6,378,137             298.257 223 563

  """

  # Projection parameters
  a = 6378137 # Semi-major axis of reference ellipsoid
  f = 1.0/298.257222101 # Ellipsoidal flattening
  
  phi0 = -0.0 # Origin latitude, degrees
  lmb0 = +173.0 # Origin longitude, degrees
  
  phi0 = phi0 * math.pi/180.0 # radians
  lmb0 = lmb0 * math.pi/180.0
  
  N0 = 10000000 # False Northing
  E0 = 1600000 # False Easting
  k0 = 0.9996 # Central meridian scale factor
  
  # Projection constants
  b = a * (1.0-f)
  e2 = 2.0*f - f*f
  e4 = e2*e2
  e6 = e4*e2
  A0 = 1.0 - (e2/4.0) - (3.0*e4/64.0) - (5.0*e6/256.0)
  A2 = 3.0/8.0 * (e2 + e4/4.0 + 15.0*e6/128.0)
  A4 = 15.0/256.0 * (e4 + 3.0*e6/4.0)
  A6 = 35*e6/3072
 
  m0 = a * (A0*phi0 - A2*math.sin(2.0*phi0) + A4*math.sin(4.0*phi0) - A6*math.sin(6.0*phi0) )
  
  @classmethod
  def latlng_to_NZTM(cls, phi,lmb):
    """
    Convert geographic lat, lng (NZGD2000 or WGS84) to NZTM2000 map coordinates.
    
    Parameters:
    
      phi : number
        Latitude of computation point, in degrees
      lmb : number
        Longitude of computation point, in degrees
        
    Returns:
      out : (number, number)
        tuple of (E, N) where E easting of computation point and N is northing of computation point
    
    """
    
    # WGS84 Bounds: 166.3300, -47.4000, 178.6000, -34.0000
    if lmb<166.3300 or lmb>178.6000: raise ValueError("longitude out of range for NZTM2000")
    if phi<-47.4000 or phi>-34.0000: raise ValueError("latitude out of range for NZTM2000")

    phi = phi * math.pi/180.0 # convert to radians
    lmb = lmb * math.pi/180.0
    
    # Geographic to Transverse Mercator projection
    
    # calculate main variables
    sin_phi = math.sin(phi)
    sin_phi2 = sin_phi*sin_phi
    m = cls.a * (cls.A0*phi - cls.A2*math.sin(2.0*phi) + cls.A4*math.sin(4.0*phi) - cls.A6*math.sin(6.0*phi) )
    rho = cls.a * (1.0-cls.e2) / (1.0 - cls.e2*sin_phi2) ** 1.5
    nu = cls.a / (1.0 - cls.e2*sin_phi2)**0.5
    psi = nu/rho
    t = math.tan(phi)
    omega = lmb - cls.lmb0
    cos_phi = math.cos(phi)
    
    # pre-calculate higher order variables
    omega2 = omega*omega
    omega4 = omega2*omega2
    omega6 = omega4*omega2
    omega8 = omega6*omega2
    cos_phi2 = cos_phi*cos_phi
    cos_phi3 = cos_phi2*cos_phi
    cos_phi4 = cos_phi3*cos_phi
    cos_phi5 = cos_phi4*cos_phi
    cos_phi6 = cos_phi5*cos_phi
    cos_phi7 = cos_phi6*cos_phi
    psi2 = psi*psi
    psi3 = psi2*psi
    psi4 = psi3*psi
    t2 = t*t
    t4 = t2*t2
    t6 = t4*t2

    N_term1 = omega2/2.0*nu*sin_phi*cos_phi
    N_term2 = omega4/24.0*nu*sin_phi*cos_phi3*(4.0*psi2+psi-t2)
    N_term3 = omega6/720.0*nu*sin_phi*cos_phi5*(8.0*psi4*(11.0 - 24.0*t2) - 28.0*psi3*(1.0 - 6.0*t2) + psi2*(1.0 - 32.0*t2) - psi*(2.0*t2) + t4)
    N_term4 = omega8/40320.0*nu*sin_phi*cos_phi7*(1385- 3111*t2 + 543*t4 - t6)

    E_term1 = omega2/6.0*cos_phi2*(psi-t2)
    E_term2 = omega4/120.0*cos_phi4*(4.0*psi3*(1.0 - 6.0*t2) + psi2*(1.0 + 8.0*t2) - psi*2*t2 + t4)
    E_term3 = omega6/5040.0*cos_phi6*(61.0 - 479.0*t2 + 179.0*t4 - t6)
    
    N = cls.N0 + cls.k0*(m-cls.m0+N_term1+N_term2+N_term3+N_term4)
    E = cls.E0 + cls.k0*nu*omega*cos_phi*(1.0 + E_term1 + E_term2 + E_term3)
    
    return (E,N)
    
  @classmethod
  def NZTM_to_latlng(cls, E, N):
    """
    Convert NZTM2000 map coordinates to geographic lat, lng (NZGD2000 or WGS84).
    
    Parameters:
    
      E : number
        Easting of computation point 
      N : number
        Northing of computation point
        
    Returns:
    
      out : (number, number)
        tuple of (phi,lmb) where phi is latitude of computation point (in degrees) and lmb is longitude of computation point (in degrees)
    """
    
    # Projected Bounds: 983515.7211, 4728776.8709, 2117458.3527, 6223676.2306
    if E<983515 or E>2117459: raise ValueError("E out of range for NZTM2000")
    if N<4728776 or N>6223677: raise ValueError("N out of range for NZTM2000")

    # Transverse Mercator projection to geographic

    # calculate main variables
    N_ = N - cls.N0
    m_ = cls.m0 + N_/cls.k0
    n = (cls.a-cls.b)/(cls.a+cls.b)
    
    # pre-calculate higher order variables
    n2 = n*n
    n3 = n2*n
    n4 = n3*n
    
    # more variables
    G = cls.a*(1.0-n)*(1.0-n2)*(1.0 + 9.0*n2/4.0 + 225.0*n4/64.0)*(math.pi/180.0)
    sigma = m_/G*(math.pi/180.0)
    phi_ = sigma + (3.0*n/2.0 - 27.0*n3/32.0)*math.sin(2.0*sigma) + (21.0*n2/16.0 - 55.0*n4/32.0)*math.sin(4.0*sigma) + 151.0*n3/96.0*math.sin(6.0*sigma)+1097.0*n4/512.0*math.sin(8.0*sigma)
    sin_phi_ = math.sin(phi_)
    sin_phi_2 = sin_phi_*sin_phi_
    rho_ = cls.a * (1.0-cls.e2) / (1.0 - cls.e2*sin_phi_2) ** 1.5
    nu_ = cls.a / (1.0 - cls.e2*sin_phi_2)**0.5
    psi_ = nu_/rho_
    t_ = math.tan(phi_)
    E_ = E - cls.E0
    x = E_/(cls.k0*nu_)

    # pre-calculate higher order variables
    x2 = x*x
    x3 = x2*x
    x5 = x3*x2
    x7 = x5*x2
    psi_2=psi_*psi_
    psi_3=psi_2*psi_
    psi_4=psi_3*psi_
    psi_5=psi_4*psi_
    t_2 = t_*t_
    t_4 = t_2*t_2
    t_6 = t_4*t_2

    phi_tk0rho = t_/(cls.k0*rho_) # used in all terms

    phi_term1 = phi_tk0rho * E_*x/2.0
    phi_term2 = phi_tk0rho * E_*x3/24.0 * (-4.0*psi_2 + 9.0*psi_*(1.0-t_2) + 12.0*t_2)
    phi_term3 = phi_tk0rho * E_*x5/720.0 * (8.0*psi_4*(11.0 - 24*t_2) - 12*psi_3*(21.0 - 71.0*t_2) + 15*psi_2*(15.0 - 98.0*t_2 + 15*t_4) + 180.0*psi_*(5*t_2 - 3*t_4) + 360.0*t_4)
    phi_term4 = phi_tk0rho * E_*x7/40320.0 * (1385.0 - 3633.0*t_2 + 4095.0*t_4 + 1575.0*t_6)
    
    phi = phi_ - phi_term1 + phi_term2 - phi_term3 + phi_term4
    sec_phi_ = 1.0/math.cos(phi_)

    lmb_term1 = x * sec_phi_
    lmb_term2 = x3 * sec_phi_ / 6.0 * (psi_ + 2*t_2)
    lmb_term3 = x5 * sec_phi_ / 120.0 * (-4.0*psi_3*(1.0 - 6.0*t_2) + psi_2*(9.0 - 68.0*t_2) + 72.0*psi_*t_2 + 24.0*t_4)
    lmb_term4 = x7 * sec_phi_ / 5040.0 * (61.0 + 662.0*t_2 + 1320*t_4 + 720*t_6)

    lmb = cls.lmb0 + lmb_term1 - lmb_term2 + lmb_term3 - lmb_term4

    phi = phi * 180.0/math.pi
    lmb = lmb * 180.0/math.pi
    
    return (phi,lmb)


if __name__ == "__main__":

  print "%.2f mE    %.2f mN"%NZTM2000.latlng_to_NZTM(-36.884391, 174.749642)
  # expect 1755918.47 mE    5916523.26 mN (NZ Map Reference Converter; http://www.linz.govt.nz/geodetic/software-downloads#nzmapconv)
  # got    1755918.47 mE    5916523.26 mN

  print "%.8f     %.8f"%NZTM2000.NZTM_to_latlng(1755918.47, 5916523.26)
  # expect 36.88439104S    174.74964195E
  # got   -36.88439105     174.74964195 # not sure why slight error in this
  
  # WGS84 Bounds: 166.3300, -47.4000, 178.6000, -34.0000
  print "%.2f mE    %.2f mN"%NZTM2000.latlng_to_NZTM(-47.4000, 166.3300)
  # expect 1096802.28 mE    4728776.87 mN
  # got    1096802.28 mE    4728776.87 mN

  print "%.2f mE    %.2f mN"%NZTM2000.latlng_to_NZTM(-34.0000, 178.6000)
  # expect 2117458.35 mE    6223676.23 mN
  # got    2117458.35 mE    6223676.23 mN
  
  print "%.2f mE    %.2f mN"%NZTM2000.latlng_to_NZTM(-34.0000, 166.3300)
  # expect 983515.72 mE    6217723.72 mN
  # got    983515.72 mE    6217723.72 mN
  
  print "%.8f     %.8f"%NZTM2000.NZTM_to_latlng(1096802.28,4728776.8709)
  # expect 47.40000000S    166.33000001E
  # got   -47.39999998     166.33000001
  
  print "%.8f     %.8f"%NZTM2000.NZTM_to_latlng(2117458.3527, 6223676.2306)
  # expect 34.00000000S    178.60000000E
  # got   -33.99999999     178.60000000
  

