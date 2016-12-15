from argparse import ArgumentParser
from datetime import datetime, timedelta
import os
import random
from itertools import count

import progressbar

import storage
import entities
import util
from otp import Otp
from config import config
from instance import Instance

def noise(time):
    shift = random.uniform(-1800, 1800)
    return time + timedelta(seconds = shift)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-o', '--fileoutput', type=str, dest='fileoutput')
    parser.add_argument('-c', '--customers', type=int, dest='customer_number')
    parser.add_argument('-v', '--vehicles', type=int, dest='vehicle_number')
    parser.add_argument('--compress', action='store_true')
    parser.add_argument('--unit', action='store_true')
    parser.add_argument('--statistics', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    frequency = [1]*24 if args.unit else [0.1, 0.1, 0.15, 0.2, 0.4, 0.65, 0.55, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 1, 1, 1, 0.8, 0.55, 0.45, 0.35, 0.2, 0.15, 0.1]
    printer = util.Printer(statistics=args.statistics, verbose=args.verbose)
    compress = '' if args.compress else '.gz'
    c_pub = 1.0/300.0
    c_walk = 1.0/180.0
    c_time = 1.0/180.0
    
    printer.write('Process started')
    
    time_step = timedelta(hours=1)
    trip_start = datetime(2015, 10, 01, 19)
    trip_finish = trip_start + time_step
    instance_start = datetime(2015, 10, 01, 03)
    instance_finish = instance_start + timedelta(days=1)
    
    instancefile = config['data']['base'] + config['data']['instance']
    outputname = args.fileoutput if args.fileoutput else 'T' + ('U' if args.unit else '') + ('_' if args.vehicle_number or args.customer_number else '') + ('V%d' % args.vehicle_number if args.vehicle_number else '') + ('C%d' % args.customer_number if args.customer_number else '') + r'\instance'
    outputfile = config['data']['base'] + '%s.json%s' % (outputname, compress) 
    
    if not os.path.exists(os.path.dirname(outputfile)):
        os.makedirs(os.path.dirname(outputfile))
        
    printer.writeInfo('Loading instance ...')    
    instance = storage.load_instance_from_json(instancefile)
    printer.writeInfo('Instance successfully loaded from %s' % instancefile)
    
    location_id = instance.trips[0].location_id
    servicedrive = instance.trips[0].servicedrive
    
    original_trips = filter(lambda k: trip_start <= k.start_time < trip_finish, instance.trips)
    
    customer_number = args.customer_number / sum(frequency) if args.customer_number else len(original_trips)
    vehicle_number = min(args.vehicle_number, len(instance.vertices)) if args.vehicle_number else len(instance.vehicles)
    
    if max(frequency) * customer_number < 1:
        printer.writeWarn('Customer number is too small')
        customer_number = 2*max(frequency)
    
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

    printer.writeInfo('Creating trips with OTP ...')

    otp = Otp()
    customers = {}
    routes = {}
    routecost = {}
    customer_index = 0
    route_index = len(prop_customers)
    trip_index = 1
    
    progress = progressbar.ProgressBar(maxval=len(prop_customers), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
    progresscount = count(1)
    
    for tmp_trip in prop_customers:
        
        station_result = otp.route(tmp_trip['finish_loc'], tmp_trip['start_loc'], tmp_trip['start_time'] + timedelta(hours=2))
        
        if not station_result:
            progress.update(progresscount.next())
            continue
        
        customer_routes = []
        
        stations = set(entities.Point(
            lon = leg['from']['lon'],
            lat = leg['from']['lat']
        ) for route in station_result for leg in route['legs'] if leg['mode'] in {'BUS', 'SUBWAY', 'RAIL'})
        
        for station in stations:
            result = otp.route(tmp_trip['start_loc'], station, noise(tmp_trip['start_time'])+timedelta(hours=2))
            if not result:
                continue
            for route in result:
                car_result = otp.route(station, tmp_trip['finish_loc'], util.to_datetime(route['endTime']), modes=['CAR', 'WALK'], numItineraries = 1)
                if not car_result:
                    continue
                route_trips = [entities.Trip(
                    vehicle_vin = 'T%05d' % (trip_index + leg_count),
                    start_time = util.to_datetime(leg['from']['departure']),
                    finish_time = util.to_datetime(leg['to']['arrival']),
                    start_longitude = leg['from']['lon'],
                    start_latitude = leg['from']['lat'],
                    finish_longitude = leg['to']['lon'],
                    finish_latitude = leg['to']['lat'],
                    distance = leg['distance']
                ) for leg_count, leg in enumerate(leg for leg in route['legs'] if leg['mode'] == 'CAR')]
                route_trips.extend([entities.Trip(
                    vehicle_vin = 'T%05d' % (trip_index + len(route_trips) + leg_count),
                    start_time = util.to_datetime(route['endTime'] + leg['from']['departure'] - car_result[0]['startTime']),
                    finish_time = util.to_datetime(route['endTime'] + leg['to']['arrival'] - car_result[0]['startTime']),
                    start_longitude = leg['from']['lon'],
                    start_latitude = leg['from']['lat'],
                    finish_longitude = leg['to']['lon'],
                    finish_latitude = leg['to']['lat'],
                    distance = leg['distance']
                ) for leg_count, leg in enumerate(leg for leg in car_result[0]['legs'] if leg['mode'] == 'CAR')])
                if route_trips:
                    trip_index += len(route_trips)
                    cost = c_pub * (route['transitTime'] + car_result[0]['transitTime']) + c_walk * (route['walkTime'] + car_result[0]['walkTime']) + c_time * (route['duration'] + car_result[0]['duration'])
                    routes.update([(route_index, route_trips)])
                    routecost.update([(route_index, cost)])
                    customer_routes.append(route_index)
                    route_index += 1
            
        for route in station_result:
            route_trips = [entities.Trip(
                vehicle_vin = 'T%05d' % (trip_index + leg_count),
                start_time = util.to_datetime(leg['from']['departure']),
                finish_time = util.to_datetime(leg['to']['arrival']),
                start_longitude = leg['from']['lon'],
                start_latitude = leg['from']['lat'],
                finish_longitude = leg['to']['lon'],
                finish_latitude = leg['to']['lat'],
                distance = leg['distance'],
            ) for (leg_count, leg) in enumerate([leg for leg in route['legs'] if leg['mode'] == 'CAR'])]
            if route_trips:
                trip_index += len(route_trips)
                cost = c_pub * route['transitTime'] + c_walk * route['walkTime'] + c_time * route['duration']
                routes.update([(route_index, route_trips)])
                routecost.update(dict([(route_index, cost)]))
                customer_routes.append(route_index)
                route_index += 1
        
        if customer_routes:
            customers.update([(customer_index, customer_routes)])
            customer_index += 1
        progress.update(progresscount.next())
    
    progress.finish()
    
    new_instance = Instance(vehicles, customers, routes, routecost, instance.refuelpoints, instance._fuelpermeter, instance._refuelpersecond, instance._costpermeter, instance._costpercar)
    new_instance._basename = outputname
    
    printer.writeInfo('New instance created')

    printer.writeStat('Name: %s' % new_instance._basename)
    printer.writeStat('Vehicles: %d, Customers: %d, Routes: %d, Trips: %d, Refuelpoints: %d' % (len(new_instance.vehicles), len(new_instance._customers), len(new_instance._routes), len(new_instance._trips), len(new_instance._refuelpoints)))
    printer.writeStat('Start: %s, Finish: %s' % (new_instance.starttime.strftime('%Y-%m-%d %H:%M:%S'), new_instance.finishtime.strftime('%Y-%m-%d %H:%M:%S')))

    storage.save_instance_to_json(outputfile, new_instance)
    printer.writeInfo('Successfully saved instance to %s' % outputfile)
    
    printer.write('Process finished')