from argparse import ArgumentParser
import random
import os
import subprocess

import storage
import entities
import taskgraph
from config import config

def determine_estimated_cost(instance):
    return dict([(r, instance.route_cost(r) + sum(instance.cost(t) for t in trips)) for r, trips in instance._routes.iteritems()])

def determine_improved_cost(solution):
    
    instance = solution.instance    
    cost = dict([(t, 0) for t in solution.trips])
    
    for v, d in solution.duties.iteritems():
        
        duty = list(d)
        length = len([t for t in duty if isinstance(t, entities.Trip)])
        
        fuel_sum = []
        fuel_cost = []
        tmp_trips = []
        r = None
        t_prev = None
        t_next = None
        
        for t in duty:
            if isinstance(t, entities.Trip):
                tmp_trips.append(t)
                if r:
                    fuel_cost.append(min(instance.cost(t_prev, r) + instance.cost(r, t) - instance.cost(t_prev, t), 0))
                    r = None
                t_prev = t
            else:
                r = t
                fuel_sum.append(sum([instance.fuel(t) for t in tmp_trips]))
                tmp_trips = []
        
        duty.append(v)
        refuel_index = 0
        tmp_trips = []
        
        for i in range(len(duty)-1):
            t = duty[i]
            t_prev = duty[i-1] if not isinstance(duty[i-1], entities.RefuelPoint) else duty[i-2]
            t_next = (duty[i+1] if not isinstance(duty[i+1], entities.RefuelPoint) else duty[i+2]) if i < len(duty)-2 else None
            if isinstance(t, entities.Trip):
                tmp_cost = cost.get(t)
                tmp_cost += instance._costpercar / length + (instance.cost(t_prev, t) + (0 if t_next is None else instance.cost(t, t_next))) / 2
                cost.update([(t, tmp_cost)])
                tmp_trips.append(t)
            else:
                for tr in tmp_trips:
                    tmp = fuel_cost[refuel_index] * instance.fuel(tr)/fuel_sum[refuel_index]
                    cost.update([(tr, cost.get(tr) + tmp)])
                tmp_trips = []
                refuel_index += 1
    
    return dict([(c, instance.route_cost(route) + sum(cost.get(t) for t in instance._routes.get(route))) for c, route in solution.customers.iteritems()])

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('-i', type=str, dest='instance')
    parser.add_argument('-g', type=str, dest='graph')
    parser.add_argument('-s', type=str, dest='solution')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
    
    solutionfile = config['data']['base'] + args.solution
    basename = os.path.join(os.path.dirname(solutionfile), os.path.basename(solutionfile).split('.')[0])
    compress = '' if args.compress else '.gz'
    
    print '[INFO] Process started'
    
    instance = None
    print 'Loading instance ...'
    if args.instance:
        instancefile = config['data']['base'] + args.instance
        instance = storage.load_instance_from_json(instancefile)
        print 'Instance successfully loaded from %s' % instancefile
    else:
        instancefile = os.path.join(os.path.dirname(solutionfile), os.path.basename(solutionfile).split('.')[0])
        if os.path.isfile(instancefile + '.json.gz'):
            instancefile += '.json.gz'
            instance = storage.load_instance_from_json(instancefile)
            print 'Instance successfully loaded from %s' % instancefile
        elif os.path.isfile(instancefile + '.json'):
            instancefile += '.json'
            instance = storage.load_instance_from_json(instancefile)
            print 'Instance successfully loaded from %s' % instancefile
    assert not instance is None
    
    if args.statistics:
        print 'Instance Basename', instance._basename
        print 'Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(instance.vehicles), len(instance._customers), len(instance._routes), len(instance._trips), len(instance._refuelpoints))
        print 'Start: %s, Finish: %s' % (instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), instance.finishtime.strftime('%Y-%m-%d %H:%M:%S'))
    
    print 'Loading solution ...'
    solution = storage.load_solution_from_xpress(solutionfile, instance)
    print 'Successfully loaded solution from %s' % solutionfile
    
    if args.statistics:
        evaluation = solution.evaluate_detailed()
        print 'Solution Basename', solution._basename
        print 'Total Cost: %.1f, Duties: %d' % (evaluation[0], evaluation[3])
    
    G = None
    print 'Loading task graph ...'
    if args.graph:
        graphfile = config['data']['base'] + args.graph
        G = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
        print 'Successfully loaded task graph from %s' % graphfile
    else:
        graphfile = os.path.join(os.path.dirname(solutionfile), os.path.basename(solutionfile).split('.')[0])
        if os.path.isfile(graphfile + '.graph.json.gz'):
            graphfile += '.graph.json.gz'
            G = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
            print 'Successfully loaded task graph from %s' % graphfile
        elif os.path.isfile(graphfile + '.graph.json'):
            graphfile += '.graph.json'
            G = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
            print 'Successfully loaded task graph from %s' % graphfile
    assert not G is None
    
    improved_cost = determine_improved_cost(solution)
    estimated_cost = determine_estimated_cost(solution.instance)
    
    #for c, route in solution.customers.iteritems():
    #    print 'Customer', '%3d'%c, 'Ratio', round(improved_cost[c]/estimated_cost[route], 2), 'Estimated Cost', [('%3d'%r, round(estimated_cost[r], 1)) for r in solution.instance._customers.get(c)], 'Route', route, 'Improved Cost', round(improved_cost[c], 1)
        
    # determine critical customer(s)
    # customers with high ratio and similar time windows
    # consider if alternatives are available
    # high ratio with small estimated cost does not give much saving

    critical_customers = random.sample(solution.customers.keys(), 2)
    
    if args.statistics:
        print 'Reviewed Customers: %d' % len(critical_customers)
        print 'Start: %s, Finish: %s' % (min(instance.earliest_starttime(c) for c in critical_customers).strftime('%Y-%m-%d %H:%M:%S'), max(instance.latest_starttime(c) for c in critical_customers).strftime('%Y-%m-%d %H:%M:%S'))
    
    print 'Creating task graph for subproblem ...'
    G_hsp, startpoints, endpoints, trips = taskgraph.split_taskgraph_subproblem(instance, G, solution, critical_customers)
    print 'Task graph for subproblem successfully created'
    
    if args.statistics:
        print 'Trips: %s, Vehicles: %s, Startpoints: %s, Endpoints: %s' % (len(trips), len(startpoints&set(instance.vehicles)), len(startpoints&set(instance.trips)), len(endpoints))
    
    xpressfile = '%s.hsp.txt%s' %(solution._basename, compress)
    print 'Exporting taskgraph for subproblem ...'
    taskgraph.save_subproblem_taskgraph_to_xpress(xpressfile, instance, G_hsp, startpoints, endpoints, trips, critical_customers)
    print 'Task graph for subproblem successfully exported to %s' % xpressfile
    
    print 'Execute Mosel ...'
    mosel = config['mosel'] + 'HSP.mos'
    subprocess.Popen(['mosel', mosel, 'SOLUTION="%s"' % xpressfile])
    print 'Mosel finished'
        
    print '[INFO] Process finished'