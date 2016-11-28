#! /bin/bash

source env/bin/activate

mkdir -p data

FILENAME="./data/bustimes__$(date +%Y-%m-%d__%H-%M-%S).json"

watch --interval 60 "python2.7 bustimes.py > $FILENAME"
