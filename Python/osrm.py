import Queue
from itertools import izip, product, count
import os
import time
from argparse import ArgumentParser
from threading import Thread
import multiprocessing
import subprocess

import requests
from polyline.codec import PolylineCodec
import progressbar
import numpy

import util
import entities
from config import config

class osrm(object):

    def __init__(self, host='localhost', port=5000, max_table_size=100):
        self.host = host
        self.port = port
        self.max_table_size = max_table_size

    def route(self, points):

        query = util.url('http', self.host, self.port, 'viaroute', {
            'instructions': 'true',
            'alt': 'false'
        })
        query =  query + '&' + '&'.join('loc=%f,%f' % (p.lat, p.lon) for p in points)
        response = requests.get(query).json()

        assert 'route_geometry' in response, "Error: Missing route_geometry in router response"
        return [entities.Point(lat=lat/10.0, lon=lon/10.0) for lat, lon in PolylineCodec().decode(response['route_geometry'])], response['via_indices']

    def matrix(self, sources, targets):

        query = util.url('http', self.host, self.port, 'matrix', {})
        query = query + '?' + '&'.join([('src=%f,%f' % (src.lat, src.lon)) for src in sources if src] + [('trgt=%f,%f' % (trgt.lat, trgt.lon)) for trgt in targets if trgt])
        response = requests.get(query).json()

        time = numpy.asarray(response['duration_table'], dtype=numpy.int32) / 10
        dist = numpy.asarray(response['distance_table'])
        assert numpy.all(time <= 100000) and numpy.all(dist <= 135000), "Error: Invalid entries in router response\n%s" % query
        return time, dist

def router_init(osrm_instance_queue):
    global osrm_instance
    params = osrm_instance_queue.get()
    osrm_instance = osrm(**params)

def router_route(points):
    global osrm_instance
    return osrm_instance.route(points)

def router_matrix(args):
    global osrm_instance
    sources, targets = args
    return osrm_instance.matrix(sources, targets)

class osrm_parallel(object):

    def __init__(self, osrm_instances=config['osrm']['hosts'], max_table_size=config['osrm']['max_table_size']):
        self.osrm_instances = list(osrm_instances)
        self.max_table_size = max_table_size

    def __enter__(self):
        osrm_instance_queue = multiprocessing.Queue()
        for osrm_instance in self.osrm_instances:
            osrm_instance_queue.put(dict(osrm_instance, max_table_size=self.max_table_size))
        self.pool = multiprocessing.Pool(processes=len(self.osrm_instances), initializer=router_init, initargs=(osrm_instance_queue,))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.pool.terminate()
        self.pool.join()
        self.pool = None

    def route(self, routes):
        return self.pool.imap(router_route, routes)

    def matrix(self, these, those):
        
        these = [t.finish_loc if isinstance(t, entities.Trip) else (t.start_loc if isinstance(t, entities.Vehicle) else t.location) for t in these]
        those = [t.start_loc if isinstance(t, (entities.Trip, entities.Vehicle)) else t.location for t in those]

        time = numpy.empty((len(these), len(those)), dtype=numpy.int32)
        dist = numpy.empty((len(these), len(those)), dtype=numpy.int32)

        n = self.max_table_size
        progress = progressbar.ProgressBar(maxval=((len(these)+n-1)/n) * ((len(those)+n-1)/n), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
        progresscount = count(1)

        for (timeblock, distblock), (i, j) in izip(self.pool.imap(router_matrix, product(util.grouper(these, n), util.grouper(those, n))), product(range(0, len(these), n), range(0, len(those), n))):
            time[i:i + timeblock.shape[0],j:j + timeblock.shape[1]] = timeblock
            dist[i:i + distblock.shape[0],j:j + distblock.shape[1]] = distblock
            progress.update(progresscount.next())
        progress.finish()

        return time, dist

if __name__ == '__main__':

    class AsynchronousFileReader(Thread):
     
        def __init__(self, fd, queue, prefix=''):
            assert isinstance(queue, Queue.Queue)
            assert callable(fd.readline)
            Thread.__init__(self)
            self._fd = fd
            self._queue = queue
            self._prefix = prefix
     
        def run(self):
            for line in iter(self._fd.readline, ''):
                self._queue.put('%s%s' % (self._prefix, line))
     
        def eof(self):
            return not self.is_alive() and self._queue.empty()

    parser = ArgumentParser()
    parser.add_argument('address', type=str, nargs='?', default='localhost')
    args = parser.parse_args()

    ports = [instance['port'] for instance in config['osrm']['hosts'] if instance['host'] == args.address]

    print 'Run OSRM on port(s) %s' % ', '.join('%d' % port for port in ports)

    osrm = os.path.join(os.getcwd(), config['osrm']['executable'])
    osm = os.path.join(os.getcwd(), config['osrm']['osm'])

    print osrm
    processes = [subprocess.Popen([osrm, osm, '-p', '%d' % port], cwd=os.path.dirname(osrm), stdout=subprocess.PIPE, stderr=subprocess.PIPE) for port in ports]
 
    stdout_queue = Queue.Queue()
    stderr_queue = Queue.Queue()

    stdout_readers = [AsynchronousFileReader(process.stdout, stdout_queue, '%d: ' % port) for port, process in izip(ports, processes)]
    stderr_readers = [AsynchronousFileReader(process.stderr, stderr_queue, '%d: ' % port) for port, process in izip(ports, processes)]

    readers = stdout_readers + stderr_readers
    for reader in readers:
        reader.start()
 
    while not all(reader.eof() for reader in readers):

        while not stdout_queue.empty():
            print stdout_queue.get(),
 
        while not stderr_queue.empty():
            print stderr_queue.get(),
 
        time.sleep(.1)
 
    for reader in readers:
        reader.join()
 
    for process in processes:
        process.stdout.close()
        process.stderr.close()