#! /bin/bash

source env/bin/activate
FLASK_APP=bustimes.py FLASK_DEBUG=1 flask run
