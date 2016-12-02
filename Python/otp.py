from Queue import Queue
import os
import time as timemodule
from argparse import ArgumentParser
from threading import Thread
import subprocess

import requests

import util
from config import config

class Otp(object):

    def __init__(self, host=config['otp']['host'], port=config['otp']['port'], router=config['otp']['router']):
        self.host = host
        self.port = port
        self.router = router

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def route(self, src, dst, finish_time, modes=['WALK', 'CAR', 'TRANSIT'], maxWalkDistance=None, numItineraries=None, walkSpeed=None):

        parameters = {
            'fromPlace': '%f,%f' % (src.lat, src.lon),
            'toPlace': '%f,%f' % (dst.lat, dst.lon),
            'time': finish_time.strftime('%I:%M%p'),
            'date': finish_time.strftime('%m-%d-%Y'),
            'mode': ','.join(modes),
            'arriveBy': 'false',
            'wheelchair': 'false',
            'locale': 'en'
        }

        if maxWalkDistance != None:
            parameters['maxWalkDistance'] = maxWalkDistance # meters

        if numItineraries != None:
            parameters['numItineraries'] = numItineraries

        if walkSpeed != None:
            parameters['walkSpeed'] = walkSpeed # meters per second

        query = util.url('http', self.host, self.port, 'otp/routers/%s/plan' % self.router, parameters)

        headers = {
            'Accept-Encoding': 'application/json'
        }

        r = requests.get(query, headers=headers)
        response = r.json()

        if 'error' in response:
            #print response['error']['message'], '(%s), (%s)' % (parameters['fromPlace'], parameters['toPlace'])
            return None
        return response['plan']['itineraries']

if __name__ == '__main__':

    class AsynchronousFileReader(Thread):
     
        def __init__(self, fd, queue, prefix=''):
            assert isinstance(queue, Queue)
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

    assert config['otp']['host'] == args.address, 'IP address does not match'

    port = config['otp']['port']
    router = config['otp']['router']

    print 'Run OTP router %s on port %d' % (router, port)

    jar = os.path.join(os.getcwd(), config['otp']['jar'])
    maxheapsize = config['otp']['maxheapsize']
    graphs = os.path.join(os.getcwd(), config['otp']['graphs'])

    processes = [subprocess.Popen(['java', '-Xmx%dG' % maxheapsize, '-jar', jar, '--graphs', graphs, '--router', router, '--server'], cwd=os.path.dirname(jar), stdout=subprocess.PIPE, stderr=subprocess.PIPE)]

    stdout_queue = Queue()
    stderr_queue = Queue()

    stdout_readers = [AsynchronousFileReader(process.stdout, stdout_queue, '%d: ' % i) for i, process in enumerate(processes)]
    stderr_readers = [AsynchronousFileReader(process.stderr, stderr_queue, '%d: ' % i) for i, process in enumerate(processes)]

    readers = stdout_readers + stderr_readers
    for reader in readers:
        reader.start()

    while not all(reader.eof() for reader in readers):

        while not stdout_queue.empty():
            print stdout_queue.get(),

        while not stderr_queue.empty():
            print stderr_queue.get(),

        timemodule.sleep(.1)

    for reader in readers:
        reader.join()

    for process in processes:
        process.stdout.close()
        process.stderr.close()