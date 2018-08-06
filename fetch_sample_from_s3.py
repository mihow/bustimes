#! /usr/bin/env python3

import boto3
import ast
import pprint
import json


sample = []

s3 = boto3.resource('s3')
bucket = s3.Bucket('bustimes-data')
search = bucket.objects.filter(Prefix='raw/bustimes__2018')
for obj in search.limit(60):
    print("Fetching", obj.key)
    data_raw = obj.get()['Body'].read().decode('utf-8')
    data = ast.literal_eval(data_raw)
    # pprint.pprint(data, indent=2)
    sample += data

fname = 'data/bustimes_sample.json'
f = open(fname, 'w')
json.dump(sample, f, indent=2)

print("Saved to", fname)
