# coding: utf-8

import argparse

import pandas as pd
import numpy as np
import datetime as dt

parser = argparse.ArgumentParser()
parser.add_argument("path_to_bus_trip_json_data")

# df.pivot_table(index=['tripID'], values=['event_day'], aggfunc='count').sort_values(by='event_day')
#
# df[df.vehicle_id==3149]
#


def get_datetime(t):
    return dt.datetime.fromtimestamp(t/1000)

def get_weekday(t):
    if not isinstance(t, dt.datetime):
        t = get_datetime(t)
    return t.strftime('%A')

def get_hour_of_day(t):
    if not isinstance(t, dt.datetime):
        t = get_datetime(t)
    return int(t.strftime('%H'))

def get_timestamp_str(t):
    if not isinstance(t, dt.datetime):
        t = get_datetime(t)
    return str(t)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)

    All args must be of equal length.

    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2

    c = 2 * np.arcsin(np.sqrt(a))
    km = 6367 * c
    miles = km * 0.621371
    return miles

def get_distance(row):

    return haversine_distance(
            row.lat_start,
            row.lon_start,
            row.lat_end,
            row.lon_end)


def distance_from_observation_to_first_stop(row):
    pass

def distance_from_observation_to_last_stop(row):
    pass

def get_situation(row, first_stop, last_stop):
    # 1545 to 792
    if row.nextLocID == first_stop:
        return 'approaching_first_stop'
    elif row.nextLocID == last_stop:
        return 'approaching_last_stop'
    elif row.lastLocID == first_stop:
        return 'leaving_first_stop'
    elif row.lastLocID == last_stop:
        return 'leaving_last_stop'
    else:
        return 'en_route'

def main(df, save=True):
    bus_line = 19
    first_stop = 1545
    last_stop = 792
    df['first_stop'] = first_stop
    df['last_stop'] = last_stop

    df = df[df['routeNumber'] == bus_line]
    df['event_timestamp'] = df.time.apply(get_datetime)
    df['situation'] = df.apply(get_situation, args=[first_stop, last_stop], axis=1)

    df['weekday'] = df.event_timestamp.apply(get_weekday)

    # monday_trips = df[df.weekday == 'Monday']

    # vehicles = df.pivot_table(index=['vehicle_id'], values=['situation'], aggfunc=lambda x: len(x.unique())).sort_values(by='situation')


    # Get only data points right after the bus leaves a stop (first or last stop)
    leavings = df[df.situation.str.contains('leaving')]


    # Work with a subset of columns
    # leavings_simple = leavings[['vehicle_id', 'event_timestamp', 'situation']]

    # Group by vehicle ID so our timeseries data makes sense

    # vehicles = leavings.groupby('vehicle_id')

    # Sample group of data points for a single vehicle
    # k, v = list(vehicles)[2]
    # k # vehicle_id
    # v # dataframe


    # all_routes_dataframes = []
    # all_blocks = set()
    #
    # # @TODO for later
    # for k, v in vehicles:

    def stats_for_vehicle_groups(df):
        df = df.sort_values('event_timestamp')

        # Save only the rows where the situation/state changed (approaching => leaving)
        state_changes = (df != df.shift(1)).situation
        vroutes = df.loc[state_changes].copy()

        previous_rows = vroutes.shift(1)

        # Save the start time, end time & duration of each trip
        vroutes['trip_start'] = previous_rows.event_timestamp # Time leaving first stop
        vroutes['trip_end'] = vroutes.event_timestamp # Time leaving last stop
        vroutes['duration'] = vroutes.trip_end - vroutes.trip_start

        vroutes['delay_start'] = previous_rows.delay
        vroutes['delay_end'] = vroutes.delay

        # Save the block ID for the start and end of each trip
        # These should always be the same, otherwise something is wrong
        # with that data point.
        vroutes['block_start'] = previous_rows.blockID.astype('str')
        vroutes['block_end'] = vroutes.blockID.astype('str')

        # Calculte the distance between each start and and point
        # This should help validate data as well
        vroutes['lat_start'] = previous_rows.latitude
        vroutes['lon_start'] = previous_rows.longitude
        vroutes['lat_end'] = vroutes.latitude
        vroutes['lon_end'] = vroutes.longitude
        vroutes['distance'] = vroutes.apply(get_distance, axis=1)

        # Only keep the "ending" data points for each trip
        completed_routes = vroutes[vroutes.situation.str.contains('last')]

        # Only keep columns we are interested in, and order them
        completed_routes = completed_routes[[
                'duration',
                'distance',
                'delay', # at last stop observation
                'trip_start',
                'trip_end',
                'delay_start',
                'delay_end',
                'first_stop',
                'last_stop',
                'block_start',
                'block_end',
                'vehicleID',
                'type',
                'tripID',
                'situation',
                'routeNumber',
                'direction',
                'bearing',
                'lastLocID',
                'lastStopSeq',
                'loadPercentage', # at last stop observation
                ]]

        # print("Sample for vehicle #{}".format(k))
        # print(completed_routes)

        # all_routes_dataframes.append(completed_routes)
        return completed_routes

    # routes = pd.concat(all_routes_dataframes)
    #  import ipdb; ipdb.set_trace()
    routes = leavings.groupby('vehicleID', group_keys=False).apply(stats_for_vehicle_groups)
    # unstack()?

    # Drop rows with NA durations
    routes = routes.dropna()

    # Drop outliers
    # about 50 out of 4000 are over 100 minutes
    # @TODO look more into these later
    # routes = routes[routes.duration < dt.timedelta(seconds=(60*100))]
    # routes = routes[scipy.stats.zscore(routes.duration) < 3]
    # These are generally over 4 hours or event multiple days
    routes = routes[routes.duration < routes.duration.quantile(0.95)]

    # Add new columns for grouping & aggregating
    routes['weekday'] = routes.trip_start.apply(
            lambda t: t.strftime('%A'))
    routes['hour'] = routes.trip_start.apply(
            lambda t: t.hour)
    routes['weekday_num'] = routes.trip_start.apply(
            lambda t: t.weekday)
    routes['trip_start_time'] = routes.trip_start.dt.time
    routes['time_of_day'] = routes.trip_start.apply(
            lambda t: t.strftime('%H%M%S')).astype('int')
    routes['duration_minutes'] = routes.duration.apply(
            lambda t: t.seconds/60.0)

    # routes['duration_category'] = pd.cut(
    #         routes.duration_minutes,
    #         bins=7,
    #         labels=['x_short', 'shorter', 'short', 'normal', 'long', 'longer', 'x-long'],
    #         include_lowest=True,)


    # Sort
    routes = routes.sort_values('trip_start')



    print(routes.duration.describe())
    # print()
    # print(routes.pivot_table(index=['weekday', 'hour'], values='duration', aggfunc='mean'))

    # import ipdb; ipdb.set_trace()

    if save:
        route_number = routes.routeNumber.mode()[0] # Should be just one route number!!
        # @TODO add trip start and end stops
        fname = "completed_bus_routes-bus{}.pickle".format(route_number)
        print("DataFrame saved to '{}'".format(fname))
        routes.to_pickle(fname)

    return routes

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

if __name__ == '__main__':

    args = parser.parse_args()
    data = pd.read_json(args.path_to_bus_trip_json_data)
    main(data)
