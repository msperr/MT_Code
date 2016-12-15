from datetime import datetime, timedelta
import itertools
import os
import numpy
import util
import storage
from config import config
import subprocess
import taskgraph

if __name__ == '__main__2':
    
    a = numpy.int32(2147)
    b = numpy.int32(2148)
    print timedelta(seconds = a)
    print timedelta(seconds = int(b))
    print timedelta(seconds = b)

if __name__ == '__main__2':
    tmp = [1, 2, 3, 2]
    print list(set(i for i in tmp))
    
if __name__ == '__main__2':
    print util.timelist(datetime(2015, 10, 01, 01), datetime(2015, 10, 02, 01), length=4)
    
if __name__ == '__main__2':
    filename = config['data']['base'] + 'instance_2.json'
    instance = storage.load_instance_from_json(filename)
    storage.save_instance_to_json(filename, instance, compress=True)
    print 'Finished'

if __name__ == '__main__2':
    filename = config['data']['base'] + config['data']['instance']
    print os.path.basename(filename)

if __name__ == '__main__2':
    tmp = [True, False, True, False, False, True, True, False, False]
    tmp_iter = iter(tmp)
    for t in iter(tmp):
        print 'Item', t
        print 'Next', next(tmp_iter)

if __name__ == '__main__2':
    filename = config['data']['base'] + r'TU_C50\instance_small.split4.time.xpress.txt.gz'
    sol = storage.load_solution_from_xpress(filename)
    print sol.duties
    print sol.evaluate()
    cost, dist, time, used_vehicles, dist_customer, dist_deadhead = sol.evaluate_detailed()
    print 'Cost', cost, 'Distance', dist, 'Time', timedelta(seconds=time), 'Vehicles Used', used_vehicles, 'Customer Distance', dist_customer, 'Deadhead Distance', dist_deadhead
    print 'Customers', sol.customers
    #outputfile = config['data']['base'] + r'TU_C50\instance_small.savedsolution.txt'
    #storage.save_solution_to_xpress(outputfile, solution)
    #print 'Successfully saved solution to %s' % outputfile
    print 'Estimated Cost', ([sol.estimated_cost(c) for c in sol.customers.iterkeys()])

if __name__ == '__main__2':
    tmp = None
    tmplist = []
    tmplist.append(1)
    tmplist.append(tmp)
    print tmplist
    
if __name__ == '__main__2':
    fuel = [1, 2, 3]
    print fuel.pop(0)
    print fuel

if __name__ == '__main__2':
    mosel = r'..\Mosel\HSP.mos'
    print mosel
    subprocess.Popen(['mosel', mosel, 'mmxprs.XPRS_verbose=true'])
    #processes = [subprocess.Popen([osrm, osm, '-p', '%d' % port], cwd=os.path.dirname(osrm), stdout=subprocess.PIPE, stderr=subprocess.PIPE) for port in ports]
    
if __name__ == '__main__2':
    input1 = '2,3,4'
    input2 = '2'

if __name__ == '__main__2':
    instancefile = config['data']['base'] + r'TU_C50\instance.json.gz'
    solutionfile = config['data']['base'] + r'TU_C50\instance.split4.time.fuelsolution.txt.gz'
    improvedfile = config['data']['base'] + r'TU_C50\instance.split4.time.hsp.solution.txt.gz'
    graphfile = config['data']['base'] + r'TU_c50\instance.graph.json.gz'
    instance = storage.load_instance_from_json(instancefile)
    solution = storage.load_solution_from_xpress(solutionfile, instance)
    graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
    taskgraph.split_taskgraph_subproblem(instance, graph, solution, [0,5,9])
    
    improved = storage.load_partial_solution_from_xpress(improvedfile, solution, instance)

if __name__ == '__main__2':
    set1 = ['A', 'B', 'C', 'D']
    set2 = ['E', 'F']
    for i, j in enumerate(itertools.chain(set1, set2)):
        print i, j

if __name__ == '__main__':
    times = [1443670100000, 1443673487000, 1443670183000, 1443673846000, 1443671059000, 1443674285000]
    time2 = [1443670100000, 1443673487000]
    
    print [util.to_datetime(time) for time in times]
    print [util.to_datetime(time) for time in time2]
    