from argparse import ArgumentParser
from datetime import timedelta
import random
import os

import storage
import taskgraph
import osrm
import util
from config import config

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('-i', type=str, dest='instance')
    parser.add_argument('-g', type=str, dest='graph')
    parser.add_argument('-l', type=int, dest='splitlength')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('-r', type=int, dest='restriction')
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--customer', action='store_true')
    parser.add_argument('--time', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
    
    compress = '.gz' if args.compress else ''
   
    print '[INFO] Process started'
    
    #Warnings
    if args.export and not (args.instance or args.fileoutput):
        print '[WARN] Base instance will be overwritten'
    if args.fileoutput and not args.export:
        print '[WARN] Results will not be saved'
    if (args.customer or args.time) and not args.splitlength:
        print '[WARN] No splitpoints available'
    if args.splitlength and not (args.customer or args.time):
        print '[WARN] Splitting type is not specified'
    
    filename = config['data']['base'] + (args.instance if args.instance else config['data']['instance'])
    basename = (config['data']['base'] + args.fileoutput) if args.fileoutput else filename.split('.json')[0]
    instance = storage.load_instance_from_json(filename)
    #instance = storage.load_instance_from_json_customer(filename)
    print 'Instance successfully loaded from %s' % filename
    
    if args.restriction:
        subsets = {}
        subsets['refuelpoints'] = random.sample(instance._refuelpoints, args.restriction)
        subsets['vehicles'] = random.sample(instance._vehicles, args.restriction)
        subsets['customers'] = random.sample(instance._customers, args.restriction)
        if subsets:
            instance = instance.subinstance(**subsets)
    
    if instance._time is None or instance._dist is None:
        extendedvertices = instance.extendedvertices
        print 'Get %d x %d matrix ...' %(len(extendedvertices), len(extendedvertices))
        with osrm.osrm_parallel() as router:
            instance._time, instance._dist = router.matrix(extendedvertices, extendedvertices)
        print 'Matrix successfully loaded'
    
    if args.statistics:
        print 'Name: ', instance._basename
        print 'Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(instance.vehicles), len(instance._customers), len(instance._routes), len(instance._trips), len(instance._refuelpoints))
        print 'Start: %s, Finish: %s' % (instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), instance.finishtime.strftime('%Y-%m-%d %H:%M:%S'))

    if args.export:
        filename = '%s.json%s' % (basename, compress)
        print 'Saving instance ...'
        storage.save_instance_to_json(filename, instance, compress=None)
        print 'Instance successfully saved to %s' % filename
            
    if args.graph:
        filename = config['data']['base'] + args.graph
        G = taskgraph.load_taskgraph_from_json(filename, instance.dictionary)
        print 'Task graph successfully loaded from %s' % filename
        
        if args.statistics:
            print 'Nodes: %d, Edges: %d' % (len(G.nodes()), len(G.edges()))
    
    else:
        print 'Creating task graph ...'
        G = taskgraph.create_taskgraph(instance)
        print 'Task graph successfully created'
    
        if args.statistics:
            print 'Nodes: %d, Edges: %d' % (len(G.nodes()), len(G.edges()))
    
        if args.export:
            xpressfile = '%s.txt%s' % (basename, compress)
            print 'Exporting task graph ...'
            taskgraph.save_taskgraph_to_xpress(xpressfile, instance, G)
            print 'Task graph successfully exported to %s' % xpressfile
            filename = '%s.graph.json%s' % (basename, compress)
            print 'Saving task graph ...'
            taskgraph.save_taskgraph_to_json(G, filename)
            print 'Task graph successfully saved to %s' % filename

    split = []  
    if args.splitlength:
        startsplit = instance.starttime
        endsplit = instance.starttime + timedelta(days=1)
        split = util.timelist(startsplit, endsplit, length = args.splitlength)
        split.remove(startsplit)
        
        if args.statistics:
            print 'Splittings:', map(lambda k: k.strftime('%H:%M:%S'), split)
    
    if args.customer and split:
        print 'Splitting task graph according to customers ...'
        G, splitpoint_list, trip_list, customer_list = taskgraph.split_taskgraph_customer(instance, G, split)
        splitpoints = [splitpoint for tmp_list in splitpoint_list for splitpoint in tmp_list]
        
        if args.statistics:
            print 'Splitpoints: %d' % len(splitpoints)
            for (index, timepoint) in enumerate(split):
                print '%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (index+1, timepoint, len(customer_list[index]), len(trip_list[index]), len(splitpoint_list[index]))
            print '%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (len(split)+1, endsplit, len(customer_list[-1]), len(trip_list[-1]), len(splitpoint_list[-1]))
        
        if args.export:
            xpressfile = '%s.split%d.customer.txt%s' % (basename, len(split)+1, compress)
            print 'Exporting split task graph ...'
            taskgraph.save_split_taskgraph_to_xpress(xpressfile, instance, G, splitpoint_list, trip_list, customer_list)
            print 'Split task graph successfully exported to %s' % xpressfile
            filename = '%s.split%d.customer.graph.json%s' % (basename, len(split)+1, compress)
            print 'Saving split task graph ...'
            taskgraph.save_taskgraph_to_json(G, filename)
            print 'Split task graph successfully saved to %s' % filename
            
    if args.time and split:
        print 'Splitting task graph according to time ...'
        G, splitpoint_list, trip_list, customer_list, route_list = taskgraph.split_taskgraph_time(instance, G, split)
        splitpoints = [splitpoint for tmp_list in splitpoint_list for splitpoint in tmp_list]
        
        if args.statistics:
            print 'Splitpoints: %d' % len(splitpoints)
            for (index, timepoint) in enumerate(split):
                print '%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (index+1, timepoint, len(customer_list[index]), len(trip_list[index]), len(splitpoint_list[index]))
            print '%2d. Time: %s, Number of Customers: %2d, Number of Trips: %3d, Number of Splitpoints: %3d' % (len(split)+1, endsplit, len(customer_list[-1]), len(trip_list[-1]), len(splitpoint_list[-1]))
        
        if args.export:
            xpressfile = '%s.split%d.time.txt%s' % (basename, len(split)+1, compress)
            print 'Exporting split task graph ...'
            taskgraph.save_split_taskgraph_to_xpress(xpressfile, instance, G, splitpoint_list, trip_list, customer_list, route_list=route_list)
            print 'Split task graph successfully exported to %s' % xpressfile
            filename = '%s.split%d.time.graph.json%s' % (basename, len(split)+1, compress)
            print 'Saving split task graph ...'
            taskgraph.save_taskgraph_to_json(G, filename)
            print 'Split task graph successfully saved to %s' % filename

    print '[INFO] Process finished'