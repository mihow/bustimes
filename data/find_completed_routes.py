# coding: utf-8

import pandas as pd
import datetime as dt

df = pd.read_json('bus_19_history.json')

# df.pivot_table(index=['tripID'], values=['event_day'], aggfunc='count').sort_values(by='event_day')
# 
# df[df.vehicle_id==3149]
# 

def get_weekday(t):
    return dt.datetime.fromtimestamp(t).strftime('%A')

def get_hour_of_day(t):
    return int(dt.datetime.fromtimestamp(t).strftime('%H'))

def get_timestamp_str(t):
    return str(dt.datetime.fromtimestamp(t))

df['weekday'] = df.event_timestamp.apply(get_weekday)

# monday_trips = df[df.weekday == 'Monday']

# vehicles = df.pivot_table(index=['vehicle_id'], values=['situation'], aggfunc=lambda x: len(x.unique())).sort_values(by='situation')


# Get only data points right after the bus leaves a stop (first or last stop)
leavings = df[df.situation.str.contains('leaving')]

# Work with a subset of columns
leavings_simple = leavings[['vehicle_id', 'event_timestamp', 'situation']]

# Group by vehicle ID so our timeseries data makes sense
vehicles = leavings_simple.groupby('vehicle_id')

# Sample group of data points for a single vehicle
# k, v = list(vehicles)[2]
# k # vehicle_id
# v # dataframe


all_routes_dataframes = []

# @TODO for later
for k, v in vehicles:

    v = v.sort_values('event_timestamp')

    # Save only the rows where the situation/state changed (approaching => leaving)
    state_changes = (v != v.shift(1)).situation
    v_routes = v.loc[state_changes].copy()

    # Time between leaving first stop and leaving last stop
    diffs = ((v_routes.event_timestamp - v_routes.shift(1).event_timestamp) / 60)

    v_routes['duration'] = diffs

    v_routes[v_routes.situation.str.contains('last')]

    completed_routes = v_routes[v_routes.situation.str.contains('last')]

    # print("Sample for vehicle #{}".format(k))
    # print(completed_routes)

    all_routes_dataframes.append(completed_routes)

routes = pd.concat(all_routes_dataframes)

# Drop rows with NA durations
routes = routes.dropna()

# Drop outliers
# about 50 out of 4000 are over 120 minutes, @TODO look more into these later
routes = routes[routes.duration < 100]

# Add new columns
routes['timestamp_str'] = routes.event_timestamp.apply(get_timestamp_str)
routes['weekday'] = routes.event_timestamp.apply(get_weekday)
routes['hour'] = routes.event_timestamp.apply(get_hour_of_day)

# Sort
routes = routes.sort_values('event_timestamp')

print(routes.duration.describe())
print()
print(routes.pivot_table(index=['weekday', 'hour'], values='duration', aggfunc='mean'))

# import ipdb; ipdb.set_trace()

# Final dataframe columns should look something like this:
# 
# [
#     time_leaving_first_stop, 
#     time_leaving_last_stop, 
#     length_of_trip, # Most important!
#     weekday, # of trip start
#     hour_of_day, # of trip start
#     route_number,
#
#     vehicle_id,
#     latlong_of_first_stop_observation,
#     latlong_of_last_stop_observation,
#     blockID_of_first_stop,
#     blockID_of_last_stop,
#     seqIDs,
#     trip_id,
#     vehicle_type,
# ]


"""
@TODO collect all trip lengths and do histogram
see what variables describe variance
"""
