from datetime import timedelta
from itertools import izip, chain, count
from enum import Enum

import progressbar

import osrm
from util import accumulate
from config import config 
import entities  

class VehicleState(Enum):
    waiting = 0
    recharging = 1
    deadhead = 2
    rental = 3

class Solution:
    
    _basename = ''

    instance = None
    duties = {}
    customers = {}
    trips = []
    dutydict = {}
    fuelstates = {}

    def __init__(self, instance, duties = None, customers = None):
        
        self.instance = instance
        self.duties = duties if duties else {s: [] for s in instance.vehicles}
        self.customers = customers if customers else {}
        self.trips = set(t for duty in self.duties.itervalues() for t in duty if isinstance(t, entities.Trip))
        self.dutydict = dict((trip, vehicle) for vehicle, trips in self.duties.iteritems() for trip in trips if isinstance(trip, entities.Trip))
    
    def determine_customers(self):
        
        customers = {}
        coveredtrips = set(t for duty in self.duties.itervalues() for t in duty if isinstance(t, entities.Trip))
        coveredroutes = set(self.instance.route(t) for t in coveredtrips)
        for customer, routes in self.instance._customers.iteritems():
            customers.update([(customer, (coveredroutes & set(routes)).pop())])
        
        return customers
    
    def determine_fuelstates(self, fuel_min, fuel_max):
        
        fuelstates = {}
        
        for v, duty in self.duties.iteritems():
            fuel_min_v = list(fuel_min[v])
            fuel_max_v = list(fuel_max[v])
            fuelstates.update(dict([(v, (fuel_min_v.pop(0), fuel_max_v.pop(0)))]))
            assert len(duty) == len(fuel_min_v) == len(fuel_max_v)
            fuelstates.update(dict([(duty[i], (fuel_min_v[i], fuel_max_v[i])) for i in range(len(duty)) if isinstance(duty[i], entities.Trip)]))
        
        return fuelstates
    
    def duty(self, t):
        return self.dutydict[t]

    def assert_valid(self, v=None):
        
        if not v:
            assert set(self.instance.vehicles) == set(self.duties.iterkeys()), '[WARN] Vehicle sets do not coincide'

            coveredtrips = set(t for duty in self.duties.itervalues() for t in duty if isinstance(t, entities.Trip))
            coveredroutes = set(self.instance.route(t) for t in coveredtrips)
            for route in coveredroutes:
                assert set(self.instance._routes.get(route)) <= coveredtrips , '[WARN] Route %d is not satisfied' % route
            for customer, routes in self.instance._customers.iteritems():
                assert len(coveredroutes & set(routes)) == 1, '[WARN] Customer %d is not satisfied' % customer
        
        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            t_prev = s
            for t in duty:
                assert not (isinstance(t, entities.RefuelPoint) and isinstance(t_prev, entities.RefuelPoint)), '[WARN] Refuelpoints %s and %s in a row' % (t, t_prev)
                t_prev = t
            assert not isinstance(t_prev, entities.RefuelPoint), '[WARN] Refuelpoint %s at the end of a duty' % t_prev

        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            e = s.fuel
            r = None
            for t in duty:
                assert e >= 0, '[WARN] Fuel for driving to %s is not sufficient' % s
                
                if isinstance(t, entities.Trip):
                    time = (t.start_time - s.finish_time).total_seconds() - (self.instance.time(s, r) + self.instance.time(r, t) if r else self.instance.time(s, t))
                    assert time >= 0, '[WARN] Not enough time for driving from %s to %s' % (s, t)
                    
                    if r:
                        e -= self.instance.fuel(s, r)
                        assert e >= 0, '[WARN] Refuel point between %s and %s cannot be reached' % (s, t)
                        e = min(e + self.instance._refuelpersecond * time, 1) - self.instance.fuel(r, t) - self.instance.fuel(t)
                    else:
                        e -= (self.instance.fuel(s, t) + self.instance.fuel(t))
                    
                    r = None
                    s = t
                
                else:
                    r = t
            assert e >= 0, '[WARN] Fuel for driving to %s is not sufficient' %s

    def evaluate(self, v=None):
        
        cost = 0.0 if v else sum(self.instance.route_cost(route) for route in self.customers.itervalues())
        
        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            for t in duty:
                cost += self.instance.cost(s, t)
                if isinstance(t, entities.Trip):
                    cost += self.instance.cost(t)
                s = t
                
        return cost

    def evaluate_detailed(self, v=None):
        
        cost = 0.0
        dist = 0.0
        time = 0.0
        used_vehicles = 0
        dist_customer = 0.0
        dist_deadhead = 0.0
        
        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            if duty:
                used_vehicles += 1
            for t in duty:
                cost += self.instance.cost(s, t)
                dist += self.instance.dist(s, t)
                dist_deadhead += self.instance.dist(s, t)
                time += self.instance.time(s, t)
                if isinstance(t, entities.Trip):
                    cost += self.instance.cost(t)
                    dist += t.distance
                    dist_customer += t.distance
                    time += t.duration.total_seconds()
                s = t
        
        cost_route = sum(self.instance.route_cost(r) for r in self.customers.itervalues())
        cost += cost_route
                
        return cost, dist, time, used_vehicles, dist_customer, dist_deadhead, cost_route

    def keyframes(self):

        keyframes = {v: [] for v in self.duties}
        for v, duty in self.duties.iteritems():
            e = v.fuel()
            keyframes[v].append((v.finish_time, v.finish_loc, e, VehicleState.waiting))
            for (s, _), (t, r) in izip(chain([(v, None)], duty[:-1]), duty):
                if r:
                    e -= self.instance.fuel(s, r)
                    keyframes[v].append((s.finish_time + self.instance.timedelta(s, r),                                        r,            e, VehicleState.deadhead))
                    time = min(t.start_time - self.instance.timedelta(s, r) - self.instance.timedelta(r, t) - s.finish_time, timedelta(seconds=(1 - e) / self.instance._refuelpersecond))
                    e = min(e + self.instance._refuelpersecond * time.total_seconds(), 1)
                    keyframes[v].append((s.finish_time + self.instance.timedelta(s, r) + time,                                 r,            e, VehicleState.recharging))
                    e -= self.instance.fuel(r, t)
                    keyframes[v].append((s.finish_time + self.instance.timedelta(s, r) + time + self.instance.timedelta(r, t), t.start_loc,  e, VehicleState.deadhead))
                    keyframes[v].append((t.start_time,                                                                         t.start_loc,  e, VehicleState.waiting))
                    e -= self.instance.fuel(t)
                    keyframes[v].append((t.finish_time,                                                                        t.finish_loc, e, VehicleState.rental))
                else:
                    e -= self.instance.fuel(s, t)
                    keyframes[v].append((s.finish_time + self.instance.timedelta(s, t), t.start_loc,  e, VehicleState.deadhead))
                    keyframes[v].append((t.start_time,                                  t.start_loc,  e, VehicleState.waiting))
                    e -= self.instance.fuel(t)
                    keyframes[v].append((t.finish_time,                                 t.finish_loc, e, VehicleState.rental))
        return keyframes

    def routes(self):

        keyframes = self.keyframes()

        with osrm.osrm_parallel() as router:

            routes = {v: [] for v in keyframes}

            progress = progressbar.ProgressBar(maxval=sum(max(len(duty)-1, 0) for duty in keyframes.itervalues()), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
            progresscount = count(1)
            for v, duty in keyframes.iteritems():
                routes[v].append(keyframes[v][0])
                for ((w, p, e, _), (z, q, f, s)), (points, _) in izip(izip(duty[:-1], duty[1:]), router.route((p, q) for (_, p, _, _), (_, q, _, _) in izip(duty[:-1], duty[1:]))):
                    dist = list(accumulate(u.airdist(v) for u, v in izip(points[:-1], points[1:])))
                    if points and dist[-1]:
                        routes[v].extend((w + timedelta(seconds=int((z - w).total_seconds() * d / dist[-1])), u, e + (f - e) * d / dist[-1], s) for u, d in izip(points[1:], dist))
                    else:
                        routes[v].append((z, q, f, s))
                    progress.update(progresscount.next())
            progress.finish()

        return routes