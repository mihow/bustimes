import requests
import hmac
import hashlib
from base64 import b64encode
import urllib.parse
import json
from datetime import datetime, timedelta
import pytz
import sys
import csv
import logging

logging.basicConfig(
        level=logging.INFO,
        format="%(message)s")
log = logging

def authenticate(method, content, content_type, date, path):
    secret_key = b'uqrwyqlpvxzzsqyrlovrtmrtnlwwwpzn'
    string_to_sign = method + '\n'
    if content:
        string_to_sign += hashlib.md5(content.encode('utf-8')).hexdigest()
    string_to_sign += ('\n' + content_type + '\n' + date + '\n' + path)
    hmac_sig = hmac.new(secret_key, string_to_sign.encode('utf-8'), hashlib.sha512).digest()
    return urllib.parse.quote(b64encode(hmac_sig))

def timestamp():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def make_filters(route_number, next_stop=None, previous_stop=None):
    conditions = [
        {
          "test": "match",
          "column_id": "routeNumber",
          "values": [
             str(route_number) 
          ]
        },
        {
          "test": "match",
          "column_id": "direction",
          "values": [
            "1" # Towards downtown
          ]
        },
    ]

    if next_stop:
        conditions.append(
            {
              "test": "match",
              "column_id": "nextLocID",
              "values": [
                str(next_stop)
              ]
            },
        )

    if previous_stop:
        conditions.append(
            {
              "test": "match",
              "column_id": "lastLocID",
              "values": [
                str(previous_stop)
              ]
            },
        )


    filters = \
    {
      "logical": "and",
      "conditions": conditions,
    }

    return filters


def exportcsv(begin, end, filters = {"logical": "and", "conditions": []}):

    api_key = 'vxnpukvqlxtovmzuvzokwqxplmovxxsm'
    columns = [
	       {'column_id': 'event_timestamp'},
	       {'column_id': 'vehicle_id'},
	       {'column_id': 'system'},
	       {'column_id': 'signMessage'},
	       {'column_id': 'signMessageLong'},
	       {'column_id': 'garage'},
	       {'column_id': 'tripID'},
	       {'column_id': 'newTrip'},
	       {'column_id': 'inCongestion'},
	       {'column_id': 'offRoute'},
	       {'column_id': 'type'},
	       {'column_id': 'expires'},
	       {'column_id': 'serviceDate'},
	       {'column_id': 'device_id'},
	       {'column_id': 'bearing'},
	       {'column_id': 'nextStopSeq'},
	       {'column_id': 'lastStopSeq'},
	       {'column_id': 'loadPercentage'},
	       {'column_id': 'direction'},
	       {'column_id': 'delay'},
	       {'column_id': 'messageCode'},
	       {'column_id': 'routeNumber'},
	       {'column_id': 'lastLocID'},
	       {'column_id': 'nextLocID'},
	       {'column_id': 'blockID'},
	       {'column_id': 'locationScheduleDay'},
	       {'column_id': 'vehicle_location'},
	      ]
    datasource_id = "ef424fcd-fd76-40eb-8d13-5a05f81391a9"
    content = json.dumps({
                  "data": {
			  "method": "export_json",
			  #"internal_compression": "none",
			  "datasource_id": datasource_id,
			  "columns": columns,
			  "event_timestamp_begin": begin,
			  "event_timestamp_end": end,
			  "filter": filters
			  }
		  })
    date = timestamp()
    hmac_sig = authenticate("POST", content, 'application/json; charset=UTF-8', date, "/v1/datasource/" + datasource_id + "/analyze")
    url = 'https://beta.db4iot.net/v1/datasource/' + datasource_id + '/analyze?X-D4i-Date=' + urllib.parse.quote(date) + '&X-D4i-APIKey=' + api_key + '&X-D4i-Signature=' + hmac_sig
    header = {'content-type': 'application/json; charset=UTF-8', 'data-type':'text'}

    response = requests.post(url, data=content.encode('utf-8'), headers=header)

    return response

def exportcsv_onetime(year, month, day, hour, minute):
    time = (datetime(year, month, day, hour, minute, tzinfo=pytz.timezone("US/Pacific")) - datetime(1970,1,1, tzinfo=pytz.utc)).total_seconds()
    return exportcsv(time, time+(60*60*24))


def routes_for_day(route_number, date):
    
    # route_number = 19
    # first_stop = 1545
    # last_stop = 792

    start_date = datetime(date.year, date.month, date.day, 0, 0, 
            tzinfo=pytz.timezone("US/Pacific"))
    
    start_time = (
            datetime(date.year, date.month, date.day, 0, 0, 
                tzinfo=pytz.timezone("US/Pacific")
            ) - datetime(1970,1,1, tzinfo=pytz.utc)
            ).total_seconds()
    
    end_time = start_time + (60*60*24)

    filters = make_filters(
        route_number = route_number,)

    resp = exportcsv(start_time, end_time, filters)
    return resp

def convert_timestamps(data=[]):
    key = 'event_timestamp'
    for i, entry in enumerate(data):
        data[i]['event_timestamp_str'] = str(
                datetime.fromtimestamp(entry[key]))
    return data

def convert_timestamps(data=[]):
    key = 'event_timestamp'
    for i, entry in enumerate(data):
        data[i]['event_day'] = datetime.fromtimestamp(entry[key]).strftime(
                '%Y-%m-%d')
        data[i]['event_timestamp_str'] = str(
                datetime.fromtimestamp(entry[key]))
    return data

def routes_since_august(route_number, debug=False, writefile=False):

    # Beginning of first day available 
    start_date = datetime(2016, 8, 18, 0, 0)

    # End of yesterday 
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    end_date = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0)
    
    if debug:
        end_date = start_date + timedelta(days=3) 

    num_days = (end_date - start_date).days
    all_routes = []
    date = start_date

    for n in range(num_days):
        log.info("Getting bus 19 routes for {} (until midnight)".format(date))
        resp = routes_for_day(route_number, date)
        resp.raise_for_status()
        data = resp.json()['data']['data']
        log.info("Got {} data points ({} total, day {}/{})".format(
            len(data), len(all_routes) + len(data), n, num_days))
        data = convert_timestamps(data)
        all_routes += data

        if writefile:
            # Overrides file every time
            fname = 'bus_routes_{:%Y-%m-%d}_{:%Y-%m-%d}.json'.format(start_date, end_date)
            outfile = open(fname, 'w')
            json.dump(all_routes, outfile, indent=2)

        # sys.stdout.write( json.dumps(data, indent=2) )
        date += timedelta(days=1)

    log.info("Collected a total of {} data points over {} days".format(
        len(all_routes), num_days))

    return all_routes

        



if __name__ == "__main__":
    import pprint

    data = routes_since_august(19, debug=False, writefile=True)
    sys.stdout.write(json.dumps(data, indent=2))

    #start_date = datetime.strptime(sys.argv[1], "%m/%d/%y")
    # resp = routes_for_day(start_date)
    # data = resp.json()
    # try:
    #     busses = data['data']['data']
    #     busses = convert_timestamps(busses)
    #     sys.stdout.write(json.dumps(busses, indent=2))
    #     #sys.stdout.write(pprint.pformat(busses, indent=2))
    # except KeyError:
    #     sys.stdout.write(json.dumps(data, indent=2))

