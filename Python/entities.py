import xpress
from distance_matrix import DistanceMatrix

import math
from datetime import datetime, timedelta
import logging
logging.getLogger('fastkml.config').addHandler(logging.NullHandler())
import fastkml
import pygeoif

class Point:

    _row_idx = -1
    _col_idx = -1

    lon = 0.0
    lat = 0.0

    def __init__(self, lon, lat):
        self.lon = lon if lon else 0.0
        self.lat = lat if lat else 0.0

    def __key__(self):
        return (self.lon, self.lat)

    def __hash__(self):
        return hash(self.__key__())

    def __eq__(self, other):
        return self.__key__() == other.__key__()

    def __str__(self):
        return '(%f, %f)' % (self.lon, self.lat)

    def __repr__(self):
        return '(%f, %f)' % (self.lon, self.lat)

    def __xpress_index(self):
        return 'Point_%d_%d' % (math.floor(100000 * self.lon), math.floor(100000 * self.lat))

class Trip:

    location_id = -1
    vehicle_vin = ''
    start_time = datetime.now()
    start_loc = Point(0.0, 0.0)
    finish_loc = Point(0.0, 0.0)
    duration = timedelta()
    distance = 0.0
    servicedrive = False    

    def __init__(self, location_id, vehicle_vin, start_time, duration, distance, servicedrive, start_loc=None, start_longitude=0.0, start_latitude=0.0, finish_loc=None, finish_longitude=0.0, finish_latitude=0.0):
        self.location_id = location_id
        self.vehicle_vin = vehicle_vin
        self.start_time = start_time
        self.start_loc = start_loc if start_loc else Point(start_longitude, start_latitude)
        self.finish_loc = finish_loc if finish_loc else Point(finish_longitude, finish_latitude)
        self.duration = duration if isinstance(duration, timedelta) else timedelta(seconds = duration)
        self.distance = distance
        self.servicedrive = True if servicedrive else False    

    def __key__(self):
        return (self.vehicle_vin, self.start_time, self.start_loc)

    def __hash__(self):
        return hash(self.__key__())

    def __repr__(self):
        return 'Trip%s_%d_%d' % (self.start_time.strftime('%H%M%S'), math.floor(100000*self.start_loc.lon), math.floor(100000*self.start_loc.lat))

    def __eq__(self, other):
        return isinstance(other, Trip) and self.__key__() == other.__key__()

    def __le__(self, other):
        return self.start_time + self.duration <= other.start_time and self.start_time + self.duration + DistanceMatrix.timedelta(self, other) <= other.start_time

    def __lt__(self, other):
        return self.start_time + self.duration < other.start_time and self.start_time + self.duration + DistanceMatrix.timedelta(self, other) < other.start_time

    def __ge__(self, other):
        return other.start_time + other.duration <= self.start_time and other.start_time + other.duration + DistanceMatrix.timedelta(other, self) <= self.start_time

    def __gt__(self, other):
        return other.start_time + other.duration < self.start_time and other.start_time + other.duration + DistanceMatrix.timedelta(other, self) < self.start_time

    def __kml__(self):
        p = fastkml.Placemark(name='%d %s' % (self.location_id, self.start_time.strftime('%Y-%m-%d %H:%M:%S')))
        p.geometry = pygeoif.LineString([(q.lon, q.lat, 0.0) for q in [self.start_loc, self.finish_loc]])
        return p

    def __xpress_index__(self):
        return repr(self)

    @property
    def finish_time(self):
        return self.start_time + self.duration

class Route:
    
    def __init__(self, trips = []):
        self.id = id
        self.trips = trips
    
class Customer:
    
    id = None
    
    def __init__(self, id, routes = []):
        self.id = id
        self.routes = routes
    
class Vehicle:

    id = None
    start_loc = Point(0.0, 0.0)
    start_time = datetime.now()
    fuel = 1.0

    def __init__(self, id, start_time, fuel = 1.0, start_loc = None, longitude = 0.0, latitude = 0.0):
        if start_loc:
            if start_loc.lon == 0 or start_loc.lat == 0:
                raise ValueError('Vehicle with 0-start_coordinates')
        elif longitude==0 or latitude==0:
            raise ValueError('Vehicle with 0-start_coordinates')
        self.id = id
        self.start_time = start_time
        self.start_loc = start_loc if start_loc else Point(longitude, latitude)
        self.fuel = fuel

    def __key__(self):
        return (self.id, self.start_time, self.start_loc)

    def __hash__(self):
        return hash(self.__key__())

    def __eq__(self, other):
        return isinstance(other, Vehicle) and self.__key__() == other.__key__()

    def __le__(self, other):
        return isinstance(other, Trip) and self.start_time <= other.start_time and self.start_time + DistanceMatrix.timedelta(self, other) <= other.start_time

    def __lt__(self, other):
        return isinstance(other, Trip) and self.start_time < other.start_time and self.start_time + DistanceMatrix.timedelta(self, other) < other.start_time

    def __repr__(self):
        return '%s' % self.id

    def __xpress_index__(self):
        return 'Vehicle'+str(self.id)

    @property
    def finish_loc(self):
        return self.start_loc

    @property
    def finish_time(self):
        return self.start_time

