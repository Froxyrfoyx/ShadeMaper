import statistics

class ResonanceDetector:
    def __init__(self, hold=1.5):
        self.timings = {}
        self.hold = hold
    def logreq(self, endpoint, elapse_time):
        if endpoint not in self.timings:
            self.timings[endpoint] = []
        self.timings[endpoint].append(elapse_time)

    def check_anomaly(self, endpoint):
        data = self.timings.get(endpoint, [])
        if len(data) < 5:
            return False
        current_latency = data[-1]
        historical_data = data[:-1]
        avg = statistics.mean(historical_data)
        stdev = statistics.stdev(historical_data)
        if stdev == 0:
            return False
        return current_latency > (avg + self.hold * stdev)
