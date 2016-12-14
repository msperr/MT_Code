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

def timelist(start_time, finish_time, time_step=0, length=0):
    step = time_step if time_step > 0 else (finish_time-start_time)/length
    return [t for t in timerange(start_time, finish_time, step)]

def to_datetime(n):
    min_date = datetime(1970, 1, 1)
    return min_date + timedelta(milliseconds = n)

def accumulate(iterable):
    it = iter(iterable)
    total = next(it)
    yield total
    for element in it:
        total = total + element
        yield total

class Printer:
    
    verbose = True
    statistics = True
    
    def __init__(self, verbose, statistics):
        self.verbose = verbose
        self.statistics = statistics
    
    def write(self, string):
        print '[INFO]', string
    
    def writeWarn(self, string):
        print '[WARN]', string
    
    def writeInfo(self, string):
        if self.verbose:
            print string
    
    def writeStat(self, string):
        if self.statistics:
            print string