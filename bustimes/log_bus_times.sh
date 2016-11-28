#! /bin/bash

source env/bin/activate

mkdir -p data

INTERVAL=60

while true
do
    FILENAME=./data/bustimes__$(date +%Y-%m-%d__%H-%M-%S).json
    clear
    echo "Writing bus data to file: $FILENAME"
    echo
    echo "Interval: $INTERVAL seconds"
    echo
    echo "Summary:"
    echo
	python2.7 bustimes.py > $FILENAME
    sleep $INTERVAL
done
