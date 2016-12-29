#pragma once

#include "SchedulingDecompApp.h"

#include "Instance.h"
#include "label.h"

#include "py_list.h"

#include <list>
#include <set>

using std::list;
using std::set;

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

py_object SchedulingDecompApp::exportSolution(const double* values) {

	
	const int num_vertices = inst.num_vehicles + inst.num_trips;
	const int numExtVertices = inst.num_vehicles + inst.num_trips + inst.num_refuelpoints;

	label_container_pareto<label<double>> container(num_vertices);

	for (int v = 0; v < inst.num_vehicles; v++) {
		int t = num_vertices;
		for (int s = num_vertices - 1; t >= inst.num_vehicles; s--) {

			if (s < inst.num_vehicles)
				s = v;

			if (s < inst.num_vehicles || values[indexY(v, s - inst.num_vehicles)] >= 1.0 - DecompEpsilon) {

				if (t >= num_vertices) {
					container.insert(label<double>(s, 0.0, 0.0, 0.0, -1, NULL, 0));
				} else {

					const double fuel_t = inst.vertex_fuel(t);

					const double dist_s_t = inst.arc_dist(s, t);
					const double fuel_s_t = inst.fuel_per_meter * dist_s_t + fuel_t;
					const double cost_s_t = inst.cost_per_meter * dist_s_t + (s < inst.num_vehicles ? inst.cost_per_car : 0.0) + inst.vertex_cost(t);

					for (const label<double>& label_t : container[t]) {

						const double fuel_s = label_t.fuellevel() + fuel_s_t;
						if (fuel_s > 1.0)
							break;
						if (s < inst.num_vehicles && fuel_s > inst.vehicle_initial_fuel(s))
							break;

						label<double> label_s(s, fuel_s, label_t.fRedCost + cost_s_t, label_t.fCost + cost_s_t, -1, &label_t, label_t.length);
						container.insert(label_s);
					}


					auto arc_refuelpoints_row = inst.arc_refuelpoints.find(t);
					auto arc_s_t_refuelpoints = arc_refuelpoints_row.find(s);
					for (int r : *arc_s_t_refuelpoints) {

						const double dist_s_r = inst.arc_dist(s, num_vertices + r);
						const double dist_r_t = inst.arc_dist(num_vertices + r, t);
						const double fuel_s_r = dist_s_r * inst.fuel_per_meter;
						const double fuel_r_t = dist_r_t * inst.fuel_per_meter;
						const double time_r = inst.vertex_starttime(t) - inst.vertex_finishtime(s) - inst.arc_time(s, num_vertices + r) - inst.arc_time(num_vertices + r, t);
						const double refuel_r = std::min(inst.refuel_per_second * time_r, 1.0);
						const double cost_s_r_t = inst.cost_per_meter * (dist_s_r + dist_r_t) + (s < inst.num_vehicles ? inst.cost_per_car : 0.0) + inst.vertex_cost(t);

						for (const label<double>& label_t : container[t]) {

							const double fuel_r = label_t.fuellevel() + fuel_t + fuel_r_t;
							if (fuel_r > 1.0)
								break;

							const double fuel_s = std::max(label_t.fuellevel() + fuel_t + fuel_r_t - refuel_r + fuel_s_r, fuel_s_r);
							if (fuel_s > 1.0)
								break;
							if (s < inst.num_vehicles && fuel_s > inst.vehicle_initial_fuel(s))
								break;

							label<double> label_s(s, fuel_s, label_t.fRedCost + cost_s_r_t, label_t.fCost + cost_s_r_t, r, &label_t, label_t.length);
							container.insert(label_s);
						}
					}
				}

				t = s;
			}
		}
	}

	py_list<py_object> pExtVertices(inst.getAttr("extendedvertices"));

	PyObject* pDuties = PyDict_New();

	for (int v = 0; v < inst.num_vehicles; v++) {

		PyObject* pDuty = PyList_New((int)(values[indexR(v)] + DecompEpsilon));
		for (int i = 0; i < values[indexR(v)] + DecompEpsilon; i++)
			PyList_SetItem(pDuty, i, Py_None);

		const label<double>* label_s = NULL;
		for (const label<double>& label_t : container[v])
			if (!label_s || label_t.fCost < label_s->fCost)
				label_s = &label_t;

		assert(abs(label_s->fCost - values[indexF(v)]) < DecompEpsilon);

		int k = 0;
		while (label_s->successor) {
			PyObject* pTrip = pExtVertices[label_s->successor->vertex];
			PyObject* pRefuelpoint = label_s->refuelpoint + 1 ? pExtVertices[num_vertices + label_s->refuelpoint] : Py_None;
			PyObject* pTuple = PyTuple_New(2);
			Py_XINCREF(pTrip);
			PyTuple_SetItem(pTuple, 0, pTrip);
			Py_XINCREF(pRefuelpoint);
			PyTuple_SetItem(pTuple, 1, pRefuelpoint);
			PyList_SetItem(pDuty, k++, pTuple);
			label_s = (label<double>*) label_s->successor;
		}
		assert(abs(k - values[indexR(v)]) < DecompEpsilon);

		PyObject* pVehicle = pExtVertices[v];
		Py_XINCREF(pVehicle);
		PyDict_SetItem(pDuties, pVehicle, pDuty);
	}

	Py_XINCREF(inst.get());

	py_object pModuleSolution(PyImport_ImportModule("solution"), py_new_ref);
	py_object pClassSolution = py_object(pModuleSolution.getAttr("Solution"));
	return std::move(py_object(PyInstance_New(pClassSolution, Py_BuildValue("(O,O)", inst.get(), pDuties), Py_BuildValue("{}")), py_new_ref));
}