class RefuelPoint(Point):
    
    id = None

    def __init__(self, id, lon, lat):
        if lon==0 or lat==0:
            raise ValueError('RefuelPoint with 0-coordinates')
        Point.__init__(self, lon, lat)
        self.id = id

    def __key__(self):
        return (self.id, self.lon, self.lat)

    def __hash__(self):
        return hash(self.__key__())

    def __eq__(self, other):
        return self.__key__() == other.__key__()
    
    def __xpress_index__(self):
        return 'RefuelPoint%s' % self.id
    
#-----------------------------------------------


def get_dict(points):
    dictionary = dict()
    for point in points:
        dictionary[xpress.xpress_index(point)] = point
    return dictionary


def compare(element1,element2):
    if isinstance(element1,Trip):
        if element1.finish_loc == element2.start_loc and element1.finish_time == element2.start_time:
            return True
    elif isinstance(element1,Spot) or isinstance(element1,Vehicle):
        if element1.start_loc == element2.start_loc and element1.start_time == element2.start_time:
            return True
    else:
        return False







class Spot:

    id = None
    start_loc = Point(0.0, 0.0)
    start_time = datetime.now()
    fuel = 1.0

    def __init__(self, id, start_time, fuel = 1.0, start_loc = None, longitude = 0.0, latitude = 0.0):
        if start_loc:
            if start_loc.lon == 0 or start_loc.lat == 0:
                raise ValueError('Spot with 0-start_coordinates')
        elif longitude==0 or latitude==0:
            raise ValueError('Spot with 0-start_coordinates')
        self.id = id
        self.start_time = start_time
        self.start_loc = start_loc if start_loc else Point(longitude, latitude)
        self.fuel = fuel

    def __key__(self):
        return (self.id, self.start_time, self.start_loc)

    def __hash__(self):
        return hash(self.__key__())

    def __eq__(self, other):
        return isinstance(other, Spot) and self.__key__() == other.__key__()

    def __le__(self, other):
        return isinstance(other, Trip) and self.start_time <= other.start_time and self.start_time + DistanceMatrix.timedelta(self, other) <= other.start_time

    def __lt__(self, other):
        return isinstance(other, Trip) and self.start_time < other.start_time and self.start_time + DistanceMatrix.timedelta(self, other) < other.start_time

    def __repr__(self):
        return 'Spot%s' % self.id

    def __xpress_index__(self):
        return 'Spot'+str(self.id)

    @property
    def finish_loc(self):
        return self.start_loc

    @property
    def finish_time(self):
        return self.start_time
    
class Splitpoint:

    id = None
    successor = Point(0.0, 0.0)
    time = datetime.now()
    weight = -1

    def __init__(self, id, time, weight = -1):
#    def __init__(self, id, successor, time, weight = -1):
        self.id = id
#        self.successor = successor
        self.time = time
        self.weight = weight

    def __key__(self):
#        return (self.id, self.successor, self.time)
        return (self.id, self.time)

    def __hash__(self):
        return hash(self.__key__())

    def __eq__(self, other):
        return isinstance(other, Splitpoint) and self.__key__() == other.__key__()

    def __repr__(self):
#        return 'Split%s' % (self.successor)
        return str(self.id)

    def __xpress_index__(self):
        return str(self.id)    

    @property
    def finish_time(self):
        return self.time

    @property
    def start_time(self):
        return self.time

def instance_check(trips,vehicles,vehicle_range=135000):
    errornumber = 0
    if not trips:
        raise ValueError
    if not vehicles:
        raise ValueError
    for trip in trips:
        if trip.duration == 0:
            print('Warning: The durration of trip %s is 0.' % trip)
            errornumber +=1
        if trip.start_loc.lon == 0:
            print('Warning: The longitude of the start-location of trip %s is 0.' % trip)
            errornumber +=1
        if trip.start_loc.lat == 0:
            print('Warning: The latitude of the start-location of trip %s is 0.' % trip)
            errornumber +=1
        if trip.finish_loc.lon == 0:
            print('Warning: The longitude of the finish-location of trip %s is 0.' % trip)
            errornumber +=1
        if trip.finish_loc.lat == 0:
            print('Warning: The latitude of the finish-location of trip %s is 0.' % trip)
            errornumber +=1
        number = 0
        for s in trips:
            if s <= trip:
                if DistanceMatrix.dist(s,trip)<vehicle_range:
                    number +=1
                    break
        if number == 0:
            for s in vehicles:
                if s <= trip:
                    if DistanceMatrix.dist(s,trip)<vehicle_range:
                        number +=1
                        break
        if number == 0:
            print('Warning: Trip %s can not be reached without refueling.' % trip)
            errornumber +=1
    return errornumber