import argparse
import datetime as dt
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt


parser = argparse.ArgumentParser()
parser.add_argument('completed_bus_trips_pickle')
parser.add_argument('filename_for_figure_image')


def remove_outliers(df):
    df = df[df.duration < df.duration.quantile(0.95)]
    df = df[df.duration > df.duration.quantile(0.05)]
    return df

def remove_weekends(df):
    df = df[df.trip_start.dt.weekday.isin([0,1,2,3,4,5])]
    return df

def add_columns(df):
    # df['trip_start_timestamp'] = df.trip_start.apply(lambda t: dt.datetime(1900, 1, 1, t.hour, t.minute, 0))
    df['weekday_num'] = df.trip_start.dt.weekday
    return df

def prep_data(df):
    df = remove_outliers(df)
    df = remove_weekends(df)
    df = add_columns(df)
    return df

def make_histogram(df, fname):
    ax = df.boxplot(column=['duration_minutes'], by='hour', figsize=(14, 6), rot=0, fontsize=15)
    bus_num = df.routeNumber.mode()[0]
    first_stop = 1545 # df.first_stop.mode()[0]
    last_stop = 792 # df.last_stop.mode()[0]
    num_samples = len(df)
    first_date = df.trip_start.min().strftime('%D')
    last_date = df.trip_start.max().strftime('%D')

    plt.suptitle('Average duration of weekday bus trips, grouped by hour of the day')
    plt.title('TriMet bus #{} from stop ID {} to {}. Generated from {} sample trips taken from {} to {}.'.format(
            bus_num, first_stop, last_stop, num_samples, first_date, last_date))
    plt.ylabel('Minutes until bus arrives at stop ID {}'.format(last_stop))
    plt.xlabel('Hour that bus leaves stop ID {} (24 clock)'.format(last_stop))
    plt.savefig(fname)


if __name__ == '__main__':

    args = parser.parse_args()
    df = pd.read_pickle(args.completed_bus_trips_pickle)
    df = prep_data(df)
    make_histogram(df, args.filename_for_figure_image)
