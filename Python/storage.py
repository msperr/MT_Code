import os
import gzip
import json
from datetime import datetime, timedelta
from collections import OrderedDict

import numpy
import progressbar

import entities
from instance import Instance
import xpress
import solution
from config import config

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
        
def load_instance_from_json(filename, compress=None):
    
    if compress is None:
        compress = os.path.splitext(filename)[1] == '.gz'
    if compress and not os.path.splitext(filename)[1] == '.gz':
        filename += '.gz'
    
    with (gzip.open(filename, 'rb') if compress else open(filename, 'r')) as f:
        data = json.load(f)
    
    customers = OrderedDict((customer['id'], [route['id'] for route in customer['routes']]) for customer in data['customers'])
    routes = OrderedDict((route['id'], [entities.Trip.parse(trip) for trip in route['trips']]) for customer in data['customers'] for route in customer['routes'])
    routecost = OrderedDict((route['id'], route['cost']) for customer in data['customers'] for route in customer['routes'])
    vehicles = [entities.Vehicle.parse(vehicle) for vehicle in data['vehicles']]
    refuelpoints = [entities.RefuelPoint.parse(refuelpoint) for refuelpoint in data['refuelpoints']]
    
    fuelpermeter = data['fuelpermeter']
    refuelpersecond = data['refuelpersecond']
    costpermeter = data['costpermeter']
    costpercar = data['costpercar']
    
    inst = Instance(vehicles, customers, routes, routecost, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar)
    
    basename, _ = os.path.splitext(filename)
    inst._basename = basename
    
    if 'time' in data:
        inst._time = numpy.array(data['time'], dtype = float)
    
    if 'dist' in data:
        inst._dist = numpy.array(data['dist'], dtype = float)
    
    return inst

def save_instance_to_json(filename, instance, compress=None):

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
                    'cost': instance._routecost.get(route),
                    'trips': [trip.__json__() for trip in instance._routes.get(route)]
                    } for route in routes]
            } for customer, routes in instance._customers.iteritems()]
        }
    
    if not instance._time is None:
        data['time'] = instance._time.tolist()
    if not instance._dist is None:
        data['dist'] = instance._dist.tolist()
        
    if compress is None:
        compress = os.path.splitext(filename)[1] == '.gz'
    if compress and not os.path.splitext(filename)[1] == '.gz':
        filename += '.gz'
    
    with (gzip.open(filename, 'wb') if compress else open(filename, 'w')) as f:
        json.dump(data, f, sort_keys=True)
        
def load_partial_solution_from_xpress(filename, previous_solution, instance, endpoints, compress=None):
    
    assert not instance is None
    
    parser_vehicles = xpress.parser_object(instance.vehicles + instance.trips)
    parser_trips = xpress.parser_object(instance.trips + instance.refuelpoints, **{'': None})
    
    parser_solution = xpress.parser_definitions({
        'Duties': xpress.parser_dict((parser_vehicles,), xpress.parser_list(parser_trips))
    })
    
    if compress is None:
        compress = os.path.splitext(filename)[1] == '.gz'
    if compress and not os.path.splitext(filename)[1] == '.gz':
        filename += '.gz'

    with (gzip.open(filename, 'rb') if compress else open(filename, 'r')) as f:
        data = f.read()
    
    partial_duties = parser_solution.parse(data)['Duties']
    previous_duties = previous_solution.duties 
    
    duties = {}
    for s, partial_duty in partial_duties.iteritems():
        if isinstance(s, entities.Trip):
            v, duty = previous_solution.duty(s), list(previous_duties[previous_solution.duty(s)])
            index = duty.index(s)
            duty = duty[0:index+1] + partial_duty
            duties.update([(v, duty)])
        elif isinstance(s, entities.Vehicle):
            duties.update([(s, partial_duty)])
        else:
            raise ValueError, 'No trip or vehicle %s' % s
    
    for s, partial_duty in duties.iteritems():
        if (partial_duty[-1] in endpoints if partial_duty else False):
            t = partial_duty[-1]
            v, duty = previous_solution.duty(t), list(previous_duties[previous_solution.duty(t)])
            index = duty.index(t)
            partial_duty.extend(duty[index+1:])
            duties.update([(s, partial_duty)])
    
    sol = solution.Solution(instance, duties)
    
    sol.assert_valid()
    sol._basename = previous_solution._basename

    sol.customers = sol.determine_customers()
        
    return sol

