from argparse import ArgumentParser
from os import path
import subprocess
from datetime import timedelta

import storage
import entities
import taskgraph
from config import config
from util import Printer

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

def determine_customers(instance, customers, ratio, maxcustomers):
    if not customers:
        return None
    customer = max(customers, key = lambda k: ratio[k])
    time = instance.earliest_starttime(customer)
    customers = filter(lambda k: instance.earliest_starttime(k) >= time-timedelta(hours=1) and instance.latest_starttime(k) <= time+timedelta(hours=1), customers)
    if not customers:
        print '[WARN] No critical customers', customer, 'Start', instance.earliest_starttime(customer), 'Finish', instance.latest_starttime(customer)
    return sorted(customers, key = lambda k: ratio[k], reverse = True)[0:min(maxcustomers, len(customers))]

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('solution', type=str)
    parser.add_argument('-m', '--maxcustomers', type=int, default=5, dest='maxcustomers')
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    printer = Printer(verbose=args.verbose, statistics=args.statistics)
    compress = '' if args.compress else '.gz'
    solutionname = args.solution
    instancename = path.join(path.dirname(solutionname), path.basename(solutionname).split('.')[0])
    
    printer.write('Process started')

    instance = None
    printer.writeInfo('Loading instance ...')
    instancefile = config['data']['base'] + instancename
    if path.isfile(instancefile + '.json.gz'):
        instancefile += '.json.gz'
        instance = storage.load_instance_from_json(instancefile)
        printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    elif path.isfile(instancefile + '.json'):
        instancefile += '.json'
        instance = storage.load_instance_from_json(instancefile)
        printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    assert not instance is None
    
    printer.writeStat('Instance Basename: %s' % instance._basename)
    printer.writeStat('Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(instance.vehicles), len(instance._customers), len(instance._routes), len(instance._trips), len(instance._refuelpoints)))
    printer.writeStat('Start: %s, Finish: %s' % (instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), instance.finishtime.strftime('%Y-%m-%d %H:%M:%S')))
        
    graph = None
    printer.writeInfo('Loading task graph ...')
    graphfile = config['data']['base'] + instancename + '.graph'
    if path.isfile(graphfile + '.json.gz'):
        graphfile += '.json.gz'
        graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
        printer.writeInfo('Task graph successfully loaded from %s' % graphfile)
    elif path.isfile(graphfile + '.json'):
        graphfile += '.json'
        graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
        printer.writeInfo('Task graph successfully loaded from %s' % graphfile)
    assert not graph is None
    
    printer.writeInfo('Execute Mosel ...')
    mosel = config['mosel'] + 'MMILP_E.mos'
    i = subprocess.call(['mosel', mosel, 'INSTANCE=%s,SOLUTION=%s' % (instancename, solutionname)])
    if i != 0:
        raise RuntimeError('MMILP_E failed')
    printer.writeInfo('Mosel finished')
    
    solution = None
    printer.writeInfo('Loading solution ...')
    solutionfile = config['data']['base'] + args.solution + '.fuelsolution'
    if path.isfile(solutionfile + '.txt.gz'):
        solutionfile += '.txt.gz'
        solution = storage.load_solution_from_xpress(solutionfile, instance)
        printer.writeInfo('Solution successfully loaded from %s' % solutionfile)
    elif path.isfile(solutionfile + '.txt'):
        solutionfile += '.txt'
        solution = storage.load_solution_from_xpress(solutionfile, instance)
        printer.writeInfo('Solution successfully loaded from %s' % solutionfile)
    assert not solution is None

    evaluation = solution.evaluate_detailed()
    printer.writeStat('Solution Basename: %s' % solution._basename)
    printer.writeStat('Total Cost: %.1f, Duties: %d' % (evaluation[0], evaluation[3]))
    
    improved_cost = determine_improved_cost(solution)
    estimated_cost = determine_estimated_cost(solution.instance)
    ratio = dict([(c, improved_cost[c]/estimated_cost[solution.customers[c]]) for c in instance.customers])
    customers = set(filter(lambda k: ratio[k] >= 2, instance.customers))

    printer.writeStat('Total Reviewed Customers: %d' % len(customers))

    count = 1
    evaluate_cost = []
    hspfile = config['data']['base'] + solutionname + '.hsp.solution.txt%s' % compress
    outputfile = config['data']['base'] + args.solution + '.solution.txt%s' % compress
    
    while customers:
        
        printer.write('%2d. Iteration' % count)
        printer.writeStat('%d customers left' % len(customers))
        count += 1
        
        if count > 2:
            printer.writeInfo('Execute Mosel ...')
            mosel = config['mosel'] + 'MMILP_E.mos'
            i = subprocess.call(['mosel', mosel, 'INSTANCE=%s,SOLUTION=%s' % (instancename, solutionname)]) 
            if i != 0:
                raise RuntimeError('MMILP_E failed')
            printer.writeInfo('Mosel finished')
            
            printer.writeInfo('Loading solution ...')
            solution = storage.load_solution_from_xpress(solutionfile, instance)
            printer.writeInfo('Solution successfully loaded from %s' % solutionfile)
    
        critical_customers = determine_customers(instance, customers, ratio, args.maxcustomers)
        if not critical_customers:
            customer = max(customers, key = lambda k: ratio[k])
            customers.remove(customer)
            continue
        
        customers = customers - set(critical_customers)
        
        printer.writeStat('Reviewed Customers: %d, Critical Customers: %s' % (len(critical_customers), ', '.join('%d (%.1f)' % (c, ratio[c]) for c in critical_customers)))
        printer.writeStat('Start: %s, Finish: %s' % (min(instance.earliest_starttime(c) for c in critical_customers).strftime('%Y-%m-%d %H:%M:%S'), max(instance.latest_starttime(c) for c in critical_customers).strftime('%Y-%m-%d %H:%M:%S')))
    
        printer.writeInfo('Creating task graph for subproblem ...')
        graph_hsp, startpoints, endpoints, trips = taskgraph.split_taskgraph_subproblem(instance, graph, solution, critical_customers)
        printer.writeInfo('Task graph for subproblem successfully created')
    
        printer.writeStat('Trips: %s, Vehicles: %s, Startpoints: %s, Endpoints: %s' % (len(trips), len(startpoints&set(instance.vehicles)), len(startpoints&set(instance.trips)), len(endpoints)))
    
        xpressfile = config['data']['base'] + solutionname + '.hsp.txt%s' % compress
        printer.writeInfo('Exporting taskgraph for subproblem ...')
        taskgraph.save_subproblem_taskgraph_to_xpress(xpressfile, instance, graph_hsp, startpoints, endpoints, trips, critical_customers)
        printer.writeInfo('Task graph for subproblem successfully exported to %s' % xpressfile)
    
        printer.writeInfo('Executing Mosel ...')
        mosel = config['mosel'] + 'HSP.mos'
        i = subprocess.call(['mosel', mosel, 'INSTANCE=%s' % solutionname])
        if i != 0:
            printer.writeWarn('HSP failed')
            continue
        printer.writeInfo('Mosel finished')

        printer.writeInfo('Loading partial solution ...')
        new_solution = storage.load_partial_solution_from_xpress(hspfile, solution, instance, endpoints)
        printer.writeInfo('Partial Solution successfully loaded from %s' % hspfile)
            
        evaluation = new_solution.evaluate_detailed()
        evaluate_cost.append((evaluation[0], evaluation[3]))
        printer.writeStat('Solution Basename: %s' % new_solution._basename)
        printer.writeStat('Total Cost: %.1f, Duties: %d' % (evaluation[0], evaluation[3]))
    
        printer.writeInfo('Exporting solution ...')
        storage.save_solution_to_xpress(outputfile, new_solution)
        printer.writeInfo('Successfully exported solution to %s' % outputfile)
    
    for i, (cost, cars) in enumerate(evaluate_cost):
        print '%2d: Cars: %2d, Cost: %1.f' % (i, cost, cars)
        
    printer.write('Process finished')