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

df['weekday'] = df.event_timestamp.apply(get_weekday)

monday_trips = df[df.weekday == 'Monday']

# vehicles = df.pivot_table(index=['vehicle_id'], values=['situation'], aggfunc=lambda x: len(x.unique())).sort_values(by='situation')


# Get only data points right after the bus leaves a stop (first or last stop)
leavings = df[df.situation.str.contains('leaving')]

# Work with a subset of columns
leavings_simple = leavings[['vehicle_id', 'event_timestamp', 'situation']]

# Group by vehicle ID so our timeseries data makes sense
vehicles = leavings_simple.groupby('vehicle_id')

# @TODO for later
# for k, v in vehicles:
#     print(len(v))

# Sample group of data points for a single vehicle
k, v = list(vehicles)[2]

k # vehicle_id
v # dataframe

v = v.sort_values('event_timestamp')

# Save only the rows where the situation/state changed (approaching => leaving)
state_changes = (v != v.shift(1)).situation
routes = v.loc[state_changes]

# Time between leaving first stop and leaving last stop
diffs = ((routes.event_timestamp - routes.shift(1).event_timestamp) / 60)

routes_with_length = routes.copy()
routes_with_length['length'] = diffs

routes_with_length[routes_with_length.situation.str.contains('last')]

completed_routes = routes_with_length[routes_with_length.situation.str.contains('last')]

print("Sample for vehicle #{}".format(k))
print(completed_routes)

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
