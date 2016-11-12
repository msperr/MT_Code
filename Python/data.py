from argparse import ArgumentParser
import json

import numpy

import storage
from entities import Point, Trip

if __name__ == '__main__':
   
    print 'start'
    
    instance = storage.read_instance_from_json_customer(r'..\data\customers.json')
    
    print 'Instance loaded with %d vehicles, %d customers, %d routes and %d refuelpoints' % (len(instance._vehicles), len(instance._customers), len(instance._routes), len(instance._refuelpoints))
        
    for customer in instance._customers:
        trips_c = [trip for trip in instance._trips if (instance.customer(trip) == customer)]
        for trip1 in trips_c:
            for trip2 in [trip for trip in trips_c if (trip1 != trip)]:
                if trip1.start_loc.__eq__(trip2.start_loc) & trip1.finish_loc.__eq__(trip2.finish_loc):
                    print '%s: %s, %s' %(customer, trip1, trip2)
    
    print 'finished'