from multiprocessing import Pool
import itertools
from collections import OrderedDict
import json

import networkx
import progressbar

import entities
import util
import xpress
from config import config

count = True

def create_taskgraph_preprocessing(args):
    instance, vertices = args
    edges = []
    for s in (vertices if vertices else instance.vertices):
        for t in instance.trips:
            time = t.start_time - (s.start_time if isinstance(s, entities.Vehicle) else s.finish_time)
            if instance.timedelta(s,t) <= time:
                filtered = [r for r in instance.refuelpoints if instance.dist(s,r) <= instance.maxrange and instance.dist(r,t) <= instance.maxrange and instance.timedelta(s, r) + instance.timedelta(r, t) <= time]
                
                try:
                    p = min(filtered, key = lambda k: instance.dist(s, k) + instance.dist(k, t))
                except (ValueError):
                    p = None

                edge = (s, t, {
                    'refuelpoint': p,
                    'fe': instance.dist(s, t) * instance._fuelpermeter,
                    'fg': instance.dist(s, p) * instance._fuelpermeter if p else 1.1,
                    'fh': instance.dist(p, t) * instance._fuelpermeter if p else 1.1,
                    'fd': (instance.dist(s, p) + instance.dist(p, t) - instance.dist(s, t)) * instance._fuelpermeter if p else 1.1,
                    'fr': min((t.start_time - (s.start_time if isinstance(s, entities.Vehicle) else s.finish_time) - instance.timedelta(s, p) - instance.timedelta(p, t)).total_seconds() * instance._refuelpersecond, 1.0) if p else 0.0,
                    'ce': instance.dist(s, t) * instance._costpermeter,
                    'cd': (instance.dist(s, p) + instance.dist(p, t) - instance.dist(s, t)) * instance._costpermeter if p else 0.0
                })
                
                if edge[2]['refuelpoint']:
                    if edge[2]['fd'] >= edge[2]['fr'] or edge[2]['fd']/instance._fuelpermeter > 2500.0 or edge[2]['fr']/instance._refuelpersecond < 1800.0:
                        edge[2]['refuelpoint'] = None
                        edge[2]['fg'] = 1.1
                        edge[2]['fh'] = 1.1
                        edge[2]['fd'] = 1.1
                        edge[2]['fr'] = 0.0
                    else:
                        if edge[2]['fg'] + edge[2]['fh'] < edge[2]['fe']:
                            edge[2]['fe'] = edge[2]['fg'] + edge[2]['fh']
                            edge[2]['fd'] = 0.0
                            edge[2]['ce'] = edge[2]['fe'] * (instance._costpermeter/instance._fuelpermeter)
                            edge[2]['cd'] = 0.0
                edges.append(edge)
                
    return edges

def create_taskgraph(instance):
    
    #TODO
    spots = []

    ds = 'DEPOTSTART'
    de = 'DEPOTEND'

    G = networkx.DiGraph(ds=ds, de=de, fuelpermeter=instance._fuelpermeter, refuelpersecond=instance._refuelpersecond)

    G.add_node(ds)
    G.add_node(de)

    G.add_nodes_from((s, {
        'f0': s.fuel
    }) for s in instance._vehicles)

    G.add_nodes_from((t, {
        'ft': t.distance * instance._fuelpermeter,
        'ct': t.distance * instance._costpermeter,
        'fmin': min(map(lambda k: instance.dist(t, k)*instance._fuelpermeter, instance.refuelpoints)),
        'fmax': 1 - min(map(lambda k: instance.dist(k, t)*instance._fuelpermeter, instance.refuelpoints))
    }) for t in instance._trips)

    G.add_nodes_from((s, {
        'f0': s.fuel
    }) for s in spots)

    G.add_edges_from((ds, s) for s in instance._vehicles)
    
    pool = Pool(4)

    original = {t: t for t in itertools.chain(instance._vehicles, instance._refuelpoints, instance._trips, spots)}
    
    n = int(len(instance.vertices)/64)+1
    progress = progressbar.ProgressBar(maxval=64, widgets=[progressbar.Bar('#', '[', ']'), ' ', progressbar.Percentage(), ' ', progressbar.Timer(), ' ', progressbar.ETA()], term_width=config['console']['width']).start()
    progresscount = itertools.count(1)
    
    for edges in pool.imap_unordered(create_taskgraph_preprocessing, ((instance, these) for these in util.grouperList(instance.vertices, n))):
        for s, t, attr in edges:
            attr['refuelpoint'] = original[attr['refuelpoint']] if attr['refuelpoint'] else None
            G.add_edge(original[s], original[t], attr)
        progress.update(progresscount.next())
    
    #for edges in create_taskgraph_preprocessing((instance, instance.vertices)):
    #    for s, t, attr in edges:
    #        attr['refuelpoint'] = original[attr['refuelpoint']] if attr['refuelpoint'] else None
    #        G.add_edge(original[s], original[t], attr)
    
    progress.finish()

    pool.terminate()
    pool.join()

    G.add_edges_from((s, de) for s in instance._vehicles)
    G.add_edges_from((t, de) for t in instance._trips)
    G.add_edges_from((s, de) for s in spots)

    return G

