# -*- coding: utf-8 -*-
"""plateau_floodsar_lib.py

This module contains classes and methos to utilize DEM tiles from the Geospatial Information Authority of Japan(GIAJ).

This module is indeed developed for PLATEAU-FloodSAR project, yet it would be
useful for similar projects.

"""
import numpy as np
import math
import requests
from shapely.geometry import Polygon, Point
import numpy
from typing import Tuple
import os
import io
import copy
from progressbar import progressbar
import skimage
from skimage import measure

#__LATLIMIT = 85.0511
#__YZERO = math.atanh(math.sin(math.radians(__LATLIMIT)))
__TD = 256
__DEMLIST = [
    {"error":0.3, "type":"dem5a", "z":15},
    {"error":0.7, "type":"dem5b", "z":15},
    {"error":5.0, "type":"dem", "z":14}
] # use dem with less error value
# ref: https://maps.gsi.go.jp/development/hyokochi.html

def translate_to_lats(ys, z):
    n = __TD * (2.0 ** z) # in pixel scale
    ycorr = np.pi * (1.0-2.0*np.array(ys)/n)
    lat_rad = np.arcsin(np.tanh(ycorr))
    lat_deg = np.degrees(lat_rad)
    return lat_deg

def translate_to_ys(lats, z):
    return np.floor(translate_to_ys_float(lats,z))

def translate_to_ys_float(lats, z):
    n = __TD * (2.0 ** z) # in pixel scale
    return (1.0-np.arcsinh(np.tan(np.radians(np.array(lats))))/np.pi)*n/2.0

def calc_xyz_from_lonlat(lon: float, lat: float, z: int):
    """緯度と経度を含むタイルのXYZ座標を計算する関数
    国土地理院用
    """
    #print(lon, lat, z)
    n = 2.0 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int( (1.0-np.arcsinh(np.tan(np.radians(lat)))/np.pi)*n/2.0 )
    #print(f"calc_xyz_from_lonlat: ({lat}, {lon}) => ({z}/{x}/{y})")
    return (x, y) #, (lon, lat)

def calc_lonlat_from_xyz(x, y, z):
    """XYZ座標のタイルの起点の緯度と経度を計算する関数
    国土地理院用
    """
    n = 2.0 ** z
    lon_deg = x / n * 360.0 - 180.0
    ycorr = np.pi * (1.0-2.0 * y / n)
    lat_rad = np.arctan(np.sinh(ycorr))
    lat_deg = np.degrees(lat_rad)
    #print(f"calc_lonlat_from_xyz: ({z}/{x}/{y}) => ({lat_deg}, {lon_deg})")
    return lon_deg, lat_deg

def generate_lonslats_from_boundbox(boundbox: Tuple[float,float,float,float],
    shape: Tuple[int,int], dir_w2e: bool = True, dir_n2s: bool = True):
    """calc_bounds_of_tiles

    Generates lists of longitudes and latitudes of a given boundary and
    sizes (in the term of a shape).

    Args:
        boundbox (Tuple): (lon_min, lat_min, lon_max, lat_max)
        shape (Tuple): (size of latitudes, size of longitudes)
        dir_w2e (bool): flag for the direction. True if from West to East.
                        Default is True.
        dir_n2s (bool): flag for the direction. True if from North to South.
                        Default is True.
    Returns:
        Tuple: (longitudes (list), latitudes (list))
    """
    lons = np.linspace(boundbox[0],boundbox[2],shape[0]+1, endpoint=True)
    lats = np.linspace(boundbox[1],boundbox[3],shape[1]+1, endpoint=True)
    if dir_w2e:
        lons = lons[:-1]
    else:
        lons = lons[1:][::-1]
    if not dir_n2s:
        lats = lats[:-1]
    else:
        lats = lats[1:][::-1]
    return lons, lats

