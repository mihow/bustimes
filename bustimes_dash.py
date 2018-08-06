import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output

import pandas as pd

mapbox_token = ''

data = pd.read_json('data/bustimes_sample.json')

def bus_route_choices():
    routes = list(data['routeNumber'].unique())
    choices = [{'label': r, 'value': r} for r in routes]
    return choices

app = dash.Dash()

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
        placeholder = 'Select a bus route',
    ),

    html.P("Summary:"),

])

@app.callback(
    Output('bus_positions', 'figure'),
    [Input('bus_routes', 'value')],
)
def update_bus_positions(bus_route):
    route_data = data[data.routeNumber==bus_route]
    description = ", ".join([
        msg for msg in route_data.signMessage.unique() if msg])
    figure = {
        'data': [
            {
                'lon': route_data['longitude'], 
                'lat': route_data['latitude'], 
                'name': bus_route, 
                'type': 'scattermapbox', 
                # 'locationmode': 'USA-states',
                'mode': 'markers',
            },
        ],
        'layout': {
            'autosize': True,
            'mapbox': {
                'accesstoken': mapbox_token,
                'zoom': 11,
                'center': {
                    # Portland center
                    'lat': 45.5426867,
                    'lon': -122.7244257,
                },
            },
            'title': description,
        },
    }
    return figure

if __name__ == '__main__':
    app.run_server(debug=True)
