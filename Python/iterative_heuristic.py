from argparse import ArgumentParser
import random
from os import path
import subprocess
from datetime import timedelta

import storage
import entities
import taskgraph
from config import config

def determine_estimated_cost(instance):
    return dict([(r, instance.route_cost(r) + sum(instance.cost(t) for t in trips)) for r, trips in instance._routes.iteritems()])

def determine_improved_cost(solution):
    
    instance = solution.instance
    cost = {}
    
    for v, d in solution.duties.iteritems():
        
        duty = list(d)
        length = len([t for t in duty if isinstance(t, entities.Trip)])
        
        fuel_sum = []
        fuel_cost = []
        tmp_trips = []
        r = None
        t_prev = v
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
                tmp_cost = instance.cost(t)
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

def determine_customers(instance, customers, ratio):
    if not customers:
        return None
    customer = max(customers, key = lambda k: ratio[k])
    time = instance.earliest_starttime(customer)
    customers = filter(lambda k: instance.earliest_starttime(k) >= time-timedelta(hours=1) and instance.latest_starttime(k) <= time+timedelta(hours=1), customers)
    return sorted(customers, key = lambda k: ratio[k], reverse = True)[0:min(3, len(customers))]

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
    
    print 'Execute Mosel ...'
    mosel = config['mosel'] + 'MMILP_E.mos'
    i = subprocess.call(['mosel', mosel, 'INSTANCE=%s,SOLUTION=%s' % (instancename, solutionname)]) 
    print 'Mosel finished', i
    
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
    
    improved_cost = determine_improved_cost(solution)
    estimated_cost = determine_estimated_cost(solution.instance)
    ratio = dict([(c, improved_cost[c]/estimated_cost[solution.customers[c]]) for c in instance.customers])
    customers = set(filter(lambda k: ratio[k] >= 2, instance.customers))
    
    if args.statistics:
        print 'Total Reviewed Customers: %d' % len(customers)

    count = 1
    
    while(customers):
        
        print '%2d. Iteration' % count
        count += 1
        
        if count > 2:
            print 'Execute Mosel ...'
            mosel = config['mosel'] + 'MMILP_E.mos'
            i = subprocess.call(['mosel', mosel, 'INSTANCE=%s,SOLUTION=%s' % (instancename, solutionname)]) 
            print 'Mosel finished', i
            
            print 'Loading solution ...'
            solution = storage.load_solution_from_xpress(solutionfile, instance)
            print 'Solution successfully loaded from %s' % solutionfile
    
        critical_customers = determine_customers(instance, customers, ratio)
        print 'Critical Customers', [(c, round(ratio[c], 1)) for c in critical_customers]
        customers = customers - set(critical_customers)

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