def calc_bounds_of_tiles(x: int, y: int, z: int, xnum: int = 1, ynum: int = 1):
    """calc_bounds_of_tiles

    xnum*ynumのXYZタイルのboundsを返す

    Args:
        x (int): x value along longitude of XYZ-tile coordinate
        y (int): y value along latitude of XYZ-tile coordinate
        z (int): z value or zoom level of XYZ-tile coordinate
        xnum (int): number of tiles in x direction. Default value is 1.
        ynum (int): number of tiles in y direction. Default value is 1.

    Returns:
        Tuple: (lon_min, lat_min, lon_max, lat_max)
    """
    lon_a, lat_a = calc_lonlat_from_xyz(x,y,z)
    lon_b, lat_b = calc_lonlat_from_xyz(x+xnum,y+ynum,z)
    lon_min, lon_max = sorted([lon_a, lon_b])
    lat_min, lat_max = sorted([lat_a, lat_b])
    return (lon_min, lat_min, lon_max, lat_max)

def calc_lonslats_of_tiles(x: int, y:int, z:int, xnum: int = 1, ynum: int = 1):
    """calc_lonslats_of_tiles

    xnum*ynumのXYZタイルのlongitudesとlatitudesを返す

    Args:
        x (int): x value along longitude of XYZ-tile coordinate
        y (int): y value along latitude of XYZ-tile coordinate
        z (int): z value or zoom level of XYZ-tile coordinate
        xnum (int): number of tiles in x direction. Default value is 1.
        ynum (int): number of tiles in y direction. Default value is 1.

    Returns:
        Tuple: (longitudes (list), latitudes (list))
    """
    #print(f"Calculating lons and lats of x={x}-{x+xnum}, y={y}-{y+ynum} at z={z}") #checknow
    linx = x + np.arange(0.0, xnum+1,1.0/__TD)
    liny = y + np.arange(0.0, ynum+1,1.0/__TD)
    return calc_lonlat_from_xyz(linx, liny, z)
    #bbox = calc_bounds_of_tiles(x,y,z, xnum=xnum, ynum=ynum)
    #return generate_lonslats_from_boundbox(bbox,(__TD*xnum,__TD*ynum))

def calc_floatIdx_of_list(val:float, list):
    """
    Args:
        val (float): value which the method finds index for.
        list (array-like): must be ordered (ascending or descending)
    """
    return (val - list[0])/(list[-1]-list[0]) * (len(list)-1)

def calc_interpval_of_list(idx:float, list):
    il = int(idx)
    ih = int(idx + 1)
    if ih >= len(list):
        return list[-1]
    dd = idx - il
    return (1-dd)*list[il] + dd*list[ih]

