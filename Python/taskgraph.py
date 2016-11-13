from multiprocessing import Pool
import time as timemodule
from datetime import timedelta
import itertools

import networkx

import entities
import util

def grouper(iterable, n):
    "Collect data into fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return ([item for item in group if item] for group in itertools.izip_longest(fillvalue=None, *args))

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
                    'fr': min((t.start_time - (s.start_time if isinstance(s, entities.Vehicle) else s.finish_time) - instance.timedelta(s, p) - instance.timedelta(p, t)).total_seconds() * instance._refuelpersecond, 1.0) if p else 0.0
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
                            edge[2]['fd']=0.0
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
        'ft': t.distance * 1000.0 * instance._fuelpermeter
    }) for t in instance._trips)

    G.add_nodes_from((s, {
        'f0': s.fuel
    }) for s in spots)

    G.add_edges_from((ds, s) for s in instance._vehicles)
    
    pool = Pool(4)

    original = {t: t for t in itertools.chain(instance._vehicles, instance._refuelpoints, instance._trips, spots)}

    starttime = timemodule.clock()
    
    for edges in pool.imap_unordered(create_taskgraph_preprocessing, ((instance, these) for these in grouper(instance.vertices, 100))):
        for s, t, attr in edges:
            attr['refuelpoint'] = original[attr['refuelpoint']] if attr['refuelpoint'] else None
            G.add_edge(original[s], original[t], attr)

#     for s, t, attr in create_taskgraph_preprocessing(instance):
#         attr['refuelpoint'] = original[attr['refuelpoint']] if attr['refuelpoint'] else None
#         G.add_edge(original[s], original[t], attr)

    pool.terminate()
    pool.join()
        
    print 'Time elapsed: ', (timemodule.clock() - starttime)

    G.add_edges_from((s, de) for s in instance._vehicles)
    G.add_edges_from((t, de) for t in instance._trips)
    G.add_edges_from((s, de) for s in spots)

    return G