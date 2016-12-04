from collections import OrderedDict
from itertools import izip
from datetime import timedelta

import numpy

import entities

class Instance:
    _basename = ''

    _fuelpermeter = 0
    _refuelpersecond = 0
    _costpermeter = 0
    _costpercar = 0

    _vehicles = []
    _customers = {}
    _routes = {}
    _customertrips = {}
    _trips = []
    _refuelpoints = []
    _index = {}

    _time = None
    _dist = None
    _paretorefuelpoints = None
    _initialfuel = None

    def __init__(self, vehicles, customers, routes, routecost, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar):

        self._fuelpermeter = fuelpermeter
        self._refuelpersecond = refuelpersecond
        self._costpermeter = costpermeter
        self._costpercar = costpercar

        self._vehicles = list(vehicles)
        self._customers = OrderedDict(customers)
        self._routes = OrderedDict(routes)
        self._routecost = OrderedDict(routecost)
        
        self._customertrips = OrderedDict((customer, [trip for route in routes for trip in self._routes.get(route)]) for (customer, routes) in self._customers.iteritems())
        
        triproutetable, trips = izip(*sorted([(r, t) for (r, ts) in self._routes.iteritems() for t in ts], key=lambda (r,t): (t.start_time, t.duration, t.distance, t.start_loc, t.finish_loc)))
        tripcustomertable, _ = izip(*sorted([(c, t) for (c, ts) in self._customertrips.iteritems() for t in ts], key=lambda (c,t): (t.start_time, t.duration, t.distance, t.start_loc, t.finish_loc)))
        
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
        return self.vehicles + self.trips + self.refuelpoints
    
    @property
    def maxrange(self):
        return 1.0 / self._fuelpermeter
    
    @property
    def starttime(self):
        return min(map((lambda t: t.start_time), self._trips))
    
    @property
    def finishtime(self):
        return max(map((lambda t: t.finish_time), self._trips))
    
    @property
    def dictionary(self):
        return entities.get_dict(self.extendedvertices)
    
    def customer(self, t):
        return self._customertable[self._index[t]];
    
    def route(self, t):
        return self._routetable[self._index[t]];
    
    def customer_starttime(self, t):
        return min(map((lambda t: t.start_time), self._customertrips.get(self.customer(t))))
    
    def latest_starttime(self, c):
        return max(map(lambda k: k.start_time, self._customertrips.get(c)))
    
    def time(self, s, t):
        return self._time[self._index[s], self._index[t]]

    def timedelta(self, s=None, t=None):
        return timedelta(seconds = int(self._time[self._index[s], self._index[t]]))

    def dist(self, s, t):
        if isinstance(s, list) and isinstance(t, list):
            return [[self._dist[self._index[tmp_s], self._index[tmp_t]] for tmp_t in t] for tmp_s in s]
        return self._dist[self._index[s], self._index[t]]

    def fuel(self, s, t=None):
        return self._fuelpermeter * (self._dist[self._index[s], self._index[t]] if t else 0.0 if self._index[s] < len(self._vehicles) else s.distance * 1000.0)

    def cost(self, s, t=None):
        return (self._costpercar if self._index[s] < len(self._vehicles) else 0) + self._costpermeter * self._dist[self._index[s], self._index[t]] if t else 0.0 if self._index[s] < len(self._vehicles) else self._costpermeter * s.distance

    def initialfuel(self, s):
        return self._initialfuel[self._index[s]]
    
    def subinstance(self, vehicles=None, customers=None, refuelpoints=None):
        vehicles = list(self._vehicles if vehicles is None else vehicles)
        customers = OrderedDict((customer, self._customers.get(customer)) for customer in (self._customers.iterkeys() if customers is None else customers))
        routes = OrderedDict((route, self._routes.get(route)) for routes in customers.itervalues() for route in routes)
        refuelpoints = list(self._refuelpoints if refuelpoints is None else refuelpoints)
        routecost = OrderedDict((route, self._routecost.get(route)) for route in routes)

        subinst = Instance(vehicles, customers, routes, routecost, refuelpoints, self._fuelpermeter, self._refuelpersecond, self._costpermeter, self._costpercar)
        
        indices = numpy.fromiter((self._index[v] for v in subinst.vertices), dtype=numpy.int)
        extindices = numpy.fromiter((self._index[v] for v in subinst.extendedvertices), dtype=numpy.int)

        subinst._time = None if self._time is None else self._time[extindices[:,None], extindices[None,:]]
        subinst._dist = None if self._dist is None else self._dist[extindices[:,None], extindices[None,:]]
        subinst._paretorefuelpoints = [[list(self._paretorefuelpoints[i][j]) for j in indices] for i in indices] if self._paretorefuelpoints else None

        return subinst