class GiajDemHandler:
    """GiajDemHandler class for DEM-tile management.

    The GiajDemHandler class downloads and manages DEM tiles from GIAJ.
    The type of DEM tile and the zoom level are set at the initialization.

    """

    def __init__(self, path:str="/tmp/", dem_type: str = "dem5a", zoom: int = 15, tilesize: int = 256):
        """__init__ method

        Args:
            path (str): saving path of the DEM files.
            dem_type (str): type of DEM. Default is "dem5a".
            zoom (int): zoom level. Default is 15.
        """
        self.tiles = {} # dict: storing tiles with key "{x}/{y}"

        self.path = path #str: saving path of the DEM files.
        if self.path[-1] != "/":
            self.path += "/"
        self.path += f"DEM/{dem_type}/{zoom}/"
        self.prep_dir(self.path)

        self.urldir =  f"https://cyberjapandata.gsi.go.jp/xyz/{dem_type}/{zoom}/"
        # str: URL of the dir of DEM tiles of given dem_type.

        self.zoom = zoom # int: zoom level
        self.numtiles = int(2**zoom)
        self.alltilebounds = [self.numtiles,self.numtiles,-1,-1]
        self.TD = tilesize
        self.numpixels = self.numtiles * self.TD

        self.alllons, self.alllats = calc_lonslats_of_tiles(0,0,self.zoom,self.numtiles,self.numtiles)
        #print(f"lons: {self.alllons}") #checknow
        #print(f"lats: {self.alllats}") #checknow
        #self.alllats = translate_to_lats(np.arange(0,self.numtiles*self.TD),zoom)

    def get_lonslats_of_tiles(self, x:int, y:int, xnum:int=1, ynum:int=1):
        return np.copy(self.alllons[x*self.TD:(x+xnum)*self.TD]), np.copy(self.alllats[y*self.TD:(y+ynum)*self.TD])

    def load_dem_tiles(self, boundary:Polygon, multiple: int = 1) -> None:
        """load_dem_tiles method
        Args:
            boundary (Polygon):
            multiple (int): base number of tile width and height

        Returns:
            None:
        """
        sx, sy, ex, ey = self.calc_boundidices(boundary.bounds,
            multiple=multiple)
        for ii in progressbar(range(sx, ex+1)):
            for jj in range(sy, ey+1):
                self.load_dem_tile(int(ii), int(jj))

    def get_dem_tile_of_lonlat(self, lon: float, lat: float):
        x, y = calc_xyz_from_lonlat(lon, lat, self.zoom)
        return copy.deepcopy(self.get_tile_safe(x,y))

    def calc_dem_interp(self, lon: float, lat: float):
        """calc_dem_interp method

        Calculates linearly interpolated value of DEM at the given location.

        Args:
            lon (float): longitude
            lat (float): latitude

        Returns:
            float: DEM
        """
        tx, ty = calc_xyz_from_lonlat(lon,lat,self.zoom)
        tile0 = self.get_tile_safe(tx,ty)
        cx = calc_floatIdx_of_list(lon, tile0["lons"])
        cy = calc_floatIdx_of_list(lat, tile0["lats"])
        xl = int(cx)
        yl = int(cy)
        flg_recal = False
        if xl >= self.TD :
            tx += 1
            flg_recal = True
            #print("wrong scale on xl: ", xl,)
            #print(tile0["lons"])
            #print(lon)
        if yl >= self.TD:
            ty += 1
            flg_recal = True
            #print("wrong scale on yl: ", yl)
            #print(tile0["lats"])
            #print(lat, lat-tile0["lats"][-1], (lat-tile0["lats"][0]),(tile0["lats"][-1]-tile0["lats"][0]),(lat-tile0["lats"][0])/(tile0["lats"][-1]-tile0["lats"][0])*255)
        if flg_recal:
            tile0 = self.get_tile_safe(tx,ty)
            cx = calc_floatIdx_of_list(lon, tile0["lons"])
            cy = calc_floatIdx_of_list(lat, tile0["lats"])
            xl = int(cx)
            yl = int(cy)
        #print((lon,lat)) #checknow
        #print(tile0["lons"]) #checknow
        #print(tile0["lats"]) #checknow
        xh = xl + 1
        dx = cx-xl
        yh = yl + 1
        dy = cy - yl
        #print(np.shape(tile0["dem"]), (yl, xl))
        dem_ll = tile0["dem"][yl,xl]
        if xh < self.TD:
            dem_lh = tile0["dem"][yl,xh]
            if yh < self.TD:
                dem_hl = tile0["dem"][yh,xl]
                dem_hh = tile0["dem"][yh,xh]
            else:
                tmp = self.get_tile_safe(tx,ty+1)
                dem_hl = tmp["dem"][0,xl]
                dem_hh = tmp["dem"][0,xh]
        else:
            tmp = self.get_tile_safe(tx+1,ty)
            dem_lh = tile0["dem"][yl,0]
            if yh < self.TD:
                dem_hl = tile0["dem"][yh,xl]
                dem_hh = tmp["dem"][yh,0]
            else:
                tmp = self.get_tile_safe(tx,ty+1)
                dem_hl = tmp["dem"][0,xl]
                tmp = self.get_tile_safe(tx+1,ty+1)
                dem_hh = tmp["dem"][0,0]

        return (1-dy)*(1-dx)*dem_ll + (1-dy)*dx*dem_lh + dy*(1-dx)*dem_hl + dy*dx*dem_hh

    def produce_tile_stiched(self, boundary:Polygon = None, multiple: int = 1):
        """produce_tile_stiched method

        This method produces one large tile of a given boundary.
        Numbers of tiles used in width and height are forced to be a multiple
        of a given multiple value with additional tiles surrounding the
        rectangular configuration of tiles least to enclose the given boundary.
        For example, you can set multiple=2 to get even numbers of tiles are
        used in both width and height.

        Args:
            boundary (Polygon):
            multiple (int): base number of tile width and height. Default is 1
        """
        #print("start stiching") #checknow
        if len(self.tiles) == 0:
            return None

        if boundary is None:
            sx, sy, ex, ey = self.alltilebounds
        else:
            sx, sy, ex, ey = self.calc_boundidices(boundary.bounds,
                multiple=multiple)
        xnum = ex-sx+1
        ynum = ey-sy+1
        dem = np.zeros((self.TD*ynum,self.TD*xnum))
        #print(dem.shape)
        isx = -self.TD
        for xx in range(sx, ex+1):
            isx += self.TD
            isy = -self.TD
            for yy in range(sy, ey+1):
                isy += self.TD
                tile = self.get_tile_safe(xx,yy)
                #print((isy,isx))
                dem[isy:isy+self.TD,isx:isx+self.TD] = tile["dem"]
        lons, lats = self.get_lonslats_of_tiles(sx, sy, xnum=xnum, ynum=ynum)
        #print("finish stiching") #checknow
        return {"dem":dem, "lons":lons, "lats":lats,
            "tilebounds":(sx, sy, ex, ey)}

    def calc_boundidices(self,boundary: Tuple[float,float,float,float],
        multiple: int=1):
        """
        Args:
            boundary (tuple): (lon_min, lat_min, lon_max, lat_max)
            multiple (int): base number of tile width and height

        Returns:
            Tuple: 4 indices (start_x, start_y, end_x, end_y)
        """
        sx, sy = calc_xyz_from_lonlat(boundary[0],boundary[3], self.zoom)
        ex, ey = calc_xyz_from_lonlat(boundary[2],boundary[1], self.zoom)
        elon, elat = calc_lonlat_from_xyz(ex, ey, self.zoom)
        # Trim last tiles if boundary is exactly at the tile boundary,
        if boundary[2] == elon:
            ex -= 1
        if boundary[1] == elat:
            ey -= 1
        dx = int((multiple - (ex-sx+1)) % multiple)
        sx -= int(dx/2)
        ex += int((dx+1)/2)
        dy = int((multiple - (ey-sy+1)) % multiple)
        sy -= int(dy/2)
        ey += int((dy+1)/2)
        return (sx, sy, ex, ey)

    def get_tile_safe(self, x: int , y: int):
       """
       """
       xcorr = int(x % self.numtiles)
       key = f"{xcorr}/{y}"
       if key not in self.tiles:
           self.load_dem_tile(xcorr,y)
       return self.tiles[key]

    def load_dem_tile(self, x: int, y: int):
        """
        """
        #print(f"loading tile {x}/{y}") #checknow
        xcorr = int(x % self.numtiles)
        key = f"{xcorr}/{y}"
        dirpath = self.path+f"{xcorr}/"
        txtfile = self.path+key+".txt"
        npyfile = self.path+key+".npy"
        self.prep_dir(dirpath)
        if os.path.isfile(npyfile):
            #print("loading ", npyfile)
            #print(f"loading {npyfile}")
            dem = np.load(npyfile)
        else:
            #print("retrieving ", npyfile)
            flg_nodata = False
            if os.path.isfile(txtfile):
                with open(txtfile, "r") as ifile:
                    txt = ifile.read()
            else:
                #print(f"downloading {self.urldir+key+'.txt'}")
                response = requests.get(self.urldir+key+".txt")
                #print(f"response.status_code = {response.status_code}")
                if response.status_code == 200:
                    txt = response.text
                    with open(txtfile, "w") as ofile:
                        ofile.write(txt)
                else:
                    dem = np.empty((self.TD, self.TD), float)
                    dem[::] = np.nan
                    flg_nodata = True
            if not flg_nodata:
                dem = np.array(
                    [
                        list(map(lambda v: float(v) if v!='e' else np.nan,
                        row.split(',')))
                        for row in txt.strip().split('\n')
                    ] # chhanged 2023Oct25: response.text => txt
                )
                np.save(npyfile, dem)
        lons, lats = self.get_lonslats_of_tiles(xcorr,y)
        self.set_tile(xcorr,y,dem,lons,lats)
        #print("finish loading") #checknow

    def set_tile(self, x, y, dem, lons, lats):
        key = f"{x}/{y}"
        self.tiles[key] = {
            "name":key,
            "dem":dem,
            "lons":lons,
            "lats":lats
        }
        if self.alltilebounds[0] > x:
            self.alltilebounds[0] = x
        if self.alltilebounds[1] > y:
            self.alltilebounds[1] = y
        if self.alltilebounds[2] < x:
            self.alltilebounds[2] = x
        if self.alltilebounds[3] < y:
            self.alltilebounds[3] = y

    def prep_dir(self,path:str):
        """__prep_dir method

        Check the exixtence of the target directory of a given path.
        Make directories down to the target directory if it does not exist.

        Args:
            path (str): path of directory
        """
        if not os.path.exists(path):
            os.makedirs(path)


    def get_lats(self, start_lat:float, end_lat:float):
        ys = np.sort(translate_to_ys([start_lat,end_lat]))
        return self.lats[int(ys[0]):int(ys[1]+1)]

    def get_lats_of_tiles(start_y:int, end_y:int):
        return self.lats[int(start_y*self.TD), int((end_y+1)*self.TD)]

    def get_lons(self, start_lon:float, end_lon:float):
        xs = int((start_lon + 180.0) / 360.0 * self.numpixels)
        xe = int((end_lon + 180.0) / 360.0 * self.numpixels)
        return np.linspace(start_lon,end_lon,xe-xs+1,endpoint=True)

    def get_lons_of_tiles(self, start_x:int, end_x:int):
        lon_s = start_x / self.numpixels * 360.0 - 180.0
        lon_e = (end_x+1) / self.numpixels * 360.0 - 180.0
        return np.linspace(lon_s, lon_e, (end_x-start_x+1)*self.TD)

    def calc_floatIdxs(self, lon:float, lat:float):
        x, y = self.alltilebounds[0:2]
        return self.calc_floatIdxs_of_tile(lon,lat,x,y)

    def calc_floatIdxs_globe(self, lon:float, lat:float):
        x = (lon + 180.0) / 360.0 * self.numpixels
        y = translate_to_ys_float(lat, self.zoom)
        return (x, y)

    def calc_floatIdxs_of_tile(self, lon:float, lat:float, x:int, y:int):
        xf, yf = self.calc_floatIdxs_globe(lon,lat)
        return (xf-x*self.TD, yf-y*self.TD)
