# coding: utf-8
import datetime as dt
import json
import logging
import pprint

import bs4
import requests

logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s")
log = logging

TRIMET_STOPS_URL = 'https://developer.trimet.org/gis/data/tm_stops.kml'
TRIMET_ROUTE_STOPS_URL = 'https://developer.trimet.org/gis/data/tm_route_stops.kml'
URL = TRIMET_ROUTE_STOPS_URL


def get_data():
    log.info("Fetching TriMet routes/stops data from '{}'".format(URL))
    resp = requests.get(URL)
    resp.raise_for_status()

    try:
        content_size = int(int(resp.headers['Content-Length'])/1024)
    except (TypeError, KeyError):
        content_size = 'Unknown'

    log.info("Parsing KML. File size: {}kb".format(content_size))
    route_stops_kml = resp.content
    soup = bs4.BeautifulSoup(route_stops_kml, 'lxml')

    placemarks = soup.find_all('placemark')
    entries = []
    for p in placemarks:
        row = {}
        for el in p.find_all('data'):
            row[el.attrs['name']] = el.value.contents[0]
        row['lat'], row['long'] = p.find('coordinates').contents[0].split(',')
        entries.append(row)

    log.info("Found {} TriMet routes/stops with {} attributes".format(
        len(entries), len(entries[0].keys())))

    return entries
        

def save_data(data):
    fname = 'active_trimet_route_stops-{:%Y-%m-%d}.json'.format(dt.date.today())
    log.info("Saving TriMet routes/stops to file '{}'".format(fname))
    json.dump(data, open(fname, 'w'), indent=2)
    return fname


if __name__ == '__main__':
    import sys

    data = get_data()

    entries = pprint.pformat( data, indent=2 )
    sys.stdout.write( entries )

    fname = save_data(data)
    sys.exit( "Saved to file '{}'".format(fname) )
