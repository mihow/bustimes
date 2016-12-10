

class BusRoute():

    def __init__(self, route_number, first_stop, last_stop):

        self.route_number = route_number
        self.first_stop = first_stop
        self.last_stop = last_stop
        self.history = self.get_history()

    def get_history(self):
        """
        Load route history from db.
        """

        return []

    def average_length_of_trip(self):
        """
        Average length of time from first_stop to last_stop based on history.
        """
        pass

    def histogram(self):
        """
        Histogram of all recorded trip lengths.
        """

    def predict_length(day_of_week, time_of_day):
        """
        Predict length of trip based on day of week & time of day.
        @HINT this is where the model goes.

        Can we give more weight the route times for this current day, or last few days?
        Do those better inform the prediction?

        Does the variance in route times for _all_ busses in the city have an influence?
        """
        pass

    def schedule(self):
        """
        Sheduled pick up & drop off times (real or average historical?).
        """
        pass
