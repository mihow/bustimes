# Bustimes 

Grabs all current Tri-Met bus locations, saves the raw result to a database and displays a quick summary of the results.

## Install

Intended to run on AWS Lambda, which requires python 2. Zappa is a project that makes deploying a Flask web app to Lambda super easy. Zappa requires we use a virtualenv. 

```bash
virtualenv env --python python2.7
source env/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
./runserver.sh
# Open a webrowser to http://localhost:5000
```

## Deploy to AWS

```bash
zappa deploy dev
zappa schedule dev # Runs save_bus_data at scheduled intervals
```

## Sample data

Data I've downloaded so far can be found in our shared Google Drive folder:
https://drive.google.com/drive/u/0/folders/0B2nKUbgRVu3VUk9hazYwZEtOMkk

