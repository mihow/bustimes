from __future__ import print_function
import sys
import json
import pprint
import urllib
import datetime

from flask import Flask, jsonify, url_for, redirect

app = Flask(__name__)

TRIMET_APP_ID = '754D006A41E6C467A520737CA'



def get_bus_data():
    url = 'http://developer.trimet.org/ws/v2/vehicles?appID={}'.format(
            TRIMET_APP_ID)
    resp = urllib.urlopen(url) 
    data = json.loads( resp.read() )
    bus_info = data.get('resultSet', {}).get('vehicle', {})

    return bus_info

def make_summary(bus_data):
    request_time = datetime.datetime.now()

    if not bus_data:
        bus_data = get_bus_data()

    buses = set([entry['vehicleID'] for entry in bus_data])
    times = [entry['time'] for entry in bus_data]
    avg_delay = sum([entry['delay'] for entry in bus_data if entry['delay']]) / float(len(bus_data))
    bus_lines = set([entry['routeNumber'] for entry in bus_data])

    def timestamp_to_dt(t):
        # Convert "miliseconds since the epoch" to a datetime object
        return datetime.datetime.fromtimestamp(t/1000)

    summary = {
            "num_vehicles_reporting": len(buses),
            "num_bus_lines_reporting": len(bus_lines), 
            "avg_delay_minutes": avg_delay/60.0,
            "time_reported_max": timestamp_to_dt(max(times)), 
            "time_reported_min": timestamp_to_dt(min(times)), 
            "time_request_made": request_time,
    }

    return summary


@app.route('/')
def index():
    return redirect(url_for('bus_summary'))


@app.route('/summary.json')
def bus_summary():
    summary = make_summary(get_bus_data())
    return jsonify(summary), 200


@app.route('/everything.json')
def show_bus_data():
    """
    Full results from TriMet 
    """
    return jsonify(get_bus_data(), 200)


def save_bus_data_to_db():
    """
    @TODO Save the raw results to a database!
    # This is a scheduled function, doesn't need an http endpoint
    """
    raise NotImplementedError


if __name__ == '__main__':

    bus_data = get_bus_data()
    summary = make_summary(bus_data)

    # Output full data in a way that it can be redirected in the shell
    sys.stdout.write(json.dumps(bus_data, indent=4))

    # Print the summary
    sys.exit(pprint.pformat( summary ))