def split_taskgraph_single(G, startpoints, endpoints, splittime, index):
    splitpoints = []
    for endpoint in endpoints:
        splitpoint_id = 'Split%s_%d' % (endpoint, index + 1)
        splitpoint = entities.Splitpoint(splitpoint_id = splitpoint_id, time = splittime)
        splitpoints.append(splitpoint)
        G.add_node(splitpoint, {
            'ft': 0.0,
            'ct': 0.0
        })
        attr = dict()
        attr['refuelpoint'] = None
        attr['fe'] = 0.0
        attr['fg'] = 0.0
        attr['fh'] = 0.0
        attr['fd'] = 0.0
        attr['fr'] = 0.0
        attr['ce'] = 0.0
        attr['cd'] = 0.0
        G.add_edge(splitpoint, endpoint, attr)
        for startpoint in startpoints:
            attr =  G.get_edge_data(startpoint, endpoint, default = 0)
            if attr:
                G.add_edge(startpoint, splitpoint, attr)
                G.remove_edge(startpoint, endpoint)
    return G, splitpoints

def split_taskgraph(instance, G, timepoints):    
    splitpoint_list = []
    trip_list = []
    customer_list = []
    trips = instance._trips

    for (index, timepoint) in enumerate(timepoints):
        startpoints = instance._vehicles
        endpoints = []
        partialtrips = []     
        for trip in trips:
            if instance.customer_starttime(trip) >= timepoint:
                endpoints.append(trip)
            else:
                startpoints.append(trip)
                partialtrips.append(trip)
        trips = endpoints
        G, splitpoints = split_taskgraph_single(G, startpoints, endpoints, timepoint, index)
        splitpoint_list.append(splitpoints)
        trip_list.append(partialtrips)
        customer_list.append(set(instance.customer(trip) for trip in partialtrips))
    trip_list.append(trips)
    customer_list.append(set(instance.customer(trip) for trip in trip_list[-1]))
    splitpoint_list.append([])
    return G, splitpoint_list, trip_list, customer_list

