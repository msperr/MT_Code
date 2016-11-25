from argparse import ArgumentParser
from datetime import datetime, timedelta
import random

import storage
import taskgraph
import osrm

# -l 2015-10-01_01:00:00,3600,2015-10-02_01:00:00

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('-i', type=str, dest='instance')
    parser.add_argument('-g', type=str, dest='graph')
    parser.add_argument('-l', type=str, dest='splitlength')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('-r', type=int, dest='restriction')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
   
    print '[INFO] Process started'
    
    if args.instance:
        instance = storage.load_instance_from_json(args.instance)
        print 'Instance successfully loaded'
    elif args.fileoutput:
        filename = '%s.json' % args.fileoutput
        instance = storage.load_instance_from_json(filename)
        print 'Instance successfully loaded'
    
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

    if args.fileoutput:    
        filename = '%s.json' % args.fileoutput
        storage.save_instance_to_json(filename, instance)
        print 'Instance successfully saved to %s' % filename
    
    split = []  
    if args.splitlength:
        splitlength_list = args.splitlength.split(',')
        startsplit = datetime.strptime(splitlength_list[0], '%Y-%m-%d_%H:%M:%S')
        endsplit = datetime.strptime(splitlength_list[2], '%Y-%m-%d_%H:%M:%S')
        splitlength = timedelta(seconds = int(splitlength_list[1]))
        
        while startsplit + splitlength < endsplit:
            startsplit += splitlength
            split.append(startsplit)
        
        if args.statistics:
            print 'Splittings:', map(lambda k: k.strftime('%H:%M:%S'), split)
            
    if args.graph:
        G = taskgraph.load_taskgraph_from_json(args.graph, instance.dictionary)
        print 'Task graph successfully loaded'
        
        if args.statistics:
            print 'Nodes: %d, Edges: %d' % (len(G.nodes()), len(G.edges()))
    
    else:
        print 'Creating task graph ...'
        G = taskgraph.create_taskgraph(instance)
        print 'Task graph successfully created'
    
        if args.statistics:
            print 'Nodes: %d, Edges: %d' % (len(G.nodes()), len(G.edges()))
    
        if args.fileoutput:
            xpressfile = '%s.txt' % args.fileoutput
            taskgraph.save_taskgraph_to_xpress(instance, G, xpressfile)
            print 'Task graph successfully exported to %s' % xpressfile
            filename = '%s.graph.json' % args.fileoutput
            taskgraph.save_taskgraph_to_json(G, filename)
            print 'Task graph successfully saved to %s' % filename
        
    if split:
        print 'Splitting task graph ...'
        G, splitpoint_list, trip_list, customer_list = taskgraph.split_taskgraph(instance, G, split)
        splitpoints = [splitpoint for tmp_list in splitpoint_list for splitpoint in tmp_list]
        
        if args.statistics:
            print 'Splitpoints: %d' % len(splitpoints)
            for (index, timepoint) in enumerate(split):
                print '%2d. Time: %s, Number of Customers: %d, Number of Trips: %d, Number of Splitpoints: %d' % (index+1, timepoint, len(customer_list[index]), len(trip_list[index]), len(splitpoint_list[index]))
            print '%2d. Time: %s, Number of Customers: %d, Number of Trips: %d, Number of Splitpoints: %d' % (len(split)+1, endsplit, len(customer_list[-1]), len(trip_list[-1]), len(splitpoint_list[-1]))
        
        if args.fileoutput:
            xpressfile = '%s.split.txt' % args.fileoutput
            taskgraph.save_split_taskgraph_to_xpress(instance, G, splitpoint_list, trip_list, customer_list, xpressfile)
            print 'Split task graph successfully exported to %s' % xpressfile
            filename = '%s.split.graph.json' % args.fileoutput
            taskgraph.save_taskgraph_to_json(G, filename)
            print 'Split task graph successfully saved to %s' % filename
    
    print '[INFO] Process finished'