### End of GiajDemHandler class


class GiajGeoidHandler(GiajDemHandler):
  def __init__(self, path:str="/tmp/", zoom: int = 8, tilesize: int = 256):
    super().__init__(path, zoom=zoom, dem_type="geoid", tilesize=tilesize)
    self.urldir = f"https://tiles.gsj.jp/tiles/elev/gsigeoid/{zoom}/"
    # self.path = f"{path}/GEOID/geoid/{zoom}/"
    # self.prep_dir(self.path)

  def tilepngarr_to_values(self, img_array):
    r = img_array[:, :, 0].astype(np.int8)
    g = img_array[:, :, 1]
    b = img_array[:, :, 2]
    mask = img_array[:, :, 3]
    dem = (65536 * r.astype(int) + 256 * g + b) * 0.0001
    dem[mask == 0] = np.nan
    return dem

  def load_dem_tile(self, x: int, y: int):
        """
        """
        xcorr = int(x % self.numtiles)
        key = f"{xcorr}/{y}"
        urlkey = f"{y}/{xcorr}"
        dirpath = self.path+f"{xcorr}/"
        txtfile = self.path+key+".png"
        npyfile = self.path+key+".npy"
        self.prep_dir(dirpath)
        if os.path.isfile(npyfile):
            #print("loading ", npyfile)
            #print(f"loading {npyfile}")
            dem = np.load(npyfile)
        else:
            #print("retrieving ", npyfile)
            flg_nodata = False
            if os.path.isfile(txtfile):
                # with open(txtfile, "r") as ifile:
                #     txt = ifile.read()
                tile_data = skimage.io.imread(txtfile)
            else:
                #print(f"downloading {self.urldir+key+'.txt'}")
                response = requests.get(self.urldir+urlkey+".png")
                #print(f"response.status_code = {response.status_code}")
                if response.status_code == 200:
                    txt = response.content
                    with open(txtfile, "wb") as ofile:
                        ofile.write(txt)
                    tile_data = skimage.io.imread(io.BytesIO(txt), plugin='imageio')
                else:
                    dem = np.empty((self.TD, self.TD), float)
                    dem[::] = np.nan
                    flg_nodata = True
            if not flg_nodata:
                dem = self.tilepngarr_to_values(tile_data)
                np.save(npyfile, dem)
        lons, lats = self.get_lonslats_of_tiles(xcorr,y)
        self.set_tile(xcorr,y,dem,lons,lats)

  def produce_tile_stiched(self, boundary:Polygon = None, multiple: int = 1):
    tile = super().produce_tile_stiched(boundary, multiple)
    tile['geoid'] = tile['dem']
    del tile['dem']
    return tile
