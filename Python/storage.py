import os
import json
import random
from datetime import datetime, timedelta
import csv

import numpy

import entities
from instance import instance
from distance_matrix import DistanceMatrix
from collections import OrderedDict

def read_vehicles_from_json(filename, fuel=False):
    with open(filename) as f:    
        data = json.load(f)
        if fuel:
            return [ entities.Vehicle(
                id=vehicle['id'],
                longitude=vehicle['longitude'],
                latitude=vehicle['latitude'],
                start_time=datetime.strptime(vehicle['start_time'], '%Y-%m-%d %H:%M:%S'),
                fuel=vehicle['fuellevel']
            ) for vehicle in data['vehicles'] ]
        else:
            return [ entities.Vehicle(
                id=vehicle['id'],
                longitude=vehicle['longitude'],
                latitude=vehicle['latitude'],
                start_time=datetime.strptime(vehicle['start_time'], '%Y-%m-%d %H:%M:%S')
            ) for vehicle in data['vehicles'] ]

def save_vehicles_to_json(vehicles, filename, fuel=False):
    if fuel:
        data = {
            'vehicles': [{
                'id': vehicle.id,
                'longitude': vehicle.start_loc.lon,
                'latitude': vehicle.start_loc.lat,
                'start_time': str(vehicle.start_time),
                'fuel': vehicle.fuel
            } for vehicle in vehicles]
        }
    else:
        data = {
            'vehicles': [{
                'id': vehicle.id,
                'longitude': vehicle.start_loc.lon,
                'latitude': vehicle.start_loc.lat,
                'start_time': str(vehicle.start_time),
            } for vehicle in vehicles],
        }    
    with open(filename,'w') as f:
        json.dump(data, f)

def save_refuelpoints_to_json(refuelpoints, filename):
    data = {
        'refuelpoints': [{
            'id': refuelpoint.id,
            'longitude': refuelpoint.lon,
            'latitude': refuelpoint.lat
        } for refuelpoint in refuelpoints]
    }
    with open(filename,'w') as f:
        json.dump(data, f)
 
def save_instance_to_json(filename, vehicles, refuelpoints, customers, fuelpermeter, refuelpersecond, matrices=False, spots=[], splitpoints=[], fuel=False):    
    trips = [trip for trip in [route.trips for route in [customer.routes for customer in customers]]];
    indices = vehicles + refuelpoints + trips + spots
    if fuel:        
        data = {        
            'vehicles': [{
                'id': vehicle.id,
                'longitude': vehicle.start_loc.lon,
                'latitude': vehicle.start_loc.lat,
                'start_time': str(vehicle.start_time),
                'fuel': vehicle.fuel
            } for vehicle in vehicles],       
            'refuelpoints': [{
                'id': refuelpoint.id,
                'longitude': refuelpoint.lon,
                'latitude': refuelpoint.lat
            } for refuelpoint in refuelpoints],        
            'customers': [{
                'id': customer.id,
                'routes': [{
                    'trips': [{
                        'location_id': trip.location_id,
                        'vehicle_vin': trip.vehicle_vin,
                        'start_time': str(trip.start_time),
                        'start_longitude': trip.start_loc.lon,
                        'start_latitude': trip.start_loc.lat,
                        'finish_longitude': trip.finish_loc.lon,
                        'finish_latitude': trip.finish_loc.lat,
                        'duration': trip.duration.total_seconds(),
                        'distance': trip.distance,
                        'servicedrive': trip.servicedrive
                    } for trip in route.trips]
                } for route in customer.route]
            } for customer in customers],
            'spots': [{
                'id': spot.id,
                'longitude': spot.start_loc.lon,
                'latitude': spot.start_loc.lat,
                'start_time': str(spot.start_time)
            } for spot in spots],                     
            'splitpoints': [{
                'id': splitpoint.id,
                'time': str(splitpoint.time),
                'weight': splitpoint.weight,
                'fuel': spot.fuel
            } for splitpoint in splitpoints],
            'fuelpermeter': fuelpermeter,
            'refuelpersecond': refuelpersecond
        }
    else:
        data = {
            'vehicles': [{
                'id': vehicle.id,
                'longitude': vehicle.start_loc.lon,
                'latitude': vehicle.start_loc.lat,
                'start_time': str(vehicle.start_time),
            } for vehicle in vehicles],        
            'refuelpoints': [{
                'id': refuelpoint.id,
                'longitude': refuelpoint.lon,
                'latitude': refuelpoint.lat
            } for refuelpoint in refuelpoints],        
            'customers': [{
                'id': customer.id,
                'routes': [{
                    'trips': [{
                        'location_id': trip.location_id,
                        'vehicle_vin': trip.vehicle_vin,
                        'start_time': str(trip.start_time),
                        'start_longitude': trip.start_loc.lon,
                        'start_latitude': trip.start_loc.lat,
                        'finish_longitude': trip.finish_loc.lon,
                        'finish_latitude': trip.finish_loc.lat,
                        'duration': trip.duration.total_seconds(),
                        'distance': trip.distance,
                        'servicedrive': trip.servicedrive
                    } for trip in route.trips]
                } for route in customer.route]
            } for customer in customers],
            'spots': [{
                'id': spot.id,
                'longitude': spot.start_loc.lon,
                'latitude': spot.start_loc.lat,
                'start_time': str(spot.start_time),
            } for spot in spots],
            'fuelpermeter': fuelpermeter,
            'refuelpersecond': refuelpersecond
        }
    if matrices:
        data.update({
            'time': DistanceMatrix.time(indices, indices),
            'dist': DistanceMatrix.dist(indices, indices)
        })
    with open(filename, 'w') as f:
        json.dump(data, f)