def load_solution_from_xpress(filename, instance=None, compress=None):

    if instance is None:
        instancefile = os.path.join(os.path.dirname(filename), os.path.basename(filename).split('.')[0])
        if os.path.isfile(instancefile + '.json.gz'):
            instancefile += '.json.gz'
            instance = load_instance_from_json(instancefile)
            print 'Successfully loaded instance from %s' % instancefile
        elif os.path.isfile(instancefile + '.json'):
            instancefile += '.json'
            instance = load_instance_from_json(instancefile)
            print 'Successfully loaded instance from %s' % instancefile
        
    assert not instance is None
            
    parser_vehicles = xpress.parser_object(instance.vehicles)
    parser_trips = xpress.parser_object(instance.trips + instance.refuelpoints, **{'': None})
    parser_fuel = xpress.parser_real()

    parser_solution = xpress.parser_definitions({
        'Duties': xpress.parser_dict((parser_vehicles,), xpress.parser_list(parser_trips)),
        'Fuel_Min': xpress.parser_dict((parser_vehicles,), xpress.parser_list(parser_fuel)),
        'Fuel_Max': xpress.parser_dict((parser_vehicles,), xpress.parser_list(parser_fuel)),
    })
    
    if compress is None:
        compress = os.path.splitext(filename)[1] == '.gz'
    if compress and not os.path.splitext(filename)[1] == '.gz':
        filename += '.gz'

    with (gzip.open(filename, 'rb') if compress else open(filename, 'r')) as f:
        data = f.read()
    
    #progress = progressbar.ProgressBar(maxval=len(data), widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
    #solution_duties = parser_solution.parse(data, progress)
    #progress.finish()
    solution_dict = parser_solution.parse(data)

    sol = solution.Solution(instance, solution_dict['Duties'])
    
    basename = os.path.splitext(filename)[0]
    if compress:
        basename = os.path.splitext(basename)[0]
    
    sol.assert_valid()
    sol._basename = basename
    
    sol.fuelstates = sol.determine_fuelstates(solution_dict['Fuel_Min'], solution_dict['Fuel_Max'])
    sol.customers = sol.determine_customers()
        
    return sol

def save_solution_to_xpress(filename, solution, compress=None):
    
    data = OrderedDict([
        ('Duties', ((xpress.xpress_index(s), (xpress.xpress_index(t) for t in duty)) for s, duty in solution.duties.iteritems()))
    ])
    
    if compress is None:
        compress = os.path.splitext(filename)[1] == '.gz'
    if compress and not os.path.splitext(filename)[1] == '.gz':
        filename += '.gz'
    
    with (gzip.open(filename, 'wb') if compress else open(filename, 'w')) as f:
        xpress.xpress_write(f, data)

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
    routecost = {}
    
    for (index, trips) in tmp_customers.iteritems():
        for trip in trips:
            route_index += 1
            result = customers.get(index) + [route_index] if (index in customers.keys()) else [route_index]
            customers.update(dict([(index, result)]))
            routes.update(dict([(route_index, [trip])]))
            routecost.update(dict([(route_index, trip.duration.total_seconds())]))
    
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
    
    inst = Instance(vehicles, customers, routes, routecost, refuelpoints, fuelpermeter, refuelpersecond, costpermeter, costpercar)
    
    basename, _ = os.path.splitext(filename)
    inst._basename = basename
    
    if 'time' in data:
        inst._time = numpy.array(data['time'], dtype = float)
    
    if 'dist' in data:
        inst._dist = numpy.array(data['dist'], dtype = float)
    
    return inst