from argparse import ArgumentParser
import random

import storage
import entities
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
    parser.add_argument('-s', type=str, dest='solution')
    parser.add_argument('-o', type=str, dest='fileoutput')
    args = parser.parse_args()
    
    solutionfile = config['data']['base'] + args.solution
    
    print 'Loading solution ...'
    solution = storage.load_solution_from_xpress(solutionfile)
    print 'Successfully loaded solution from %s' % solutionfile
    
    instance = solution.instance
    
    improved_cost = determine_improved_cost(solution)
    estimated_cost = determine_estimated_cost(solution.instance)
    evaluation = solution.evaluate_detailed()
    
    print 'Vehicles', evaluation[3], 'Trip Cost', round(evaluation[4]*instance._costpermeter, 1), 'Deadhead Cost', round(evaluation[5]*instance._costpermeter, 1), 'Route Cost', round(evaluation[6], 1)
    
    for c, route in solution.customers.iteritems():
        print 'Customer', '%3d'%c, 'Ratio', round(improved_cost[c]/estimated_cost[route], 2), 'Estimated Cost', [('%3d'%r, round(estimated_cost[r], 1)) for r in solution.instance._customers.get(c)], 'Route', route, 'Improved Cost', round(improved_cost[c], 1)
        
    # determine critical customer(s)
    # customers with high ratio and similar time windows
    # consider if alternatives are available
    # high ratio with small estimated cost does not give much saving
    
    critical_customers = random.sample(solution.customers.keys(), 5)
    
    # export graph for HSP(c)
        
    print '[INFO] Process finished'