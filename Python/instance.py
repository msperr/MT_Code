from collections import OrderedDict
from itertools import izip

import numpy

basename = r'..\data\instance'

class instance:
    _basename = ''

    _fuelpermeter = 0
    _refuelpersecond = 0
    _costpermeter = 0
    _costpercar = 0

    _vehicles = []
    _customers = {}
    _routes = {}
    _trips = []
    _refuelpoints = []
    _index = {}

    _time = None
    _dist = None
    _paretorefuelpoints = None
    _initialfuel = None

    def __init__(self, vehicles, customers, routes, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar):

        self._fuelpermeter = fuelpermeter
        self._refuelpersecond = refuelpersecond
        self._costpermeter = costpermeter
        self._costpercar = costpercar

        self._vehicles = list(vehicles)
        self._customers = OrderedDict(customers)
        self._routes = OrderedDict(routes)
        
        customers = OrderedDict()
        for (customer, tmp_routes) in self._customers.iteritems():
            customers.update(OrderedDict([(customer, [trip for route in tmp_routes for trip in self._routes.get(route)])]))
        
        triproutetable, trips = izip(*sorted([(r, t) for (r, ts) in self._routes.iteritems() for t in ts], key=lambda (r,t): (t.start_time, t.duration, t.distance, t.start_loc, t.finish_loc)))
        tripcustomertable, _ = izip(*sorted([(c, t) for (c, ts) in customers.iteritems() for t in ts], key=lambda (c,t): (t.start_time, t.duration, t.distance, t.start_loc, t.finish_loc)))
        
        self._trips = list(trips)
        self._routetable = numpy.array([-1] * len(self._vehicles) + list(triproutetable), dtype=numpy.int32)
        self._customertable = numpy.array([-1] * len(self._vehicles) + list(tripcustomertable), dtype=numpy.int32)
        self._refuelpoints = list(refuelpoints)
        self._index = {s: i for i, s in enumerate(self.extendedvertices)}
        self._initialfuel = numpy.ones((len(vehicles),), dtype=float)
    
    @property
    def vehicles(self):
        return self._vehicles
    
    @property
    def trips(self):
        return self._trips

    @property
    def refuelpoints(self):
        return self._refuelpoints
    
    @property
    def vertices(self):
        return self.vehicles + self.trips
    
    @property
    def extendedvertices(self):
        return self._vehicles + self._trips + self._refuelpoints
    
    def customer(self, t):
        return self._customers.keys()[self._customertable[self._index[t]]];
    
    def route(self, t):
        return self._routes.keys()[self._routetable[self._index[t]]];