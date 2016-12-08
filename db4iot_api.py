import requests
import hmac
import hashlib
from base64 import b64encode
import urllib.parse
import json
from datetime import datetime
import pytz

from db4iot_credentials import API_KEY, SECRET_KEY


def authenticate(method, content, content_type, date, path):
    secret_key = SECRET_KEY
    string_to_sign = method + '\n'
    if content:
        string_to_sign += hashlib.md5(content.encode('utf-8')).hexdigest()
    string_to_sign += ('\n' + content_type + '\n' + date + '\n' + path)
    hmac_sig = hmac.new(secret_key, string_to_sign.encode('utf-8'), hashlib.sha512).digest()
    return urllib.parse.quote(b64encode(hmac_sig))

def timestamp():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def exportcsv(begin, end, filters = {"logical": "and", "conditions": []}):
    api_key = API_KEY 
    columns = [
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
	       {'column_id': 'vehicle_location'}
	      ]
    datasource_id = "ef424fcd-fd76-40eb-8d13-5a05f81391a9"
    content = json.dumps({
                  "data": {
			  "method": "export_csv",
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
    response = requests.post(url, data=content, headers=header)
    return response

def exportcsv_onetime(month, day, hour, minute):
    time = (datetime(2016, month, day, hour, minute, tzinfo=pytz.timezone("US/Pacific")) - datetime(1970,1,1, tzinfo=pytz.utc)).total_seconds()
    return exportcsv(time, time+10)

if __name__ == "__main__":
    print(exportcsv_onetime(9, 1, 8, 0).text)
    
