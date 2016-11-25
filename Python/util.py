from itertools import izip_longest
from datetime import datetime, timedelta
from urlparse import urlunparse
from urllib import urlencode

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)

def grouperList(iterable, n):
    "Collect data into fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return ([item for item in group if item] for group in izip_longest(fillvalue=None, *args))

def url(scheme='http', hostname='', port=80, path='', query={}):
    return urlunparse((scheme, '%s:%d' % (hostname, port), path, '', urlencode(query), ''))

def timerange(start_time, finish_time, time_step):
    for n in range(0, int((finish_time - start_time).total_seconds()), int(time_step.total_seconds())):
        yield start_time + timedelta(seconds = n)

def to_datetime(n):
    min_date = datetime(1970, 1, 1)
    return min_date + timedelta(milliseconds = n) 