###############################################################################

###############################################################################

def read_trips_from_csv_file(filename):
    with open(filename, 'rb') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(csvreader, None)
        return [ entities.Trip(
            location_id = int(row[0]),
            vehicle_vin = row[1],
            start_time = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S'),
            start_longitude = float(row[3]),
            start_latitude = float(row[4]),
            finish_longitude = float(row[5]),
            finish_latitude = float(row[6]),
            duration = int(row[7]),
            distance = int(row[8]),
            servicedrive = int(row[9])
        ) for row in csvreader ]

def read_trips_from_json_file(filename):
    with open(filename) as f:
        data = json.load(f)
        return [entities.Trip(
            location_id = trip['location_id'],
            vehicle_vin = trip['vehicle_vin'],
            start_time = datetime.strptime(trip['start_time'], '%Y-%m-%d %H:%M:%S'),
            start_longitude = trip['start_longitude'],
            start_latitude = trip['start_latitude'],
            finish_longitude = trip['finish_longitude'],
            finish_latitude = trip['finish_latitude'],
            duration = timedelta(seconds=trip['duration']),
            distance = trip['distance'],
            servicedrive = trip['servicedrive']
        ) for trip in data['trips'] ]

def save_trips_to_json_file(trips, filename):
    data = {
        'trips': [{
            'location_id': trip.location_id,
            'vehicle_vin': trip.vehicle_vin,
            'start_time': str(trip.start_time),
            'start_longitude': trip.start_loc.lon,
            'start_latitude': trip.start_loc.lat,
            'finish_longitude': trip.finish_loc.lon,
            'finish_latitude': trip.finish_loc.lat,
            'duration': trip.duration.total_seconds(),
            'distance': trip.distance,
            'servicedrive': trip.servicedrive
        } for trip in trips]
    }

    with open(filename,'w') as f:
        json.dump(data, f)

def reduce_trips_randomly(probability, objectlist):
    return [obj for obj in objectlist if random.random() <= probability]

def reduce_vehicles_randomly_from_trips(probability,trips):
    vehicle_ids = set(t.vehicle_vin for t in trips)
    vehicles = []
    for vin in vehicle_ids:
        rand = random.random()
        if rand <= probability:
            vehicles.append(entities.Vehicle(
                id=vin, 
                start_loc=max([t for t in trips if t.vehicle_vin == vin], key=lambda t: t.start_time + t.duration).finish_loc,
                start_time=max([t.start_time + t.duration for t in trips if t.vehicle_vin == vin])
            ))
    return vehicles

def save_spots_as_json_file(spots,filename):
    dictionary = dict()
    dictionary['spots']=[dict([('id',spot.id),('longitude',spot.start_loc.lon),('latitude',spot.start_loc.lat),('start_time',str(spot.start_time)),('fuellevel',spot.fuel)]) for spot in spots]
    f = open(filename,'w')
    json.dump(dictionary,f)
    f.close()

def read_spots_from_json_file(filename):
    with open(filename) as f:    
        data = json.load(f)
        return [ entities.Spot(
            id=spot['id'],
            longitude=spot['longitude'], 
            latitude=spot['latitude'],
            start_time=datetime.strptime(spot['start_time'], '%Y-%m-%d %H:%M:%S'),
            fuel = spot['fuellevel']
        ) for spot in data['spots'] ]

###############################################################################
# deprecated methods
###############################################################################

def read_refuelpoints_from_json_deprecated(filename):
    with open(filename) as f:    
        data = json.load(f)
        return [ entities.RefuelPoint(
            station['id']['id'], 
            station['coordinates']['longitude'], 
            station['coordinates']['latitude']
        ) for station in data['chargeStations'] ]