### End of GiajGeoidHandler class

class GiajDemManager(GiajDemHandler):
    """GiajDemHandler class for DEM-tile management.

    The GiajDemManager class utilizes several types of DEM at once.
    The type of DEM tile and the zoom level are set at the initialization.

    """

    def __init__(
        self, path:str,
        dem_types = [
            {"type":"dem5a","z":15},
            {"type":"dem5b","z":15},
            {"type":"dem","z":14}
        ], tilesize: int = 256
    ):
        """
        """
        ss = "combined_"+"-".join([tt["type"] for tt in dem_types])
        super().__init__(path, dem_type = ss, zoom= dem_types[0]["z"])
        #print(self.path)
        #self.zoom = dem_types[0]['z']
        #self.path = path+f"DEM/{ss}/{self.zoom}"
        #self.numtiles = int(2**self.zoom)
        #self.TD = tilesize

        self.tiles = {}
        self.handlers = []

        for dts in dem_types:
            self.handlers.append(
                GiajDemHandler(path,dem_type=dts["type"], zoom=dts["z"])
            )

    def load_dem_tile(self, x: int, y: int):
        """
        """
        #print("Child method is called.")
        xcorr = int(x % self.numtiles)
        key = f"{xcorr}/{y}"
        dirpath = self.path+f"{xcorr}/"
        npyfile = self.path+key+".npy"
        self.prep_dir(dirpath)
        key = f"{xcorr}/{y}"
        dirpath = self.path+f"{xcorr}/"
        npyfile = self.path+key+".npy"
        lons, lats = self.get_lonslats_of_tiles(xcorr,y)
        clon = lons[int(len(lons)/2)]
        clat = lats[int(len(lats)/2)]
        #print(f"GDM: loading {key} ({clon,clat})") #checknow
        self.prep_dir(dirpath)
        if os.path.isfile(npyfile):
            #print("loading ",npyfile)
            dem = np.load(npyfile)
        else:
            tile = self.handlers[0].get_dem_tile_of_lonlat(clon,clat)
            dem = tile["dem"]
            #print("filling -1s")
            for ii, lon in enumerate(lons):
                for jj, lat in enumerate(lats):
                    if np.isnan(dem[jj,ii]):
                        #cnt = 0
                        for hdl in self.handlers[1:]:
                            #print(cnt)
                            #cnt += 1
                            dem_tmp = hdl.calc_dem_interp(lon, lat)
                            if not np.isnan(dem_tmp):
                                dem[jj,ii] = dem_tmp
                                break
            np.save(npyfile, dem)
        self.set_tile(xcorr,y,dem,lons,lats)
