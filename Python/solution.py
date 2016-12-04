from datetime import timedelta
from itertools import izip, chain, count
import os
import gzip
from enum import Enum

import progressbar
import osrm
import xpress
import storage
from util import accumulate
from config import config   

class VehicleState(Enum):
    waiting = 0
    recharging = 1
    deadhead = 2
    rental = 3

class Solution:

    instance = None
    duties = {}

    def __init__(self, instance, duties = None):
        self.instance = instance
        self.duties = duties if duties else {s: [] for s in instance.vehicles}

    def export(self, filename, compress=None):

        if compress == None:
            compress = os.path.splitext(filename)[1] == '.gz'

        with (gzip.open(filename, 'wb') if compress else open(filename, 'w')) as f:
            xpress.write(f, {
                'duties': self.duties
            })

    def assertValid(self, v=None):

        if not v:
            assert set(self.instance.vehicles) == set(self.duties.iterkeys()), 'Vehicle sets not equal'

            coveredtrips = set(t for duty in self.duties.itervalues() for t, _ in duty)
            for customer, trips in self.instance._customers.iteritems():
                assert len(coveredtrips & set(trips)) == 1, 'Customer cover for {0} not satisfied'.format(customer)

        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            e = self.instance.initialfuel(s)
            for t, r in duty:
                assert e >= 0, 'Not enough fuel to travel to {0}'.format(s)
                if r:
                    time = (t.start_time - s.finish_time).total_seconds() - (self.instance.time(s, r) + self.instance.time(r, t))
                    assert time >= 0, 'Not enough time to travel from {0} over {1} to {2}'.format(s, r, t)
                    e -= self.instance.fuel(s, r)
                    assert e >= 0, 'Refuelpoint {0} between {1} and {2} not reached'.format(r, s, t)
                    e = min(e + self.instance._refuelpersecond * time, 1) - self.instance.fuel(r, t) - self.instance.fuel(t)
                else:
                    assert (t.start_time - s.finish_time).total_seconds() >= self.instance.time(s, t), 'Not enough time to travel from {0} to {1}'.format(s, t)
                    e -= self.instance.fuel(s, t) + self.instance.fuel(t)
                s = t
            assert e >= 0, 'Not enough fuel to travel to {0}'.format(s)

    def evaluate(self, v=None):

        cost = 0.0

        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            for t, r in duty:
                if r:
                    cost += self.instance.cost(s, r) + self.instance.cost(r, t)
                else:
                    cost += self.instance.cost(s, t)
                cost += self.instance.cost(t)
                s = t

        return cost

    def evaluate_detailed(self, v=None):

        cost = 0.0
        dist = 0.0
        time = 0.0
        used = 0
        dist_customer = 0.0
        dist_deadhead = 0.0

        for s, duty in ((v, self.duties[v]),) if v else self.duties.iteritems():
            if duty:
                used += 1
            for t, r in duty:
                if r:
                    cost += self.instance.cost(s, r) + self.instance.cost(r, t)
                    dist += self.instance.dist(s, r) + self.instance.dist(r, t)
                    dist_deadhead += self.instance.dist(s, r) + self.instance.dist(r, t)
                    time += self.instance.time(s, r) + self.instance.time(r, t)
                else:
                    cost += self.instance.cost(s, t)
                    dist += self.instance.dist(s, t)
                    dist_deadhead += self.instance.dist(s, t)
                    time += self.instance.time(s, t)
                cost += self.instance.cost(t)
                dist += t.distance * 1000.0
                dist_customer += t.distance * 1000.0
                time += t.duration.total_seconds()
                s = t

        return cost, dist, time, used, dist_customer, dist_deadhead

    def keyframes(self):

        keyframes = {v: [] for v in self.duties}
        for v, duty in self.duties.iteritems():
            e = self.instance.initialfuel(v)
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
    
def import_solution(filename, instancefile = None, instance = None):

    if instance is None:
        instance = storage.load_instance_from_json(instancefile)
        print 'Successfully loaded instance from %s' % instancefile
            
    parser_vehicles = xpress.parser_object(instance.vehicles)
    parser_trips = xpress.parser_object(instance.trips + instance.refuelpoints, **{'': None})

    parser_solution = xpress.parser_definitions({
        'Duties': xpress.parser_dict((parser_vehicles,), xpress.parser_list(parser_trips))
    })

    with open(filename) as f:
        data = f.read()
            
    progress = progressbar.ProgressBar(maxval=len(data), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
    solution = parser_solution.parse(data, progress)
    progress.finish()
        
    return Solution(instance, solution['Duties'])