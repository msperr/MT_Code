from argparse import ArgumentParser
from datetime import datetime, timedelta
import random

import storage
import taskgraph

if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument('-i', type=str, dest='instance')
    parser.add_argument('-l', type=str, dest='splitlength')
    parser.add_argument('-p', type=int, dest='probability')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('--random', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
   
    print '[INFO] Process started'
    
    if args.instance:
        instance = storage.load_instance_from_json(args.instance)
        print 'Instance successfully loaded'
    
    if args.random:
        subsets = {}
        subsets['refuelpoints'] = random.sample(instance._refuelpoints, args.probability)
        subsets['vehicles'] = random.sample(instance._vehicles, args.probability)
        subsets['customers'] = random.sample(instance._customers, args.probability)
        if subsets:
            instance = instance.subinstance(**subsets)

    if args.statistics:
        print 'Name: ', instance._basename
        print 'Vehicles: %d' % len(instance.vehicles)
        print 'Customers: %d'% len(instance._customers)
        print 'Routes: %d' % len(instance._routes)
        print 'Trips: %d' % len(instance._trips)
        print 'Refuelpoints: %d' % len(instance._refuelpoints)
        print 'Start: %s, Finish: %s' % (min(map((lambda t: t.start_time), instance._trips)).strftime('%Y-%m-%d %H:%M:%S'), max(map((lambda t: t.finish_time), instance._trips)).strftime('%Y-%m-%d %H:%M:%S'))

    if args.fileoutput:    
        filename = '%s.json' % args.fileoutput
        storage.save_instance_to_json(filename, instance)
        print 'Instance successfully saved to %s' % filename
        
    if args.splitlength:
        splitlength_list = args.splitlength.split(',')
        startsplit = datetime.strptime(splitlength_list[0], '%Y-%m-%d_%H:%M:%S')
        endsplit = datetime.strptime(splitlength_list[2], '%Y-%m-%d_%H:%M:%S')
        splitlength = timedelta(seconds = int(splitlength_list[1]))
        split = []

        while startsplit + splitlength < endsplit:
            startsplit += splitlength
            split.append(startsplit)
        print map(lambda k: k.strftime('%Y-%m-%d %H:%M:%S'), split)
    
    print 'Creating Task Graph ...'
    G = taskgraph.create_taskgraph(instance)
    
    print '[INFO] Process finished'