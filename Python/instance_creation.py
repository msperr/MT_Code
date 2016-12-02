from argparse import ArgumentParser
from datetime import datetime, timedelta
import random
from itertools import count

import progressbar

import storage
import entities
import util
from otp import Otp
from config import config
from instance import Instance

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-i', type=str, dest='instance')
    parser.add_argument('-o', type=str, dest='fileoutput')
    parser.add_argument('-c', type=int, dest='customer_number')
    parser.add_argument('-v', type=int, dest='vehicle_number')
    parser.add_argument('--statistics', action='store_true')
    args = parser.parse_args()
    
    print '[INFO] Process started'
    
    frequency = [0.1, 0.1, 0.15, 0.2, 0.4, 0.65, 0.55, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 1, 1, 1, 0.8, 0.55, 0.45, 0.35, 0.2, 0.15, 0.1]
    
    time_step = timedelta(seconds=3600)
    trip_start = datetime(2015, 10, 01, 19)
    trip_finish = trip_start + time_step
    instance_start = datetime(2015, 10, 01, 03)
    instance_finish = instance_start + timedelta(days=1)
    
    filename = config['data']['base'] + (args.instance if args.instance else config['data']['instance'])
    instance = storage.load_instance_from_json(filename)
    print 'Instance successfully loaded from %s' % filename
    
    location_id = instance._trips[0].location_id
    servicedrive = instance._trips[0].servicedrive
    
    original_trips = [trip for trip in instance._trips if (trip_start <= trip.start_time and trip.start_time < trip_finish)]
    
    customer_number = args.customer_number / sum(frequency) if args.customer_number else len(original_trips)
    vehicle_number = args.vehicle_number if args.vehicle_number else len(instance._vehicles)
    
    original_start = map(lambda k: k.start_loc, original_trips)
    original_finish = map(lambda k: k.finish_loc, original_trips)
    
    prop_customers = []
    
    for (time_index, timepoint) in enumerate(util.timerange(instance_start, instance_finish, time_step)):
        tmp_trips = random.sample(original_trips, int(frequency[time_index] * customer_number))
        finish_locs = random.sample([trip.finish_loc for trip in original_trips], len(tmp_trips))
        random.shuffle(finish_locs)
        
        prop_customers.extend([{
            'start_time': (trip.start_time - trip_start) + timepoint,
            'start_loc': trip.start_loc,
            'finish_loc': finish_locs[trip_index],
        } for (trip_index, trip) in enumerate(tmp_trips)])
    
    if args.vehicle_number:
        if args.vehicle_number <= len(instance.vehicles):
            vehicle_locs = random.sample(map(lambda k: k.start_loc, instance.vehicles), args.vehicle_number)
        else:
            vehicle_locs = map(lambda k: k.start_loc, instance.vehicles) + random.sample(map(lambda k: k.finish_loc, instance.trips), args.vehicle_number - len(instance.vehicles))
    else:
        vehicle_locs = map(lambda k: k.start_loc, instance.vehicles)
    
    vehicles = ([entities.Vehicle(
        vehicle_id = 'V%04d' % vehicle_index,
        start_time = instance_start,
        start_loc = vehicle_loc
    ) for (vehicle_index, vehicle_loc) in enumerate(vehicle_locs)])

    print 'Creating trips with OTP ...'

    otp = Otp()
    customers = {}
    routes = {}
    customer_index = 0
    route_index = len(prop_customers)
    trip_index = 0
    
    progress = progressbar.ProgressBar(maxval=len(prop_customers), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
    progresscount = count(1)
    
    for tmp_trip in prop_customers:
        result = otp.route(tmp_trip['start_loc'], tmp_trip['finish_loc'], tmp_trip['start_time'] + timedelta(seconds=7200))
        
        if not result:
            progress.update(progresscount.next())
            continue
        
        customer_routes = []
        for route in result:
            route_trips = [entities.Trip(
                location_id = location_id,
                vehicle_vin = 'T%05d' % (trip_index + leg_count),
                start_time = util.to_datetime(leg['from']['departure']),
                finish_time = util.to_datetime(leg['to']['arrival']),
                start_longitude = leg['from']['lon'],
                start_latitude = leg['from']['lat'],
                finish_longitude = leg['to']['lon'],
                finish_latitude = leg['to']['lat'],
                distance = leg['distance'],
                servicedrive = servicedrive
            ) for (leg_count, leg) in enumerate([leg for leg in route['legs'] if leg['mode'] == 'CAR'])]
            trip_index += len(route_trips)
            routes.update(dict([(route_index, route_trips)]))
            customer_routes.append(route_index)
            route_index += 1
        customers.update(dict([(customer_index, customer_routes)]))
        customer_index += 1
        progress.update(progresscount.next())
    
    progress.finish()
    
    new_instance = Instance(vehicles, customers, routes, instance._refuelpoints, instance._fuelpermeter, instance._refuelpersecond, instance._costpermeter, instance._costpercar)
    
    basename = config['data']['base'] + (args.fileoutput if args.fileoutput else args.instance.split('.json')[0])
    new_instance._basename = basename
    
    print 'New instance created'
    
    if args.statistics:
        print 'Name: ', new_instance._basename
        print 'Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(new_instance.vehicles), len(new_instance._customers), len(new_instance._routes), len(new_instance._trips), len(new_instance._refuelpoints))
        print 'Start: %s, Finish: %s' % (new_instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), new_instance.finishtime.strftime('%Y-%m-%d %H:%M:%S'))
    
    filename = '%s.json' % basename
    storage.save_instance_to_json(filename, new_instance)
    print 'Successfully saved instance to %s' % filename
    
    print '[INFO] Process finished'