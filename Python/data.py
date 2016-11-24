from argparse import ArgumentParser
from datetime import datetime, timedelta
import random

import storage
import taskgraph

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('-i', type=str, dest='instance')
    parser.add_argument('-l', type=str, dest='splitlength')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('-r', type=float, dest='restriction')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
   
    print '[INFO] Process started'
    
    if args.instance:
        instance = storage.load_instance_from_json(args.instance)
        #instance = storage.load_instance_from_json_deprecated(args.instance)
        print 'Instance successfully loaded'
    elif args.fileoutput:
        filename = '%s.json' % args.fileoutput
        instance = storage.load_instance_from_json(filename)
        print 'Instance successfully loaded'
    
    if args.restriction:
        assert 0 <= args.restriction <= 1
        subsets = {}
        subsets['vehicles'] = random.sample(instance._vehicles, int(round(args.restriction * len(instance._vehicles))))
        subsets['customers'] = random.sample(instance._customers, int(round(args.restriction * len(instance._customers))))
        subsets['refuelpoints'] = random.sample(instance._refuelpoints, int(round(args.restriction * len(instance._refuelpoints))))
        if subsets:
            instance = instance.subinstance(**subsets)
    
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
            print 'Splittings:', map(lambda k: k.strftime('%Y-%m-%d %H:%M:%S'), split)
    
    if args.statistics:
        start = datetime.now()
        
    print 'Creating task graph ...'
    G = taskgraph.create_taskgraph(instance)
    
    print 'Task graph successfully created'
    
    if args.statistics:
        finish = datetime.now()
        print 'Time elapsed: %ds' % (finish - start).total_seconds()
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
        G, splitpoint_list, trip_list = taskgraph.split_taskgraph(instance, G, split)
        splitpoints = [splitpoint for tmp_list in splitpoint_list for splitpoint in tmp_list]
        
        if args.statistics:
            print 'Splitpoints: %d' % len(splitpoints)
            for (index, timepoint) in enumerate(split):
                print 'Time: %s, Number of Splitpoints: %d, Number of Trips: %d' % (timepoint, len(splitpoint_list[index]), len(trip_list[index]))
            print 'Time: %s, Number of Splitpoints: %d, Number of Trips: %d' % (instance.finishtime, len(splitpoint_list[-1]), len(trip_list[-1]))
        
        if args.fileoutput:
            xpressfile = '%s.split.txt' % args.fileoutput
            taskgraph.save_split_taskgraph_to_xpress(instance, G, splitpoint_list, trip_list, xpressfile)
            print 'Split task graph successfully exported to %s' % xpressfile
            filename = '%s.split.graph.json' % args.fileoutput
            taskgraph.save_taskgraph_to_json(G, filename)
            print 'Split task graph successfully saved to %s' % filename
    
    print '[INFO] Process finished'