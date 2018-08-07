import os
import datetime

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import pandas as pd

app = dash.Dash()

data = pd.read_json('data/bustimes_sample.json')

mapbox_token = os.environ.get('MAPBOX_ACCESS_TOKEN')

date_fmt = '%a %b %-m, %Y %-I:%M%p'

def timestamp_to_dt(t, format=False):
    # Convert "miliseconds since the epoch" to a datetime object
    dt = datetime.datetime.fromtimestamp(t/1000)
    if format:
        return dt.strftime(date_fmt)
    return dt

def bus_route_choices():
    routes = list(data['routeNumber'].unique())
    choices = [{'label': "Bus #{}".format(r), 'value': r} for r in routes]
    return choices


def make_summary(bus_data):
    buses = bus_data['vehicleID'].unique()
    times = bus_data['time']
    avg_delay = bus_data['delay'].sum() / len(bus_data)
    bus_lines = list(bus_data['routeNumber'].unique())

    summary = {
            "num_vehicles_reporting": len(buses),
            "num_bus_lines_reporting": len(bus_lines),
            "avg_delay_minutes": round(avg_delay/60.0, 1),
            "time_reported_max": timestamp_to_dt(max(times)).strftime(date_fmt),
            "time_reported_min": timestamp_to_dt(min(times)).strftime(date_fmt),
    }

    return summary


app.layout = html.Div([

    dcc.Graph(
        id = 'bus_positions',
        figure = {
            'data': [
                {'x': [], 'y': []},
            ],
        },
        style = {
            'height': '900px',
        },
    ),

    dcc.Dropdown(
        id = 'bus_routes',
        options = bus_route_choices(),
        placeholder='Select a bus route',
        # multi=True,
    ),

    html.Ul(id='summary'),

])

@app.callback(
    Output('summary', 'children'),
    [Input('bus_routes', 'value')],
)
def update_summary(bus_route):
    route_data = data[data.routeNumber == bus_route]
    summary = make_summary(route_data)

    list_items = [html.Li("{}: {}".format(k, v)) for k, v in summary.items()]

    return list_items

@app.callback(
    Output('bus_positions', 'figure'),
    [Input('bus_routes', 'value')],
)
def update_bus_positions(bus_route):
    route_data = data[data.routeNumber == bus_route]
    description = ", ".join([
        msg for msg in route_data.signMessage.unique() if msg])

    def hover_text(row):
        date = timestamp_to_dt(row['time']).strftime(date_fmt)
        name = row['signMessageLong']
        text = "{}<br>{}".format(name, date)
        return text

    figure = {
        'data': [
            {
                'lon': route_data['longitude'],
                'lat': route_data['latitude'],
                #'color': route_data['tripID'].as_type(int),
                'text': route_data.apply(hover_text, axis=1),
                'hoverinfo': 'text',
                'type': 'scattermapbox',
                'mode': 'markers',
            },
        ],
        'layout': {
            'autosize': True,
            'mapbox': {
                'accesstoken': mapbox_token,
                'zoom': 10,
                'center': {
                    # Portland center
                    'lat': route_data['latitude'].median(),
                    'lon': route_data['longitude'].median()
                },
            },
            'title': description,
        },
    }
    return figure

if __name__ == '__main__':
    app.run_server(debug=True)
