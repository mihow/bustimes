#! /usr/bin/env python3

import sys
import urllib.request
import ast
import json


def fix_json(data_raw):
    """
    The "JSON" data with bus times was actually a literal python string.
    This converts the python to a json object.
    """

    # data_str = data_bytes.decode('utf-8')  # AWS api will return bytes
    data_str = data_raw
    try:
        data_python = ast.literal_eval(data_str)
    except ValueError as e:
        # Catch this error otherwise the output is too long.
        print("Could not decode literal python string", e)
        sys.exit(1)
    data_json = json.dumps(data_python, indent=2)
    return data_json


if __name__ == '__main__':
    # Usage:
    # ./fix_malformed_json.py INPUT_FILE_PATH_OR_URL > output.json

    # Example URL:
    # https://bustimes-data.s3.amazonaws.com/raw/bustimes__2018-08-03__03-06-51.json

    input_file_or_url = sys.argv[1]
    if input_file_or_url.startswith('http'):
        data = urllib.request.urlopen(input_file_or_url).read().decode('utf-8')
    else:
        data = open(input_file_or_url, 'r').read()

    print("Reading data len {}".format(len(data)))
    data_json = fix_json(data)

    sys.stdout.write(data_json)
