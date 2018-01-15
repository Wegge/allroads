#! /usr/bin/env python3

import collections
import gpxpy
import pyproj
import svgwrite
import urllib.request
import math

from urllib.error import HTTPError


dagi = pyproj.Proj(init='epsg:4326')
u32 = pyproj.Proj(init='epsg:23032')

TrkSeg = collections.namedtuple('TrkSeg', 'x1 y1 x2 y2')
TrkCnt = collections.Counter()

# Skagen
startLat = '57.7195821262563'
startLon = '10.553680148866'

INFILE = 'RegionOutline'
LOCATIONS = 'DK_locations.csv'


def scale_UTM32(lon, lat):
    return (lon-421499)/100, (6422253-lat)/100


def get_route(lon, lat, kode):

    req = f'http://localhost:8989/route?point={startLat}%2C{startLon}&'
    req += f'point={lat}%2C{lon}&type=gpx&instructions=false&vehicle=car'

    try:
        resp = urllib.request.urlopen(req)
        gpxData = gpxpy.parse(str(resp.read(), 'utf-8'))

        lonStart, latStart = None, None
        for pt in gpxData.tracks[0].segments[0].points:

            lonEnd, latEnd = pyproj.transform(dagi, u32,
                                              pt.longitude, pt.latitude)
            lonEnd, latEnd = scale_UTM32(lonEnd, latEnd)
            if lonStart is not None:
                TrkCnt[TrkSeg(lonStart, latStart, lonEnd, latEnd)] += 1
            lonStart, latStart = lonEnd, latEnd

    except HTTPError as e:
        print(f'bad request on location index {kode}')
        print(req)
        pass


def buildpath(line):
    mapid, region, polygon = line.split('|')

    print(mapid, region, ' '*30, end='\r')

    polyline = ["M"]

    for node in polygon.split(',')[1:]:
        tlon, tlat, *_ = node.split(' ')
        lon, lat = scale_UTM32(float(tlon), float(tlat))
        polyline.append(f"{lon},{lat}")
    polyline.append("z")

    return " ".join(polyline)


def main():

    regionmap = svgwrite.Drawing(filename="Basemap.svg",
                                 debug=False,
                                 size=(4915, 3925))

    style = """
    line {
        stroke-width: 1mm;
        stroke-linecap:butt;
    }"""

    colours = [
        "990000", "d7301f", "ef6548", "fc8d59",
        "fdbb84", "fdd49e", "fef0d9"]

    for lev, coldef in enumerate(colours):
        style = style + f"g.l{lev} line {{stroke: #{coldef}; stroke-opacity: 1;fill: none;}}"

    regionmap.add(regionmap.style(style))

    regionmap.add(regionmap.rect(insert=(0, 0), size=('100%', '100%'),
                                 stroke='none', fill='#87dde5'))
    landgrp = regionmap.add(regionmap.g(id="Land",
                                        fill='black', stroke='black'))

    print ("Adding map shapes:")
    
    with open(INFILE, 'r') as fh:
        for regionpart in fh:
            if 'MULTIPOLYGON' in regionpart:
                p = buildpath(regionpart)
                landgrp.add(regionmap.path(d=p))
            pass

    print ("\n\nFetching routes:")

    with open(LOCATIONS, 'r') as fh:
        for destination in fh:
            if destination.startswith('#'):
                continue
            kode, navn, lon, lat = destination.strip().split(',')
            if not kode.isnumeric():
                continue
            print(kode, navn, ' '*30, end='\r')
            get_route(lon, lat, kode)

    print ("\n\nAdding route segments:")

    groups = []
    for lev, coldef in enumerate(colours):
        groups.append(regionmap.add(regionmap.g()))
        groups[lev]['class'] = f'l{lev}'

    HighCount = TrkCnt.most_common(1)[0][1]
    level_adjust = (math.exp(7) - 1)/HighCount
    AddCnt = 0
    
    for seg, count in TrkCnt.items():
        destgrp = groups[int(math.log(count*level_adjust))]
        destgrp.add(regionmap.line(start=(seg.x1, seg.y1),
                                 end=(seg.x2, seg.y2)))
        AddCnt += 1
        if AddCnt % 1000 == 0:
            print (f"{AddCnt}", end='\r')

    print (f"{AddCnt}", end='\r')
    print ("\n\nSaving to disk.")
    regionmap.save()
    print ("\nDone")
    
if __name__ == '__main__':
    main()