def read_instance_from_json_knoll(filename, fuel=False):
    
    with open(filename) as f:
        data = json.load(f)

    refuelpoints = [ entities.RefuelPoint(
        station['id']['id'], 
        station['coordinates']['longitude'], 
        station['coordinates']['latitude']
    ) for station in data['chargeStations'] ]

    trips = [ entities.Trip(
        location_id = trip['location_id'],
        vehicle_vin = trip['vehicle_vin'],
        start_time = datetime.strptime(trip['start_time'], '%Y-%m-%d %H:%M:%S'),
        start_longitude = trip['start_longitude'],
        start_latitude = trip['start_latitude'],
        finish_longitude = trip['finish_longitude'],
        finish_latitude = trip['finish_latitude'],
        duration = timedelta(seconds=trip['duration']),
        distance = trip['distance'],
        servicedrive = trip['servicedrive']
    ) for trip in data['trips'] ]
    
    fuelpermeter = data['fuelpermeter']
    refuelpersecond = data['refuelpersecond']
    
    if fuel:
        vehicles = [ entities.Vehicle(
            id=vehicle['id'],
            longitude=vehicle['longitude'], 
            latitude=vehicle['latitude'],
            start_time=datetime.strptime(vehicle['start_time'], '%Y-%m-%d %H:%M:%S'),
            fuel = vehicle['fuellevel']    
        ) for vehicle in data['vehicles'] ]
        
        spots = [ entities.Spot(
            id=spot['id'],
            longitude=spot['longitude'], 
            latitude=spot['latitude'],
            start_time=datetime.strptime(spot['start_time'], '%Y-%m-%d %H:%M:%S'),
            fuel = spot['fuellevel']    
        ) for spot in data['spots'] ]
    
        splitpoints = [ entities.Splitpoint(
            id=splitpoint['id'],
            time=datetime.strptime(splitpoint['time'], '%Y-%m-%d %H:%M:%S'),
            weight=splitpoint['weight']
        ) for splitpoint in data['splitpoints'] ]
        
        if 'time' in data and 'dist' in data:
            indices = vehicles + refuelpoints + trips + spots
            DistanceMatrix.set(indices, indices, data['time'], data['dist'])
        
        return refuelpoints, vehicles, trips, spots, splitpoints, fuelpermeter, refuelpersecond
        
    else:
        vehicles = [ entities.Vehicle(
            id=vehicle['id'],
            longitude=vehicle['longitude'], 
            latitude=vehicle['latitude'],
            start_time=datetime.strptime(vehicle['start_time'], '%Y-%m-%d %H:%M:%S')        
        ) for vehicle in data['vehicles'] ]
        
        if 'time' in data and 'dist' in data:
            indices = vehicles + refuelpoints + trips
            DistanceMatrix.set(indices, indices, data['time'], data['dist'])
        
        return refuelpoints, vehicles, trips, fuelpermeter, refuelpersecond

def read_instance_from_json_customer(filename):
    
    with open(filename) as f:
        data = json.load(f)
        
    tmp_customers = OrderedDict((
        customer['id'],
        [ entities.Trip(
            location_id=trip['location_id'],
            vehicle_vin=trip['vehicle_vin'],
            start_time=datetime.strptime(trip['start']['time'], '%Y-%m-%d %H:%M:%S'),
            start_longitude=trip['start']['lon'],
            start_latitude=trip['start']['lat'],
            finish_longitude=trip['finish']['lon'],
            finish_latitude=trip['finish']['lat'],
            duration=datetime.strptime(trip['finish']['time'], '%Y-%m-%d %H:%M:%S')-datetime.strptime(trip['start']['time'], '%Y-%m-%d %H:%M:%S'),
            distance=trip['distance'],
            servicedrive=trip['servicedrive']
        ) for trip in customer['trips'] ]
    ) for customer in data['customers'])
    
    route_index = max(tmp_customers.keys())
    customers = {}
    routes = {}
    
    for (index, trips) in tmp_customers.iteritems():
        for trip in trips:
            route_index += 1
            result = customers.get(index) + [route_index] if (index in customers.keys()) else [route_index]
            customers.update(dict([(index, result)]))
            routes.update(dict([(route_index, [trip])]))
    
    vehicles = [ entities.Vehicle(
        id=vehicle['id'],
        longitude=vehicle['coordinates']['lon'],
        latitude=vehicle['coordinates']['lat'],
        start_time=datetime.strptime(vehicle['time'], '%Y-%m-%d %H:%M:%S'),
        fuel=vehicle['fuel']
    ) for vehicle in data['vehicles'] ]
    
    refuelpoints = [ entities.RefuelPoint(
        id=refuelpoint['id'],
        lon=refuelpoint['coordinates']['lon'],
        lat=refuelpoint['coordinates']['lat']
    ) for refuelpoint in data['refuelpoints'] ]
    
    fuelpermeter = data['fuelpermeter']
    refuelpersecond = data['refuelpersecond']
    costpermeter = data['costpermeter']
    costpercar = data['costpercar']
    
    inst = instance(vehicles, customers, routes, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar)
    
    basename = os.path.splitext(filename)
    inst._basename = basename
    
    if 'time' in data:
        inst._time = numpy.array(data['time'], dtype = float)
    
    if 'dist' in data:
        inst._dist = numpy.array(data['dist'], dtype = float)
    
    if 'paretorefuelpoints' in data:
        inst._paretorefuelpoints = data['paretorefuelpoints']
    
    if 'initialfuel' in data:
        inst._initialfuel = numpy.array(data['initialfuel'], dtype = float)
    
    return inst