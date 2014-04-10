'''Sending metrics to statsd server.

We define `metered` context manager and `metrics` decorator. Both will update
the following metrics:

    # Counters
    - <prefix>.<name>.num_runs

    # Timers
    - <prefix>.<name>

StatsD server,port and <prefix> are defined in the config module.
'''

from . import config

from statsd import StatsClient

from functools import wraps
from time import time
from app import context

class metered(object):
    '''A context manager sending metrics to statsd.'''
    def __init__(self, name):
        prefix = '{}.{}'.format(config.METRICS_ENV,  name)
        self.runs = '{}.num_runs'.format(prefix)
        self.time = prefix


    def __enter__(self):
        context.stats_client.incr(self.runs)
        self.start = time()


    def __exit__(self, exc_type, exc_value, traceback):
        duration = int(time() - self.start) * 1000  # statsd times in msec
        context.stats_client.timing(self.time, duration)


def metrics(fn):
    '''A decorator manager sending metrics to statsd.'''
    name = fn.__name__

    @wraps(fn)
    def wrapper(*args, **kw):

        with metered(name):
            return fn(*args, **kw)

    wrapper._orig_fn = fn
    return wrapper