"""Dashboard for exploring historical TriMet bus times & locations."""
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
    """Convert "miliseconds since the epoch" to a datetime object."""
    dt = datetime.datetime.fromtimestamp(t/1000)
    if format:
        return dt.strftime(date_fmt)
    return dt


def bus_route_choices():
    """Create a dict of choices for the bus route selection dropdown."""
    routes = sorted([r for r in list(data['signMessageLong'].unique()) if r])
    choices = [{'label': "{}".format(r), 'value': r} for r in routes]
    return choices


def make_summary(bus_data):
    """Create summary of useful info about current dataset."""
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
        id='bus_positions',
        figure={
            'data': [
                {'x': [], 'y': []},
            ],
        },
        style={
            'height': '900px',
        },
    ),

    dcc.Dropdown(
        id='bus_routes',
        options=bus_route_choices(),
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
    """Update summary on page when bus route selector changes."""
    if bus_route:
        route_data = data[data['signMessageLong'] == bus_route]
        summary = make_summary(route_data)

        list_items = [
            html.Li("{}: {}".format(k, v)) for k, v in summary.items()]

        return list_items
    else:
        return None


@app.callback(
    Output('bus_positions', 'figure'),
    [Input('bus_routes', 'value')],
)
def update_bus_positions(bus_route):
    """Update map of bus locations when bus route selector changes."""
    route_data = data[data['signMessageLong'] == bus_route]
    description = ", ".join([
        msg for msg in route_data.signMessage.unique() if msg])

    def hover_text(row):
        """Text to display when hovering over a single bus location."""
        date = timestamp_to_dt(row['time']).strftime(date_fmt)
        name = row['vehicleID']
        text = "{}<br>{}".format(name, date)
        return text

    def get_position_index(time, start, end):
        """
        Index of bus' position relative to first and last pos in current data.

        Returns value between 0 and 1.
        Used as opacity value for markers on map, bus path appears as a snake
        from light to dark.
        """
        # Value between 0 and 1
        pos = (time - start) / (end - start)
        return pos

    if bus_route:
        chart_data = []
        for vehicle, route in route_data.groupby('vehicleID'):
            start = route['time'].min()
            end = route['time'].max()

            chart_data.append({
                'lon': list(route['longitude']),
                'lat': list(route['latitude']),
                'marker': {
                    'opacity': list(route['time'].apply(
                        get_position_index,
                        args=[start, end]) + 0.3)
                },
                'text': list(route.apply(hover_text, axis=1)),
                'name': vehicle,
                'hoverinfo': 'text',
                'type': 'scattermapbox',
                'mode': 'markers',
            })

        figure = {
            'data': chart_data,
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
    else:
        return None


if __name__ == '__main__':
    """Run the server!"""
    app.run_server(debug=True)
