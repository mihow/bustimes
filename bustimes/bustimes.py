from __future__ import print_function
import sys
import json
import pprint
import urllib
import datetime
# import decimal

import boto3
from flask import Flask, jsonify, url_for, redirect

app = Flask(__name__)

TRIMET_APP_ID = '754D006A41E6C467A520737CA'
S3_BUCKET_NAME = 'bustimes-data'
DYNAMODB_TABLE_NAME = 'bustimes'

s3 = boto3.client('s3')
db = boto3.resource('dynamodb').Table(DYNAMODB_TABLE_NAME)



def get_bus_data():
    url = 'http://developer.trimet.org/ws/v2/vehicles?appID={}'.format(
            TRIMET_APP_ID)
    print("Fetching bus data from URL: '{}'".format(url))
    resp = urllib.urlopen(url) 
    data = json.loads( resp.read() )
    bus_info = data.get('resultSet', {}).get('vehicle', {})

    return bus_info

def make_summary(bus_data={}, save=True):
    request_time = datetime.datetime.now()

    if not bus_data:
        bus_data = get_bus_data()

    buses = set([entry['vehicleID'] for entry in bus_data])
    times = [entry['time'] for entry in bus_data]
    avg_delay = sum([entry['delay'] for entry in bus_data if entry['delay']]) / float(len(bus_data))
    bus_lines = set([entry['routeNumber'] for entry in bus_data])

    if save:
        url, resp = save_bus_data(bus_data=bus_data)
    else:
        url = None

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
            "data": url,
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


def save_to_s3(bus_data):

    filename = 'raw/bustimes__{:%Y-%m-%d__%H-%M-%S}.json'.format(
        datetime.datetime.now())

    print("Saving file '{}' to S3 bucket '{}'".format(
        filename, S3_BUCKET_NAME))

    resp = s3.put_object(
            ACL='public-read',
            Bucket=S3_BUCKET_NAME,
            Key=filename, 
            Body=bytes(bus_data),
            ContentType='application/json')

    if not resp['ResponseMetadata']['HTTPStatusCode'] == 200:
        raise Exception("Error saving obj to S3")
    
    # And return the URL
    object_url = "https://{0}.s3.amazonaws.com/{1}".format(
        S3_BUCKET_NAME, filename)

    return object_url, resp


def _replace_floats(obj):
    if isinstance(obj, list):
        for i in xrange(len(obj)):
            obj[i] = _replace_floats(obj[i])
        return obj
    elif isinstance(obj, dict):
        for k in obj.iterkeys():
            obj[k] = _replace_floats(obj[k])
        return obj
    elif isinstance(obj, (float, long)):
        # return decimal.Decimal(obj) # Not working
        return str(obj)
    else:
        return obj


def _make_id(obj):
   keys = ['tripID', 'vehicleID', 'time']
   obj_hash = '-'.join([str(obj[k]) for k in keys]) 
   obj['id'] = obj_hash
   return obj


def save_to_db(bus_data):
    """
    Save each entry in the JSON as a row
    in a database.
    """

    print("Batch saving {} bus data items to DynamoDB table '{}' ".format(
        len(bus_data), DYNAMODB_TABLE_NAME))

    with db.batch_writer() as batch:
	for item in bus_data:

	    item = _make_id(item)
	    item = _replace_floats(item)

	    db.put_item( Item=item )

    return True


def save_bus_data(*args, **kwargs):
    """
    This is a scheduled function, doesn't need an http endpoint
    """
    bus_data = kwargs.get('bus_data', get_bus_data())

    save_to_db(bus_data)

    return save_to_s3(bus_data)



if __name__ == '__main__':

    bus_data = get_bus_data()
    summary = make_summary(bus_data)

    # Output full data in a way that it can be redirected in the shell
    sys.stdout.write(json.dumps(bus_data, indent=4))

    # Print the summary
    sys.exit(pprint.pformat( summary ))
