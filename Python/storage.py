import os
import json
from datetime import datetime, timedelta
from collections import OrderedDict

import numpy

import entities
from instance import Instance

def load_vehicles_from_json(filename):
    with open(filename) as f:    
        data = json.load(f)
        return [entities.Vehicle.parse(vehicle) for vehicle in data['vehicles']]

def save_vehicles_to_json(vehicles, filename, fuel=False):   
    with open(filename,'w') as f:
        json.dump({'vehicles': [vehicle.__json__() for vehicle in vehicles]}, f, sort_keys=True)

def load_refuelpoints_from_json(filename):
    with open(filename) as f:
        data = json.load(f)
        return [entities.RefuelPoint.parse(refuelpoint) for refuelpoint in data['refuelpoints']]

def save_refuelpoints_to_json(refuelpoints, filename):
    with open(filename,'w') as f:
        json.dump({'refuelpoints': [refuelpoint.__json__() for refuelpoint in refuelpoints]}, f, sort_keys=True)
        
def load_instance_from_json(filename):
    
    with open(filename) as f:
        data = json.load(f)
    
    customers = OrderedDict((customer['id'], [route['id'] for route in customer['routes']]) for customer in data['customers'])
    routes = OrderedDict((route['id'], [entities.Trip.parse(trip) for trip in route['trips']]) for customer in data['customers'] for route in customer['routes'])
    vehicles = [entities.Vehicle.parse(vehicle) for vehicle in data['vehicles']]
    refuelpoints = [entities.RefuelPoint.parse(refuelpoint) for refuelpoint in data['refuelpoints']]
    
    fuelpermeter = data['fuelpermeter']
    refuelpersecond = data['refuelpersecond']
    costpermeter = data['costpermeter']
    costpercar = data['costpercar']
    
    inst = Instance(vehicles, customers, routes, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar)
    
    basename, _ = os.path.splitext(filename)
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

def save_instance_to_json(filename, instance):
    
    data = {
            'fuelpermeter': instance._fuelpermeter,
            'refuelpersecond': instance._refuelpersecond,
            'costpermeter': instance._costpermeter,
            'costpercar': instance._costpercar,
            'vehicles': [vehicle.__json__() for vehicle in instance._vehicles],
            'refuelpoints': [refuelpoint.__json__() for refuelpoint in instance._refuelpoints],
            'customers': [{
                'id': customer,
                'routes': [{
                    'id': route,
                    'trips': [trip.__json__() for trip in instance._routes.get(route)]
                    } for route in routes]
            } for customer, routes in instance._customers.iteritems()]
        }
    
    if not instance._time is None:
        data['time'] = instance._time.tolist()
    if not instance._dist is None:
        data['dist'] = instance._dist.tolist()
    if not instance._paretorefuelpoints is None:
        data['paretorefuelpoints'] = instance._paretorefuelpoints
    if not instance._initialfuel is None:
        data['initialfuel'] = instance._initialfuel.tolist()
    
    with open(filename, 'w') as f:
        json.dump(data, f, sort_keys=True)

###############################################################################
# deprecated methods
###############################################################################

def load_refuelpoints_from_json_deprecated(filename):
    with open(filename) as f:    
        data = json.load(f)
        return [ entities.RefuelPoint(
            station['id']['id'], 
            station['coordinates']['longitude'], 
            station['coordinates']['latitude']
        ) for station in data['chargeStations'] ]

def load_instance_from_json_deprecated(filename):
    
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
    
    customer_index = 0
    route_index = len(trips)
    customers = {}
    routes = {}
    
    for trip in trips:
        customers.update(dict([(customer_index, [route_index])]))
        routes.update(dict([(route_index, [trip])]))
        customer_index += 1
        route_index += 1

    vehicles = [ entities.Vehicle(
        vehicle_id=vehicle['id'],
        longitude=vehicle['longitude'], 
        latitude=vehicle['latitude'],
        start_time=datetime.strptime(vehicle['start_time'], '%Y-%m-%d %H:%M:%S'),
        fuel = vehicle['fuellevel'] if 'fuellevel' in vehicle else 1.0   
    ) for vehicle in data['vehicles'] ]
        
    fuelpermeter = data['fuelpermeter']
    refuelpersecond = data['refuelpersecond']
    costpermeter = data['costpermeter'] if 'costpermeter' in data else 1.0
    costpercar = data['costpercar'] if 'costpercar' in data else 1000.0
    
    inst = Instance(vehicles, customers, routes, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar)
    
    basename, _ = os.path.splitext(filename)
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

def load_instance_from_json_customer(filename):
    
    with open(filename) as f:
        data = json.load(f)
        
    tmp_customers = OrderedDict((
        customer['id'],
        [ entities.Trip(
            location_id=trip['location_id'],
            vehicle_vin=trip['vehicle_vin'],
            start_time=datetime.strptime(trip['start']['time'], '%Y-%m-%d %H:%M:%S'),
            finish_time=datetime.strptime(trip['finish']['time'], '%Y-%m-%d %H:%M:%S'),
            distance=trip['distance'],
            servicedrive=trip['servicedrive'],
            start_longitude=trip['start']['lon'],
            start_latitude=trip['start']['lat'],
            finish_longitude=trip['finish']['lon'],
            finish_latitude=trip['finish']['lat']
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
        vehicle_id=vehicle['id'],
        longitude=vehicle['coordinates']['lon'],
        latitude=vehicle['coordinates']['lat'],
        start_time=datetime.strptime(vehicle['time'], '%Y-%m-%d %H:%M:%S'),
        fuel=vehicle['fuel']
    ) for vehicle in data['vehicles'] ]
    
    refuelpoints = [ entities.RefuelPoint(
        refuelpoint_id=refuelpoint['id'],
        longitude=refuelpoint['coordinates']['lon'],
        latitude=refuelpoint['coordinates']['lat']
    ) for refuelpoint in data['refuelpoints'] ]
    
    fuelpermeter = data['fuelpermeter']
    refuelpersecond = data['refuelpersecond']
    costpermeter = data['costpermeter']
    costpercar = data['costpercar']
    
    inst = Instance(vehicles, customers, routes, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar)
    
    basename, _ = os.path.splitext(filename)
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