def save_taskgraph_to_xpress(instance, G, filename):

    data = OrderedDict([
        ('DS', G.graph['ds']),
        ('DE', G.graph['de']),
        ('Vehicles', (xpress.xpress_index(s) for s in G.nodes_iter() if isinstance(s, entities.Vehicle))),
        ('Trips', (xpress.xpress_index(t) for t in G.nodes_iter() if isinstance(t, entities.Trip))),
        ('Splitpoints', (xpress.xpress_index(s) for s in G.nodes_iter() if isinstance(s, entities.Splitpoint))),
        ('Refuelpoints', (xpress.xpress_index(r) for r in instance._refuelpoints)),
        ('Trip_Refuelpoints', (((v, w), xpress.xpress_index(attr['refuelpoint']) if attr['refuelpoint'] else '') for v, w, attr in G.edges_iter(data=True) if 'refuelpoint' in attr)),
        ('Nin', ((v, (xpress.xpress_index(w) for w in G.predecessors_iter(v))) for v in G.nodes())),
        ('Nout', ((v, (xpress.xpress_index(w) for w in G.successors_iter(v))) for v in G.nodes())),
        ('F0', ((v, attr['f0']) for v, attr in G.nodes_iter(data=True) if 'f0' in attr)),
        ('FT', ((v, attr['ft']) for v, attr in G.nodes_iter(data=True) if 'ft' in attr)),
        ('FE', (((v, w), attr['fe']) for v, w, attr in G.edges_iter(data=True) if 'fe' in attr)),
        ('FG', (((v, w), attr['fg']) for v, w, attr in G.edges_iter(data=True) if 'fg' in attr)),
        ('FH', (((v, w), attr['fh']) for v, w, attr in G.edges_iter(data=True) if 'fh' in attr)),
        ('FD', (((v, w), attr['fd']) for v, w, attr in G.edges_iter(data=True) if 'fd' in attr)),
        ('FR', (((v, w), attr['fr']) for v, w, attr in G.edges_iter(data=True) if 'fr' in attr)),
        ('CT', ((v, attr['ct']) for v, attr in G.nodes_iter(data=True) if 'ct' in attr)),
        ('CE', (((v, w), attr['ce']) for v, w, attr in G.edges_iter(data=True) if 'ce' in attr)),
        ('CD', (((v, w), attr['cd']) for v, w, attr in G.edges_iter(data=True) if 'cd' in attr)),
        ('Customers', (c for c in instance._customers.iterkeys())),
        ('Customer_Routes', ((c, r) for (c, r) in instance._customers.iteritems())),
        ('Routes', ((r, [xpress.xpress_index(t)]) for (r, t) in instance._routes.iteritems())),
        ('Vehicle_Cost', instance._costpercar)
    ])

    with open(filename, 'w') as f:
        xpress.xpress_write(f, data)

def save_split_taskgraph_to_xpress(instance, G, splitpoint_list, trip_list, customer_list, filename):
    assert len(splitpoint_list) == len(trip_list) == len(customer_list)
    
    indices = range(1, len(splitpoint_list) + 1)
    data = OrderedDict([
        ('I', (i for i in indices)),
        ('Partial_Trips', ((i, (xpress.xpress_index(v) for v in trip_list[i-1])) for i in indices)),
        ('Partial_Splitpoints', ((i, (xpress.xpress_index(v) for v in splitpoint_list[i-1])) for i in indices)),
        ('Partial_Customers', ((i, (c for c in customer_list[i-1])) for i in indices)),
        ('DS', G.graph['ds']),
        ('DE', G.graph['de']),
        ('Vehicles', (xpress.xpress_index(s) for s in G.nodes_iter() if isinstance(s, entities.Vehicle))),
        ('Refuelpoints', (((v, w), xpress.xpress_index(attr['refuelpoint']) if attr['refuelpoint'] else '') for v, w, attr in G.edges_iter(data=True) if 'refuelpoint' in attr)),
        ('Nin', ((v, (xpress.xpress_index(w) for w in G.predecessors_iter(v))) for v in G.nodes())),
        ('Nout', ((v, (xpress.xpress_index(w) for w in G.successors_iter(v))) for v in G.nodes())),
        ('F0', ((v, attr['f0']) for v, attr in G.nodes_iter(data=True) if 'f0' in attr)),
        ('FT', ((v, attr['ft']) for v, attr in G.nodes_iter(data=True) if 'ft' in attr)),
        ('FE', (((v, w), attr['fe']) for v, w, attr in G.edges_iter(data=True) if 'fe' in attr)),
        ('FG', (((v, w), attr['fg']) for v, w, attr in G.edges_iter(data=True) if 'fg' in attr)),
        ('FH', (((v, w), attr['fh']) for v, w, attr in G.edges_iter(data=True) if 'fh' in attr)),
        ('FD', (((v, w), attr['fd']) for v, w, attr in G.edges_iter(data=True) if 'fd' in attr)),
        ('FR', (((v, w), attr['fr']) for v, w, attr in G.edges_iter(data=True) if 'fr' in attr)),
        ('CT', ((v, attr['ct']) for v, attr in G.nodes_iter(data=True) if 'ct' in attr)),
        ('CE', (((v, w), attr['ce']) for v, w, attr in G.edges_iter(data=True) if 'ce' in attr)),
        ('CD', (((v, w), attr['cd']) for v, w, attr in G.edges_iter(data=True) if 'cd' in attr)),
        ('Fmin', ((v, attr['fmin']) for v, attr in G.nodes_iter(data=True) if 'fmin' in attr)),
        ('Fmax', ((v, attr['fmax']) for v, attr in G.nodes_iter(data=True) if 'fmax' in attr)),
        ('Customer_Routes', ((c, r) for (c, r) in instance._customers.iteritems())),
        ('Routes', ((r, [xpress.xpress_index(t)]) for (r, t) in instance._routes.iteritems())),
        ('Vehicle_Cost', instance._costpercar)
    ])
    
    with open(filename, 'w') as f:
        xpress.xpress_write(f, data)

