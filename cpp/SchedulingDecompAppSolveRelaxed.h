#pragma once

#include "SchedulingDecompApp.h"

#include "Instance.h"

#include <list>
#include <set>

using std::list;
using std::set;

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

template<class label_type, class label_container_type, bool check_fuel, bool check_length, bool check_alternatives, typename>
void SchedulingDecompApp::solveRelaxedLabeling(label_container_type& container, const double redCostF, const double* redCostY, const double* redCostV, const double* convexDuals, const bool* include, const bool* exclude, const int* mincustomers, const int* maxcustomers, DecompVarList& varList, vector<DecompSolverStatus>& states) {
	
	printf(">> SchedulingDecompApp::solveRelaxedLabeling()\n");

	std::cout << "container.size(): " << container.size() << std::endl;

	const int num_vertices = inst.num_vehicles + inst.num_trips;
	const int numExtVertices = inst.num_vehicles + inst.num_trips + inst.num_refuelpoints;

	vector<int> includeindex;
	for (int t = inst.num_vehicles; t < num_vertices; t++)
		if (include[t])
			includeindex.push_back(t);

	vector<int> vehicles;
	for (int t = 0; t < inst.num_vehicles; t++)
		if (!exclude[t])
			vehicles.push_back(t);

	for (int t = includeindex.size() ? includeindex.back() : 0; t < num_vertices; t++) {
		label_type label_t(t, 0.0, 0.0, 0.0, -1, nullptr, 0);
		
		//if (forbidAlternatives && check_alternatives && t >= inst.num_vehicles && inst.customer_type(inst.vertex_customer(t)) >= Instance::intermittent_alternatives)
			//label_t.customers.insert(inst.vertex_customer(t));
		
		if (inst.num_vehicles <= t) {
			int* routes = new int[inst.num_routes];
			for (int i = 0; i < inst.num_routes; i++) {
				routes[i] = inst.customerroute_vertices(i + inst.num_routes).size();
			}
			label_t.routes = routes;
		}
		container.reset(t, label_t);
	}

	vector<DecompVarList> neg_rc(inst.num_vehicles);
	vector<unique_ptr<DecompVar>> min_non_neg_rc(inst.num_vehicles);

	if (!includeindex.size()) {
		for (int s : vehicles) {
			const label_type& label_s = container.get(s);
			if (check_length && mincustomers && label_s.length < mincustomers[s])
				continue;
			if (label_s.fRedCost - convexDuals[s] < -m_param.RedCostEpsilon)
				neg_rc[s].push_back(path(label_s));
		}
	}

	auto arc_refuelpoints_row = inst.arc_refuelpoints.rbegin();
	for (auto row = arc_arcs.rbegin(); row != arc_arcs.rfind(inst.num_vehicles); ++row, ++arc_refuelpoints_row) {

		const int t = row.index();
		if (exclude[t])
			continue;

		std::cout << "t: " << t << std::endl;

		auto iter = std::lower_bound(includeindex.begin(), includeindex.end(), t);
		int u = iter == includeindex.begin() ? 0 : *(iter - 1);

		const double fuel_t = inst.vertex_fuel(t);

		auto arc_s_t_refuelpoints = arc_refuelpoints_row.find(u);
		for (auto arcs_s_t = row.find(u); arcs_s_t != row.end(); ++arcs_s_t, ++arc_s_t_refuelpoints) {

			const int s = arcs_s_t.index();
			if (exclude[s])
				continue;

			if (s < inst.num_vehicles)
				container.reset(s, label_type(s));

			const double dist_s_t = inst.arc_dist(s, t);
			const double fuel_s_t = inst.fuel_per_meter * dist_s_t + fuel_t;
			const double cost_s_t = inst.cost_per_meter * dist_s_t + (s < inst.num_vehicles ? inst.cost_per_car : 0.0) + inst.vertex_cost(t);

			for (const label_type& label_t : container[t]) {

				const double fuel_s = label_t.fuellevel() + fuel_s_t;
				if (check_fuel && fuel_s > 1.0)
					break;

				if (check_fuel && s < inst.num_vehicles && fuel_s > inst.vehicle_initial_fuel(s))
					break;

				if (check_length && s < inst.num_vehicles && ((mincustomers && label_t.length < mincustomers[s] - 1) || (maxcustomers && label_t.length >= maxcustomers[s])))
					continue;

				//if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles && inst.customer_type(inst.vertex_customer(s)) >= Instance::intermittent_alternatives && label_t.customers.find(inst.vertex_customer(s)) != label_t.customers.end())
				if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles && label_t.routes[inst.vertex_route(s)] > 0)
					continue;

				label_type label_s(s, fuel_s, label_t.fRedCost + redCostF * cost_s_t + redCostY[t - inst.num_vehicles] + (s < inst.num_vehicles ? redCostV[s] : 0.0), label_t.fCost + cost_s_t, -1, &label_t, label_t.length + 1);
				label_s.routes = label_t.routes;
				if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles) {
					for (auto route : inst.customer_routes(inst.vertex_customer(s))) {
						label_s.routes[route] = route == inst.vertex_route(s) ? label_s.routes[route] - 1 : 0;
					}
				}

				//label_s.customers = label_t.customers;
				//if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles && inst.customer_type(inst.vertex_customer(s)) >= Instance::intermittent_alternatives)
				//	label_s.customers.insert(inst.vertex_customer(s));

				container.insert(label_s);
			}

			for (int r : *arc_s_t_refuelpoints) {

				const double dist_s_r = inst.arc_dist(s, num_vertices + r);
				const double dist_r_t = inst.arc_dist(num_vertices + r, t);
				const double fuel_s_r = dist_s_r * inst.fuel_per_meter;
				const double fuel_r_t = dist_r_t * inst.fuel_per_meter;
				const double time_r = inst.vertex_starttime(t) - inst.vertex_finishtime(s) - inst.arc_time(s, num_vertices + r) - inst.arc_time(num_vertices + r, t);
				const double refuel_r = std::min(inst.refuel_per_second * time_r, 1.0);
				const double cost_s_r_t = inst.cost_per_meter * (dist_s_r + dist_r_t) + (s < inst.num_vehicles ? inst.cost_per_car : 0.0) + inst.vertex_cost(t);

				for (const label_type& label_t : container[t]) {

					const double fuel_r = label_t.fuellevel() + fuel_t + fuel_r_t;
					if (check_fuel && fuel_r > 1.0)
						break;

					const double fuel_s = std::max(label_t.fuellevel() + fuel_t + fuel_r_t - refuel_r + fuel_s_r, fuel_s_r);
					if (check_fuel && fuel_s > 1.0)
						break;

					if (check_fuel && s < inst.num_vehicles && fuel_s > inst.vehicle_initial_fuel(s))
						break;

					if (check_length && s < inst.num_vehicles && ((mincustomers && label_t.length < mincustomers[s] - 1) || (maxcustomers && label_t.length >= maxcustomers[s])))
						continue;

					//if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles && inst.customer_type(inst.vertex_customer(s)) >= Instance::intermittent_alternatives && label_t.customers.find(inst.vertex_customer(s)) != label_t.customers.end())
					if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles && label_t.routes[inst.vertex_route(s) > 0])
						continue;

					label_type label_s(s, fuel_s, label_t.fRedCost + redCostF * cost_s_r_t + redCostY[t - inst.num_vehicles] + (s < inst.num_vehicles ? redCostV[s] : 0.0), label_t.fCost + cost_s_r_t, r, &label_t, label_t.length + 1);
					//label_s.customers = label_t.customers;
					//if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles && inst.customer_type(inst.vertex_customer(s)) >= Instance::intermittent_alternatives)
					//	label_s.customers.insert(inst.vertex_customer(s));
					label_s.routes = label_t.routes;
					if (forbidAlternatives && check_alternatives && s >= inst.num_vehicles) {
						for (auto route : inst.customer_routes(inst.vertex_customer(s))) {
							label_s.routes[route] = route == inst.vertex_route(s) ? label_s.routes[route] - 1 : 0;
						}
					}
					container.insert(label_s);
				}
			}

			if (s < inst.num_vehicles) {
				const label_type& label_s = container.get(s);
				if (label_s.fRedCost - convexDuals[s] < -m_param.RedCostEpsilon)
					neg_rc[s].push_back(path(label_s));
			}
		}
	}

	std::cout << "Step 3" << std::endl;

	for (int w : vehicles) {
		if (neg_rc[w].empty()) {
			states[w] = DecompSolStatNoSolution;
		}
		else {
			varList.splice(varList.end(), neg_rc[w]);
			states[w] = DecompSolStatFeasible;
		}
	}

	/*for (int i = 0; i < container.size(); i++) {
		container.get(i).print();
	}*/

	printf("labels: %d\n", container.size());

	printf("<< SchedulingDecompApp::solveRelaxedLabeling()\n");
}