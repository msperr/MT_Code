from argparse import ArgumentParser
from datetime import timedelta
import random
from os import path

import storage
import taskgraph
import osrm
import util
from config import config
import xpress

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('instance', type=str)
    parser.add_argument('-l', type=int, nargs='*', dest='splitlength')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('-r', type=int, dest='restriction')
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--customer', action='store_true')
    parser.add_argument('--time', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    printer = util.Printer(statistics = args.statistics, verbose = args.verbose)
    compress = '' if args.compress else '.gz'

    printer.write('Process started')
    
    instancename = args.instance
    
    instance = None 
    printer.writeInfo('Loading instance ...')
    instancefile = config['data']['base'] + instancename
    if path.isfile(instancefile + '.json.gz'):
        instancefile += '.json.gz'
        instance = storage.load_instance_from_json(instancefile)
        printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    if path.isfile(instancefile + '.json'):
        instancefile += '.json'
        instance = storage.load_instance_from_json(instancefile)
        printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    assert not instance is None
    
    assert len(set(xpress.xpress_index(vehicle) for vehicle in instance.vehicles)) == len(instance.vehicles)
    assert len(set(xpress.xpress_index(trip) for trip in instance.trips)) == len(instance.trips)
    
    export = False
    
    if args.fileoutput:
        export = True
        instancename = args.fileoutput
    
    if args.restriction:
        export = True
        subsets = {}
        subsets['refuelpoints'] = random.sample(instance._refuelpoints, args.restriction)
        subsets['vehicles'] = random.sample(instance._vehicles, args.restriction)
        subsets['customers'] = random.sample(instance._customers, args.restriction)
        if subsets:
            instance = instance.subinstance(**subsets)
    
    if instance._time is None or instance._dist is None:
        export = True
        extendedvertices = instance.extendedvertices
        printer.writeInfo('Getting %d x %d matrix ...' %(len(extendedvertices), len(extendedvertices)))
        with osrm.osrm_parallel() as router:
            instance._time, instance._dist = router.matrix(extendedvertices, extendedvertices)
        printer.writeInfo('Matrix successfully loaded')

    printer.writeStat('Name: %s' % instance._basename)
    printer.writeStat('Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(instance.vehicles), len(instance._customers), len(instance._routes), len(instance._trips), len(instance._refuelpoints)))
    printer.writeStat('Start: %s, Finish: %s' % (instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), instance.finishtime.strftime('%Y-%m-%d %H:%M:%S')))

    if export:
        instancefile = config['data']['base'] + instancename + '.json%s' % compress
        printer.writeInfo('Saving instance ...')
        storage.save_instance_to_json(instancefile, instance)
        printer.writeInfo('Instance successfully saved to %s' % instancefile)
    
    graph = None
    if not export:
        graphfile = config['data']['base'] + instancename + '.graph'
        if path.isfile(graphfile + '.json.gz'):
            printer.writeInfo('Loading task graph ...')
            graphfile += '.json.gz'
            graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
            printer.writeInfo('Task graph successfully loaded from %s' % graphfile)
        elif path.isfile(graphfile + '.json'):
            printer.writeInfo('Loading task graph ...')
            graphfile += '.json'
            graph = taskgraph.load_taskgraph_from_json(graphfile, instance.dictionary)
            printer.writeInfo('Task graph successfully loaded from %s' % graphfile)
    if graph is None:
        export = True
        printer.writeInfo('Creating task graph ...')
        graph = taskgraph.create_taskgraph(instance)
        printer.writeInfo('Task graph successfully created')

    printer.writeStat('Nodes: %d, Edges: %d' % (len(graph.nodes()), len(graph.edges())))
        
    if export:
        xpressfile = config['data']['base'] + instancename + '.txt%s' % compress
        printer.writeInfo('Exporting task graph ...')
        taskgraph.save_taskgraph_to_xpress(xpressfile, instance, graph)
        printer.writeInfo('Task graph successfully exported to %s' % xpressfile)
        graphfile = config['data']['base'] + instancename + '.graph.json%s' % compress
        printer.writeInfo('Saving task graph ...')
        taskgraph.save_taskgraph_to_json(graph, graphfile)
        printer.writeInfo('Task graph successfully saved to %s' % graphfile)

    startsplit = instance.starttime
    endsplit = instance.starttime + timedelta(days=1)
        
    for splitlength in args.splitlength if args.splitlength else []:
        split = util.timelist(startsplit, endsplit, length = splitlength)
        split.remove(startsplit)

        printer.writeStat('Splittings: %s' % ', '.join(map(lambda k: k.strftime('%H:%M'), split)))
    
        if args.customer and split:
            printer.writeInfo('Splitting task graph according to customers ...')
            graph_customer, splitpoint_list, trip_list, customer_list = taskgraph.split_taskgraph_customer(instance, graph, split)
            splitpoints = [splitpoint for tmp_list in splitpoint_list for splitpoint in tmp_list]

            printer.writeStat('Splitpoints: %d' % len(splitpoints))
            for (index, timepoint) in enumerate(split):
                printer.writeStat('%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (index+1, timepoint, len(customer_list[index]), len(trip_list[index]), len(splitpoint_list[index])))
            printer.writeStat('%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (len(split)+1, endsplit, len(customer_list[-1]), len(trip_list[-1]), len(splitpoint_list[-1])))

            xpressfile = config['data']['base'] + instancename + '.split%d.customer.txt%s' % (len(split)+1, compress)
            printer.writeInfo('Exporting split task graph ...')
            taskgraph.save_split_taskgraph_to_xpress(xpressfile, instance, graph_customer, splitpoint_list, trip_list, customer_list)
            printer.writeInfo('Split task graph successfully exported to %s' % xpressfile)
            
        if args.time and split:
            printer.writeInfo('Splitting task graph according to time ...')
            graph_time, splitpoint_list, trip_list, customer_list, route_list = taskgraph.split_taskgraph_time(instance, graph, split)
            splitpoints = [splitpoint for tmp_list in splitpoint_list for splitpoint in tmp_list]
        
            printer.writeStat('Splitpoints: %d' % len(splitpoints))
            for (index, timepoint) in enumerate(split):
                printer.writeStat('%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (index+1, timepoint, len(customer_list[index]), len(trip_list[index]), len(splitpoint_list[index])))
            printer.writeStat('%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (len(split)+1, endsplit, len(customer_list[-1]), len(trip_list[-1]), len(splitpoint_list[-1])))

            xpressfile = config['data']['base'] + instancename + '.split%d.time.txt%s' % (len(split)+1, compress)
            printer.writeInfo('Exporting split task graph ...')
            taskgraph.save_split_taskgraph_to_xpress(xpressfile, instance, graph_time, splitpoint_list, trip_list, customer_list, route_list=route_list)
            printer.writeInfo('Split task graph successfully exported to %s' % xpressfile)

    printer.write('Process finished')