def save_taskgraph_to_json(G, filename):
    dictionary = dict()
    dictionary['nodes'] = []
    for node, attributes in G.nodes_iter(data = True):
        nodedict = dict()
        nodedict['attributes'] = attributes
        nodedict['successors'] = dict()
        for successor in G.successors_iter(node):
            edgeattributes = G.edge[node][successor]
            if ('refuelpoint' in edgeattributes) and edgeattributes['refuelpoint']:
                edgeattributes['refuelpoint'] = xpress.xpress_index(edgeattributes['refuelpoint'])
            nodedict['successors'][xpress.xpress_index(successor) if isinstance(successor, entities.Vehicle) or isinstance(successor, entities.Trip) or isinstance(successor, entities.Splitpoint) else successor] = edgeattributes
        dictionary['nodes'].append({xpress.xpress_index(node) if isinstance(node, entities.Vehicle) or isinstance(node, entities.Trip) or isinstance(node, entities.Splitpoint) else node : nodedict})
    dictionary['attributes'] = G.graph
    
    with open(filename, 'w') as f:
        json.dump(dictionary,f)

def load_taskgraph_from_json(filename, dictionary):
    
    with open(filename) as f:
        data = json.load(f)
        
    ds = data['attributes']['ds']
    de = data['attributes']['de']
    fuelpermeter = data['attributes']['fuelpermeter']
    refuelpersecond = data['attributes']['refuelpersecond']
    #costpermeter = data['attributes']['costpermeter']
    #costpercar = data['attributes']['costpercar']
    #G = networkx.DiGraph(ds=ds, de=de, fuelpermeter=fuelpermeter, refuelpersecond=refuelpersecond, costpermeter=costpermeter, costpercar=costpercar)
    G = networkx.DiGraph(ds=ds, de=de, fuelpermeter=fuelpermeter, refuelpersecond=refuelpersecond)
    for node in data['nodes']:
        for key in node:
            if key == ds or key == de:
                    G.add_node(str(key))
            else:
                    G.add_node(dictionary[key], node[key]['attributes'])
    for node in data['nodes']:
        for (key, value) in node.iteritems():
            if key == ds or key == de:
                for (name, attributes) in value['successors'].iteritems():
                    if 'refuelpoint' in attributes:
                        if attributes['refuelpoint']:
                            attributes['refuelpoint'] = dictionary[attributes['refuelpoint']]
                    G.add_edge(key, dictionary[name], attributes)
            else:
                for (name, attributes) in value['successors'].iteritems():
                    if 'refuelpoint' in attributes:
                        if attributes['refuelpoint']:
                            attributes['refuelpoint'] = dictionary[attributes['refuelpoint']]
                    G.add_edge(dictionary[key], de if name == de else dictionary[name], attributes)
    for t in G.nodes_iter():
        if isinstance(t, entities.Trip):
            if all(G.edge[s][t]['fe'] > 1 and (G.edge[s][t]['fg'] > 1 or G.edge[s][t]['fh'] > 1) for s in G.predecessors_iter(t) if s != ds):
                print "Warning: %s not reachable" % t
    return G
