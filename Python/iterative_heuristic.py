from argparse import ArgumentParser
import random
from os import path
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
    parser.add_argument('solution', type=str)
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
    
    compress = '' if args.compress else '.gz'
    solutionname = args.solution
    instancename = path.join(path.dirname(solutionname), path.basename(solutionname).split('.')[0])
    
    print '[INFO] Process started'
    
    print 'Execute Mosel ...'
    mosel = config['mosel'] + 'MMILP_E.mos'
    i = subprocess.call(['mosel', mosel, 'INSTANCE=%s,SOLUTION=%s' % (instancename, solutionname)]) 
    print 'Mosel finished', i
    
    instance = None
    print 'Loading instance ...'
    instancefile = config['data']['base'] + instancename
    if path.isfile(instancefile + '.json.gz'):
        instancefile += '.json.gz'
        instance = storage.load_instance_from_json(instancefile)
        print 'Instance successfully loaded from %s' % instancefile
    elif path.isfile(instancefile + '.json'):
        instancefile += '.json'
        instance = storage.load_instance_from_json(instancefile)
        print 'Instance successfully loaded from %s' % instancefile
    assert not instance is None
    
    if args.statistics:
        print 'Instance Basename', instance._basename
        print 'Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(instance.vehicles), len(instance._customers), len(instance._routes), len(instance._trips), len(instance._refuelpoints))
        print 'Start: %s, Finish: %s' % (instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), instance.finishtime.strftime('%Y-%m-%d %H:%M:%S'))
    
    solution = None
    print 'Loading solution ...'
    solutionfile = config['data']['base'] + args.solution + '.fuelsolution'
    if path.isfile(solutionfile + '.txt.gz'):
        solutionfile += '.txt.gz'
        solution = storage.load_solution_from_xpress(solutionfile, instance)
        print 'Solution successfully loaded from %s' % solutionfile
    if path.isfile(solutionfile + '.txt'):
        solutionfile += '.txt'
        solution = storage.load_solution_from_xpress(solutionfile, instance)
        print 'Solution successfully loaded from %s' % solutionfile
    assert not solution is None
    
    if args.statistics:
        evaluation = solution.evaluate_detailed()
        print 'Solution Basename', solution._basename
        print 'Total Cost: %.1f, Duties: %d' % (evaluation[0], evaluation[3])
    
    graph = None
    print 'Loading task graph ...'
    graphfile = config['data']['base'] + instancename + '.graph'
    if path.isfile(graphfile + '.json.gz'):
        graphfile += '.json.gz'
        graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
        print 'Task graph successfully loaded from %s' % graphfile
    elif path.isfile(graphfile + '.json'):
        graphfile += '.json'
        graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
        print 'Task graph successfully loaded from %s' % graphfile
    assert not graph is None
    
    improved_cost = determine_improved_cost(solution)
    estimated_cost = determine_estimated_cost(solution.instance)
    
    #for c, route in solution.customers.iteritems():
    #    print 'Customer', '%3d'%c, 'Ratio', round(improved_cost[c]/estimated_cost[route], 2), 'Estimated Cost', [('%3d'%r, round(estimated_cost[r], 1)) for r in solution.instance._customers.get(c)], 'Route', route, 'Improved Cost', round(improved_cost[c], 1)
        
    # determine critical customer(s)
    # customers with high ratio and similar time windows
    # consider if alternatives are available
    # high ratio with small estimated cost does not give much saving

    critical_customers = random.sample(solution.customers.keys(), 3)
    #critical_customers = [38, 30, 45]

    if args.statistics:
        print 'Reviewed Customers: %d' % len(critical_customers), critical_customers
        print 'Start: %s, Finish: %s' % (min(instance.earliest_starttime(c) for c in critical_customers).strftime('%Y-%m-%d %H:%M:%S'), max(instance.latest_starttime(c) for c in critical_customers).strftime('%Y-%m-%d %H:%M:%S'))
    
    print 'Creating task graph for subproblem ...'
    graph_hsp, startpoints, endpoints, trips = taskgraph.split_taskgraph_subproblem(instance, graph, solution, critical_customers)
    print 'Task graph for subproblem successfully created'
    
    if args.statistics:
        print 'Trips: %s, Vehicles: %s, Startpoints: %s, Endpoints: %s' % (len(trips), len(startpoints&set(instance.vehicles)), len(startpoints&set(instance.trips)), len(endpoints))
    
    xpressfile = config['data']['base'] + solutionname + '.hsp.txt%s' % compress
    print 'Exporting taskgraph for subproblem ...'
    taskgraph.save_subproblem_taskgraph_to_xpress(xpressfile, instance, graph_hsp, startpoints, endpoints, trips, critical_customers)
    print 'Task graph for subproblem successfully exported to %s' % xpressfile
    
    print 'Executing Mosel ...'
    mosel = config['mosel'] + 'HSP.mos'
    i = subprocess.call(['mosel', mosel, 'INSTANCE=%s' % solutionname])
    print 'Mosel finished', i
    
    solutionfile = config['data']['base'] + solutionname + '.hsp.solution.txt%s' % compress
    print 'Loading partial solution ...'
    new_solution = storage.load_partial_solution_from_xpress(solutionfile, solution, instance, endpoints)
    print 'Partial Solution successfully loaded from %s' % solutionfile
    
    if args.statistics:
        evaluation = new_solution.evaluate_detailed()
        print 'Solution Basename', new_solution._basename
        print 'Total Cost: %.1f, Duties: %d' % (evaluation[0], evaluation[3])
    
    solutionfile = config['data']['base'] + args.solution + '.solution.txt%s' % compress
    print 'Exporting solution ...'
    storage.save_solution_to_xpress(solutionfile, new_solution)
    print 'Successfully exported solution to %s' % solutionfile
        
    print '[INFO] Process finished'