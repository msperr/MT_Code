from itertools import izip, izip_longest, product
from datetime import timedelta
from multiprocessing import Pool, Queue
import json
from urlparse import urlunparse
from urllib import urlencode
import sys
import os

import requests

import entities
import util

with open('config.json', 'r') as f:
    config = json.load(f)

def distance_matrix_get_many_to_many_parallel_initializer(host_queue):
    global osrm_host
    osrm_host = host_queue.get()
    print "Initialized: process id = %d, host = %s" % (os.getpid(), osrm_host)

def distance_matrix_get_many_to_many_parallel_func(args):
    global osrm_host
    sources, targets = args
    query = urlunparse(('http', '%s:%d' %(osrm_host['host'], osrm_host['port']), 'matrix', '', urlencode({}), ''))
    query = query + '?' + '&'.join([('src=%f,%f' % (src.lat, src.lon)) for src in sources if src] + [('trgt=%f,%f' % (trgt.lat, trgt.lon)) for trgt in targets if trgt])

    r = requests.get(query)
    response = r.json()
    for i, src in enumerate(sources):
        if src:
            for j, trgt in enumerate(targets):
                if trgt:
                    if response['duration_table'][i][j]>100000 or response['distance_table'][i][j]>135000:
                        print('Warning: From %s to %s: duration: %s and distance: %s' %(src,trgt,response['duration_table'][i][j],response['distance_table'][i][j]))
                        print(query)
                        raise ValueError
    times = {(src, trgt): timedelta(seconds=response['duration_table'][i][j] / 10) for i, src in enumerate(sources) if src for j, trgt in enumerate(targets) if trgt}
    distances = {(src, trgt): response['distance_table'][i][j] for i, src in enumerate(sources) if src for j, trgt in enumerate(targets) if trgt}
    return times, distances

def create_worker_pool():
    osrm_hosts = Queue()
    for host in config['osrm']['hosts']:
        osrm_hosts.put(host)
    return Pool(initializer=distance_matrix_get_many_to_many_parallel_initializer, initargs=(osrm_hosts,))

class DistanceMatrix:

    max_table_size = config['osrm']['max_table_size']
    pool = None

    _row_indices = {}
    _col_indices = {}

    _time = []
    _dist = []

    @staticmethod
    def init():
        if not DistanceMatrix.pool:
            DistanceMatrix.pool = create_worker_pool()    

    @staticmethod
    def row_index(t):

        if isinstance(t, entities.Vehicle) or isinstance(t, entities.Spot):
            t = t.start_loc
        elif isinstance(t, entities.Trip):
            t = t.finish_loc

        if t._row_idx == -1:
            if t in DistanceMatrix._row_indices:
                t._row_idx = DistanceMatrix._row_indices[t]
            else:
                t._row_idx = len(DistanceMatrix._row_indices)
                DistanceMatrix._row_indices[t] = t._row_idx

        return t._row_idx

    @staticmethod
    def col_index(t):

        if isinstance(t, entities.Vehicle) or isinstance(t, entities.Spot):
            t = t.start_loc
        elif isinstance(t, entities.Trip):
            t = t.start_loc

        if t._col_idx == -1:
            if t in DistanceMatrix._col_indices:
                t._col_idx = DistanceMatrix._col_indices[t]
            else:
                t._col_idx = len(DistanceMatrix._col_indices)
                DistanceMatrix._col_indices[t] = t._col_idx

        return t._col_idx

    @staticmethod
    def prepare(these, those):

        rows = [DistanceMatrix.row_index(this) for this in these]
        cols = [DistanceMatrix.col_index(that) for that in those]

        for row in DistanceMatrix._time:
            row.extend([sys.maxint] * (len(DistanceMatrix._col_indices) - len(row)))
        DistanceMatrix._time.extend([sys.maxint] * len(DistanceMatrix._col_indices) for _ in xrange(len(DistanceMatrix._row_indices) - len(DistanceMatrix._time)))

        for row in DistanceMatrix._dist:
            row.extend([sys.maxint] * (len(DistanceMatrix._col_indices) - len(row)))
        DistanceMatrix._dist.extend([sys.maxint] * len(DistanceMatrix._col_indices) for _ in xrange(len(DistanceMatrix._row_indices) - len(DistanceMatrix._dist)))

        return rows, cols

    @staticmethod
    def get_many_to_many(these, those):

        DistanceMatrix.init()

        these = [t.start_loc if isinstance(t, entities.Vehicle) or isinstance(t, entities.Spot) else (t.finish_loc if isinstance(t, entities.Trip) else t) for t in these]
        those = [t.start_loc if isinstance(t, entities.Vehicle) or isinstance(t, entities.Spot) or isinstance(t, entities.Trip) else t for t in those]

        DistanceMatrix.prepare(these, those)

        for times, distances in DistanceMatrix.pool.imap_unordered(distance_matrix_get_many_to_many_parallel_func, product(util.grouper(these, DistanceMatrix.max_table_size), util.grouper(those, DistanceMatrix.max_table_size))):
            for (src, trgt), time in times.iteritems():
                DistanceMatrix._time[DistanceMatrix.row_index(src)][DistanceMatrix.col_index(trgt)] = time.total_seconds()
            for (src, trgt), dist in distances.iteritems():
                DistanceMatrix._dist[DistanceMatrix.row_index(src)][DistanceMatrix.col_index(trgt)] = dist

    @staticmethod
    def get_one_to_many(this, those):
        return DistanceMatrix.get_many_to_many([this], those)

    @staticmethod
    def dist(s, t):
        if isinstance(s, list) and isinstance(t, list):
            rows, cols = DistanceMatrix.prepare(s, t)
            return [[DistanceMatrix._dist[row][col] for col in cols] for row in rows]
        else:
            return DistanceMatrix._dist[DistanceMatrix.row_index(s)][DistanceMatrix.col_index(t)]

    @staticmethod
    def time(s, t):
        if isinstance(s, list) and isinstance(t, list):
            rows, cols = DistanceMatrix.prepare(s, t)
            return [[DistanceMatrix._time[row][col] for col in cols] for row in rows]
        else:
            return DistanceMatrix._time[DistanceMatrix.row_index(s)][DistanceMatrix.col_index(t)]

    @staticmethod
    def timedelta(s, t):
        if isinstance(s, list) and isinstance(t, list):
            rows, cols = DistanceMatrix.prepare(s, t)
            return [[timedelta(seconds=DistanceMatrix._time[row][col]) for col in cols] for row in rows]
        else:
            return timedelta(seconds=DistanceMatrix._time[DistanceMatrix.row_index(s)][DistanceMatrix.col_index(t)])

    @staticmethod
    def set(these, those, time, dist):
        rows, cols = DistanceMatrix.prepare(these, those)
        for row, timerow in izip(rows, time):
            for col, value in izip(cols, timerow):
                DistanceMatrix._time[row][col] = value
        for row, distrow in izip(rows, dist):
            for col, value in izip(cols, distrow):
                DistanceMatrix._dist[row][col] = value