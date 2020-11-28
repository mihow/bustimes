#! /usr/bin/env python3

import os
import ast
import pprint
import json
from multiprocessing.dummy import Pool

import boto3

pool = Pool(16)
s3 = boto3.resource('s3')
bucket = s3.Bucket('bustimes-data')

def format_and_save(obj):
    fname = 'data_test/%s' % obj.key
    if os.path.exists(fname):
        print("Skipping", obj.key)
    else:
        print("Fetching", obj.key)
        data_raw = obj.get()['Body'].read().decode('utf-8')
        data = ast.literal_eval(data_raw)
        with open(fname, 'w') as f:
            json.dump(data, f, indent=2)
        print("Saved to", fname)

search = bucket.objects.filter(Prefix='raw/bustimes__2018-05')
pool.map(format_and_save, search.limit(60))
