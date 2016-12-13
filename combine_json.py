# coding: utf-8

import os
import json

files = [f for f in os.listdir('.') if f.endswith('.json')]
    
everything = []

for f in files:
    data = json.load(open(f, 'r'))
    everything += data
    
json.dump(everything, open('everything.json', 'w'))