### End of GiajDemManager class

class ValueBoundInspector:
    def __init__(self, demhandler, scale=None, method=lambda data, val: data<val, minarea = 0):
        """
        """
        if not issubclass(type(demhandler), GiajDemHandler):
            raise InputError("ValueBoundInspector must be initialized with an instance of GiajDemHandler class or its subclass.")
        self.demhndlr = demhandler
        tile = demhandler.produce_tile_stiched()
        data = tile["dem"]
        lons = tile["lons"]
        lats = tile["lats"]
        numx, numy = data.shape
        self.data = np.empty((numx+2,numy+2))
        self.data[:,:] = np.nan
        self.data[1:-1,1:-1] = data
        self.lons = np.empty((len(lons)+2))
        self.lons[1:-1]= lons
        self.lons[0] = 2 * lons[0] - lons[1]
        self.lons[-1] = 2 * lons[-1] - lons[-2]
        self.lats = np.empty((len(lats)+2))
        self.lats[1:-1]= lats
        self.lats[0] = 2 * lats[0] - lats[1]
        self.lats[-1] = 2 * lats[-1] - lats[-2]
        if scale is None:
            self.set_scale_auto()
        else:
            self.scale = np.sort(np.array(scale))
        self.cntrsets = {}
        self.method = method
        self.minarea = minarea

    def calc_floatIdxs(self, lon, lat):
        idx = calc_floatIdx_of_list(lon,self.lons)
        idy = calc_floatIdx_of_list(lat,self.lats)
        return (idx, idy)

    def calc_lonlat(self, x, y):
        lon = calc_interpval_of_list(x,self.lons)
        lat = calc_interpval_of_list(y,self.lats)
        return (lon, lat)

    def calc_area_bound(self,lon,lat,val):
        if val <= self.scale[0]:
            sl = -1
        else:
            tmp = list(np.where(self.scale <= val)[-1])
            sl = int(tmp[-1])
        sh = sl+1
        idx, idy = np.floor(self.calc_floatIdxs(lon,lat))
        al = self.find_area_from_idpt(idx, idy, sl)
        ah = self.find_area_from_idpt(idx, idy, sh)
        if al < 0:
            return ah
        if ah < 0:
            return al
        ds = val - self.scale[sl]
        return (1-ds)*al + ds*ah

    def get_mindem_bound(self,lon,lat,val):
        if val <= self.scale[0]:
            sl = -1
        else:
            tmp = list(np.where(self.scale <= val)[-1])
            sl = int(tmp[-1])
        sh = sl+1
        idx, idy = np.floor(self.calc_floatIdxs(lon,lat))
        mdl = self.find_mindem_from_idpt(idx, idy, sl)
        mdh = self.find_mindem_from_idpt(idx, idy, sh)
        return np.nanmin([mdl,mdh])

    def find_area_from_idpt(self, idx: int, idy: int, sid, minarea=0):
        if sid < 0 or len(self.scale) <= sid:
            return -1
        if sid not in self.cntrsets:
            self.set_cntrs_for_scaleidx(sid)
        label = self.cntrsets[sid]["labeledmap"][int(idy),int(idx)]
        if label not in self.cntrsets[sid]["areas"]:
            self.cntrsets[sid]["areas"][label] = np.count_nonzero(self.cntrsets[sid]["labeledmap"]==label)
        return self.cntrsets[sid]["areas"][label]

    def find_mindem_from_idpt(self, idx: int, idy: int, sid):
        if sid < 0 or len(self.scale) <= sid:
            return np.nan
        if sid not in self.cntrsets:
            self.set_cntrs_for_scaleidx(sid)
        label = self.cntrsets[sid]["labeledmap"][int(idy),int(idx)]
        if label not in self.cntrsets[sid]["mindems"]:
            self.cntrsets[sid]["mindems"][label] = np.nanmin( self.data[np.where(self.cntrsets[sid]["labeledmap"]==label)] )
        return self.cntrsets[sid]["mindems"][label]

    def set_scale_auto(self, num:int = 100):
        self.scale = np.linspace(np.nanmin(self.data), np.nanmax(self.data),num,endpoint=True)

    def set_cntrs_for_scaleidx(self,sid):
        val = self.scale[sid]
        tmpmap = self.generate_labeledmap(val)
        numlabels = np.nanmax(tmpmap)
        areas = {}
        areas[0] = np.nan
        mindems = {}
        mindems[0] = np.nan
        #for ii in np.arange(1,numlabels):
        #    areas[ii] = np.count_nonzero(tmpmap==ii)
        self.cntrsets[sid] = {
            "val":val,
            "labeledmap": tmpmap,
            "areas": areas,
            "mindems": mindems
        }

    def generate_boundmap_exact(self, lon, lat, val):
        tmpmap = self.generate_labeledmap(val)
        idx, idy = np.floor(self.calc_floatIdxs(lon,lat))
        resmap = np.zeros_like(tmpmap)
        resmap[np.where(tmpmap == tmpmap[int(idy),int(idx)])] = 1
        return resmap

    def generate_labeledmap(self, val):
        binary_map = self.method(self.data, val)
        return measure.label(binary_map,connectivity=1, background=0)

    def set_cntrs_all(self):
        print("Preparing all contours")
        for ii in progressbar(range(len(self.scale))):
            if ii not in self.cntrsets:
                self.set_cntrs_for_scaleidx(ii)

    def translate_polygon_in_lonlat(self, polygon):
        xx, yy = polygon.exterior.xy
        poly = []
        for x, y in zip(xx,yy):
            poly.append(self.calc_lonlat(x,y))
        return Polygon(poly)

    def release_cntrs_all(self):
        del self.cntrsets
        self.cntrsets = {}
### End of ValueBoundInspector
