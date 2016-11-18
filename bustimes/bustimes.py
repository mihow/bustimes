import json
import urllib
import datetime

from flask import Flask, jsonify

app = Flask(__name__)

TRIMET_APP_ID = '754D006A41E6C467A520737CA'



def get_bus_data():
    url = 'http://developer.trimet.org/ws/v2/vehicles?appID={}'.format(
            TRIMET_APP_ID)
    resp = urllib.urlopen(url) 
    data = json.loads( resp.read() )
    bus_info = data.get('resultSet', {}).get('vehicle', {})

    return bus_info


@app.route('/')
def bus_summary():
    request_time = datetime.datetime.now()
    bus_info = get_bus_data()

    buses = set([entry['vehicleID'] for entry in bus_info])
    times = [entry['time'] for entry in bus_info]
    avg_delay = sum([entry['delay'] for entry in bus_info if entry['delay']]) / float(len(bus_info))
    bus_lines = set([entry['routeNumber'] for entry in bus_info])

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

    return jsonify(summary), 200


def save_bus_data():
    """
    @TODO Save the raw results to a database!
    # This is a scheduled function, doesn't need an http endpoint
    """
    raise NotImplementedError


if __name__ == '__main__':
    app.run()
