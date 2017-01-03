from argparse import ArgumentParser
import os
import sys
sys.path.append(os.path.abspath(os.getenv('SCHEDULING_CPP_PATH', '..\\x64-v120-Release')))
import scheduling_cpp
import itertools

import time
import numpy
import progressbar

import storage
from util import Printer
from config import config

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('solution', type=str)
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    printer = Printer(verbose=args.verbose, statistics=args.statistics)
    compress = '' if args.compress else '.gz'
    solutionname = args.solution
    instancename = os.path.join(os.path.dirname(solutionname), os.path.basename(solutionname).split('.')[0])
    
    printer.write('Process started')
    
    instance = None
    printer.writeInfo('Loading instance ...')
    instancefile = config['data']['base'] + instancename
    if os.path.isfile(instancefile + '.json.gz'):
        instancefile += '.json.gz'
        instance = storage.load_instance_from_json(instancefile)
        printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    elif os.path.isfile(instancefile + '.json'):
        instancefile += '.json'
        instance = storage.load_instance_from_json(instancefile)
        printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    assert not instance is None
    
    printer.writeStat('Instance Basename: %s' % instance._basename)
    printer.writeStat('Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(instance.vehicles), len(instance._customers), len(instance._routes), len(instance._trips), len(instance._refuelpoints)))
    printer.writeStat('Start: %s, Finish: %s' % (instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), instance.finishtime.strftime('%Y-%m-%d %H:%M:%S')))
    
    export = False
    
    if instance._paretorefuelpoints is None:
    
        printer.writeInfo('Determine Pareto-optimal refuelpoints ...')
        
        export = True
    
        m = len(instance.vehicles)
        n = len(instance.trips)
        k = len(instance.refuelpoints)

        starttime  = numpy.array([time.mktime(t.start_time.timetuple()) for t in itertools.chain(instance.vehicles, instance.trips)])
        finishtime = numpy.array([time.mktime(t.finish_time.timetuple()) for t in itertools.chain(instance.vehicles, instance.trips)])

        a = (finishtime[:,None] + instance._time[:(m+n),:(m+n)]) < starttime[None,:]

        paretorefuelpoints = [[None] * (m + n) for _ in xrange(m + n)]

        try:
            progress = progressbar.ProgressBar(maxval=m+n, widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
            progresscount = itertools.count(1)

            phi = numpy.empty((4, k, m+n), dtype=numpy.float)        
            comparison = numpy.empty((4, k, k, m+n), dtype=numpy.bool)
            dominance = numpy.empty((k,k,m+n), dtype=numpy.bool)
            frontier = numpy.empty((k,m+n), dtype=numpy.bool)
            for s in xrange(m + n):
                refueltime = starttime[None,:] - instance._time[m+n:,:m+n] - instance._time[s,m+n:,None] - finishtime[s]
                phi[0,:,:] =            instance._costpermeter * instance._dist[s,m+n:,None]                                                                      + instance._costpermeter * instance._dist[m+n:,:m+n]
                phi[1,:,:] =            instance._fuelpermeter * instance._dist[s,m+n:,None] + numpy.maximum( - numpy.minimum(instance._refuelpersecond * refueltime, 1)     + instance._fuelpermeter * instance._dist[m+n:,:m+n], 0)
                phi[2,:,:] = numpy.maximum(instance._fuelpermeter * instance._dist[s,m+n:,None]               - numpy.minimum(instance._refuelpersecond * refueltime, 1), 0) + instance._fuelpermeter * instance._dist[m+n:,:m+n]
                phi[3,:,:] =            instance._fuelpermeter * instance._dist[s,m+n:,None]               - numpy.minimum(instance._refuelpersecond * refueltime, 1)     + instance._fuelpermeter * instance._dist[m+n:,:m+n]
                numpy.less_equal(phi[:,:,None,:], phi[:,None,:,:], comparison)
                numpy.all(comparison, 0, dominance)
                numpy.logical_and(dominance, numpy.invert(numpy.transpose(numpy.logical_and(dominance, numpy.tri(k,k)[:,:,None]), (1, 0, 2))), dominance)
                numpy.any(dominance, 0, frontier)
                numpy.logical_or(frontier, refueltime < 0, frontier)
                numpy.invert(frontier, frontier)
                paretorefuelpoints[s] = [numpy.flatnonzero(frontier[:,t]).tolist() for t in xrange(m+n)]
                progress.update(progresscount.next())

        except MemoryError as e:
            progress = progressbar.ProgressBar(maxval=numpy.sum(a), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
            progresscount = itertools.count(1)

            phi = numpy.empty((k,4), dtype=numpy.float)
            for s, t in itertools.izip(*a.nonzero()):
                refueltime = starttime[t] - instance._time[s,(m+n):] - numpy.transpose(instance._time[(m+n):,t]) - finishtime[s]
                phi[:,0] =            instance._costpermeter * instance._dist[s,(m+n):]                                                                      + instance._costpermeter * numpy.transpose(instance._dist[(m+n):,t])
                phi[:,1] =            instance._fuelpermeter * instance._dist[s,(m+n):] + numpy.maximum( - numpy.minimum(instance._refuelpersecond * refueltime, 1)     + instance._fuelpermeter * numpy.transpose(instance._dist[(m+n):,t]), 0)
                phi[:,2] = numpy.maximum(instance._fuelpermeter * instance._dist[s,(m+n):]               - numpy.minimum(instance._refuelpersecond * refueltime, 1), 0) + instance._fuelpermeter * numpy.transpose(instance._dist[(m+n):,t])
                phi[:,3] =            instance._fuelpermeter * instance._dist[s,(m+n):]               - numpy.minimum(instance._refuelpersecond * refueltime, 1)     + instance._fuelpermeter * numpy.transpose(instance._dist[(m+n):,t])
                dominance = numpy.all(phi[:,None,:] <= phi[None,:,:], 2)
                numpy.logical_and(dominance, numpy.invert(numpy.transpose(numpy.triu(dominance))), dominance)
                frontier = numpy.invert(numpy.logical_or(numpy.any(dominance, 0), refueltime < 0))
                paretorefuelpoints[s][t] = numpy.flatnonzero(frontier).tolist()
                progress.update(progresscount.next())
    
        progress.finish()
        instance._paretorefuelpoints = paretorefuelpoints
    
        printer.writeInfo('Pareto-optimal refuelpoints successfully determined')
    
    if export:
        instancefile = config['data']['base'] + instancename + '.json%s' % compress
        printer.writeInfo('Saving instance ...')
        storage.save_instance_to_json(instancefile, instance)
        printer.writeInfo('Instance successfully saved to %s' % instancefile)
    
    solution = None
    printer.writeInfo('Loading solution ...')
    solutionfile = config['data']['base'] + args.solution + '.solution'
    if os.path.isfile(solutionfile + '.txt.gz'):
        solutionfile += '.txt.gz'
        solution = storage.load_solution_from_xpress(solutionfile, instance)
        printer.writeInfo('Solution successfully loaded from %s' % solutionfile)
    elif os.path.isfile(solutionfile + '.txt'):
        solutionfile += '.txt'
        solution = storage.load_solution_from_xpress(solutionfile, instance)
        printer.writeInfo('Solution successfully loaded from %s' % solutionfile)
    assert not solution is None

    evaluation = solution.evaluate_detailed()
    printer.writeStat('Solution Basename: %s' % solution._basename)
    printer.writeStat('Total Cost: %.1f, Duties: %d' % (evaluation[0], evaluation[3]))
    
    printer.write('Heuristic solution computed')
    printer.write('Heuristic: Total Cost: %d, Vehicles: %d' % (round(evaluation[0]), evaluation[3]))
    
    milp = 0
    
    parameters = {
        "DECOMP": {

            "TolZero": 2.0e-16,
            "LogLevel": 3,
            "LogDebugLevel": 0,
            "LogLpLevel": 0,
            "LogIpLevel": 0,
            "LogDumpModel": 0,

            'SolveMasterAsMip': 1 if milp else 0,

            "PCStrategy": 0, # 1: FavorPrice, 2: FavorCut
            "CutCGL": 0,
            'RoundCutItersLimit': 0,

            "BranchEnforceInMaster": 0, # needs to be 0 due to quick fix of setMasterBounds
            "BranchEnforceInSubProb": 1, # needs to be 1 due to quick fix of setMasterBounds
            "TailoffLength": 1e10,
            "TailoffPercent": 0.0,

            'SubProbGapLimitExact': 0.0,
            'RedCostEpsilon': 1e-4,
            'checkForDuplicateCols': 0,
            #"CompressColumnsMasterGapStart": 2.0,

            "TimeLimit": 1800,
        },

        "CUSTOM": {
                
            "dropUnusedResources": 1,
            "forbidAlternatives": 1,
            "findExactCover": 1,

            "branchOnNumberOfVehicles": 1,
            "branchOnAlternativeTrips": 1,
            "branchOnLengthOfDuties": 1,
        }
    }
    
    for vehicle in solution.duties.iterkeys():
        print vehicle, "(%d): " % instance._index[vehicle] + ", ".join(["%s (%d)" % (trip, instance._index[trip]) for trip in solution.duties.get(vehicle)])
    
    printer.write('Computing optimal solution ...')
    
    status, message, sol = scheduling_cpp.Solve(parameters, instance, solution)
    sol.assertValid()
    
    printer.write('Process finished')