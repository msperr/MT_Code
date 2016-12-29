#pragma once

#include "SchedulingDecompApp.h"

#include <boost/graph/r_c_shortest_paths.hpp>

template<typename T, typename = typename std::enable_if<std::is_arithmetic<T>::value>::type>
struct spprc_resource_container
{
	spprc_resource_container(int vertex = -1, double cost = 0.0, double reduced_cost = 0.0, T fuel = 0, int numcustomers = 0) :
		vertex(vertex), cost(cost), reduced_cost(reduced_cost), fuel(fuel), numcustomers(numcustomers)
	{
	}

	spprc_resource_container(int vertex, double cost, double reduced_cost, T fuel, int numcustomers, const set<int>& customers) :
		vertex(vertex), cost(cost), reduced_cost(reduced_cost), fuel(fuel), numcustomers(numcustomers), customers(customers)
	{}

	spprc_resource_container(const spprc_resource_container& other) :
		spprc_resource_container(other.vertex, other.cost, other.reduced_cost, other.fuel, other.numcustomers, other.customers) 
	{}

	spprc_resource_container& operator=(const spprc_resource_container& other) {
		if (this == &other)
			return *this;
		this->~spprc_resource_container();
		new(this) spprc_resource_container(other);
		return *this;
	}

	int vertex;
	double cost;
	double reduced_cost;
	T fuel;
	int numcustomers;
	set<int> customers;
};

template<typename T>
bool operator==(const spprc_resource_container<T>& lhs, const spprc_resource_container<T>& rhs)
{
	return lhs.vertex == rhs.vertex && lhs.reduced_cost == rhs.reduced_cost && lhs.fuel == rhs.fuel && /*lhs.numcustomers == rhs.numcustomers && */lhs.customers == rhs.customers;
}

template<typename T>
bool operator<(const spprc_resource_container<T>& lhs, const spprc_resource_container<T>& rhs)
{
	return lhs.vertex > rhs.vertex || (lhs.vertex == rhs.vertex && (lhs.reduced_cost < rhs.reduced_cost || (lhs.reduced_cost == rhs.reduced_cost && (lhs.fuel < rhs.fuel || (lhs.fuel == rhs.fuel && (/*lhs.numcustomers > rhs.numcustomers || (lhs.numcustomers == rhs.numcustomers && */lhs.customers < rhs.customers/*)*/))))));
}

template<algorithm_type mode, typename fuel_level_type = std::conditional<mode == exact, double, int>::type>
class spprc_ref
{
public:

	const SchedulingDecompApp& app;
	const fuel_level_type max_fuel_level;
	const bool* include;
	const bool* exclude;
	const double redCostF;
	const double* redCostY;
	const double* redCostV;
	const int* mincustomers;
	const int* maxcustomers;

	vector<int> includeindex;

	spprc_ref(const SchedulingDecompApp& app, fuel_level_type max_fuel_level, const bool* include, const bool* exclude, double redCostF, const double* redCostY, const double* redCostV, const int* mincustomers, const int* maxcustomers) : 
		app(app), max_fuel_level(max_fuel_level), include(include), exclude(exclude), redCostF(redCostF), redCostY(redCostY), redCostV(redCostV), mincustomers(mincustomers), maxcustomers(maxcustomers)
	{
		const int num_vertices = app.inst.num_vehicles + app.inst.num_trips;
		includeindex.clear();
		for (int t = 0; t < num_vertices; t++)
			if (include[t])
				includeindex.push_back(t);
	}

	spprc_ref(const spprc_ref& other) :
		spprc_ref(other.app, other.max_fuel_level, other.include, other.exclude, other.redCostF, other.redCostY, other.RedCostV, other.mincustomers, other.maxcustomers)
	{}

	inline bool operator()(const boost_graph& g, spprc_resource_container<fuel_level_type>& new_cont, const spprc_resource_container<fuel_level_type>& old_cont, boost::graph_traits<boost_graph>::edge_descriptor ed) const
	{
		const arc_property& arc_prop = get(boost::edge_bundle, g)[ed];

		const int num_vertices = app.inst.num_vehicles + app.inst.num_trips;
		const int t = source(ed, g);
		const int s = target(ed, g);

		if (t < num_vertices && exclude[t])
			return false;

		if (s < num_vertices && exclude[s])
			return false;

		const auto iter = std::lower_bound(includeindex.begin(), includeindex.end(), t);
		const int u = iter == includeindex.begin() ? 0 : *(iter - 1);
		if (s < u)
			return false;

		new_cont.vertex = s;
		new_cont.reduced_cost = old_cont.reduced_cost + redCostF * arc_prop.cost_s_r_t + (app.inst.num_vehicles <= t && t < num_vertices ? redCostY[t - app.inst.num_vehicles] : 0.0) + (s < app.inst.num_vehicles && t < num_vertices ? redCostV[s] : 0.0);
		new_cont.cost = old_cont.cost + arc_prop.cost_s_r_t;
		fuel_level_type& fuel = new_cont.fuel;
		new_cont.numcustomers = old_cont.numcustomers + (s >= app.inst.num_vehicles && (mincustomers || maxcustomers) ? 1 : 0);

		fuel = mode == exact ?
			old_cont.fuel + arc_prop.fuel_t + arc_prop.fuel_r_t :
			old_cont.fuel + (fuel_level_type)ceil(max_fuel_level * (arc_prop.fuel_t + arc_prop.fuel_r_t));

		if (fuel > max_fuel_level)
			return false;

		fuel = mode == exact ?
			std::max(fuel - arc_prop.fuel_r + arc_prop.fuel_s_r, arc_prop.fuel_s_r) :
			std::max(fuel + (fuel_level_type)ceil(max_fuel_level * (-arc_prop.fuel_r + arc_prop.fuel_s_r)), (fuel_level_type)ceil(max_fuel_level * arc_prop.fuel_s_r));

		if (fuel > max_fuel_level)
			return false;

		if (s < app.inst.num_vehicles && fuel > app.inst.vehicle_initial_fuel(s) * max_fuel_level)
			return false;

		if (s < app.inst.num_vehicles && ((mincustomers && new_cont.numcustomers < mincustomers[s]) || (maxcustomers && maxcustomers[s] < new_cont.numcustomers)))
			return false;

		new_cont.customers = old_cont.customers;
		if (app.forbidAlternatives) {
			if (app.inst.num_vehicles <= s && s < num_vertices && app.inst.customer_type(app.inst.vertex_customer(s)) >= Instance::intermittent_alternatives)
				if (!new_cont.customers.insert(app.inst.vertex_customer(s)).second)
					return false;
			//new_cont.customers.erase(arc_prop.drop_customers.begin(), arc_prop.drop_customers.end());
			for (int c : arc_prop.drop_customers)
				new_cont.customers.erase(c);
		}

		return true;
	}
};

template<typename T>
class spprc_dominance
{
public:
	inline bool operator()(const spprc_resource_container<T>& lhs, const spprc_resource_container<T>& rhs) const
	{
		return lhs.vertex >= rhs.vertex && lhs.reduced_cost <= rhs.reduced_cost && lhs.fuel <= rhs.fuel && lhs.numcustomers == rhs.numcustomers && lhs.customers == rhs.customers; // must be ">=" here!!! must NOT be ">"!!!
	}
};

template<typename T>
using spprc_label = boost::r_c_shortest_paths_label<boost_graph, spprc_resource_container<T>>;

template<typename T>
struct spprc_visitor {

	SchedulingDecompApp& app;
	const double* convexDuals;
	vector<DecompVarList>& varLists;

	spprc_visitor(SchedulingDecompApp& app, const double* convexDuals, vector<DecompVarList>& varLists) :
		app(app), convexDuals(convexDuals), varLists(varLists)
	{
	};

	spprc_visitor(const spprc_visitor& other) : spprc_visitor(other.app, other.convexDuals, other.varLists) { // shallow copy
	}

	spprc_visitor(const spprc_visitor&&) = delete;

	void on_label_popped(const spprc_label<T>&, const boost_graph& graph) {};

	void on_label_feasible(const spprc_label<T>& label, const boost_graph& graph) {
	}

	void on_label_not_feasible(const spprc_label<T>&, const boost_graph& graph) {};

	void on_label_dominated(const spprc_label<T>& label, const boost_graph& graph) {
	};

	void on_label_not_dominated(const spprc_label<T>& label, const boost_graph& graph) {

		const int num_vertices = app.inst.num_vehicles + app.inst.num_trips;

		const int v = label.resident_vertex;

		if (v < app.inst.num_vehicles && label.cumulated_resource_consumption.reduced_cost - convexDuals[v] < -app.m_param.RedCostEpsilon) {

			const int num_vertices = app.inst.num_vehicles + app.inst.num_trips;

			vector<int> indices;
			vector<double> values;

			indices.push_back(app.indexF(v));
			values.push_back(label.cumulated_resource_consumption.cost);

			indices.push_back(app.indexV(v));
			values.push_back(label.p_pred_label->resident_vertex < num_vertices ? 1.0 : 0.0);

			int length = 0;

			for (auto l = &label; l->p_pred_label; l = l->p_pred_label) {

				const int t = l->p_pred_label->resident_vertex;

				if (t < num_vertices) {
					indices.push_back(app.indexY(v, t - app.inst.num_vehicles));
					values.push_back(1.0);
					length++;
				}
			}

			indices.push_back(app.indexR(v));
			values.push_back(length);

			assert((label.p_pred_label->resident_vertex < num_vertices) == (length > 0) && (label.cumulated_resource_consumption.numcustomers == 0 || label.cumulated_resource_consumption.numcustomers == length));

			DecompVar* var = new DecompVar(indices, values, label.cumulated_resource_consumption.reduced_cost, label.cumulated_resource_consumption.cost);
			var->setBlockId(v);
			varLists[v].push_back(var);
		}
	};

	template<class Queue>
	bool on_enter_loop(const Queue& queue, const boost_graph& graph) { return true; };
};

template<algorithm_type mode>
void SchedulingDecompApp::solveRelaxedBoost(const double redCostF, const double* redCostY, const double* redCostV, const double* convexDuals, const bool* include, const bool* exclude, const int* mincustomers, const int* maxcustomers, DecompVarList& varList, vector<DecompSolverStatus>& states) {

	typedef std::conditional<mode == exact, double, int>::type fuel_level_type;
	typedef spprc_label<fuel_level_type> spprc_label_type;
	const fuel_level_type max_fuel_level = mode == exact ? 1.0 : num_levels - 1;

	const int num_vertices = inst.num_vehicles + inst.num_trips;

	vector<DecompVarList> varLists(inst.num_vehicles);

	boost::r_c_shortest_paths(graph, 
		get(&vertex_property::index, graph), 
		get(&arc_property::index, graph), 
		num_vertices, 
		num_vertices + 1, 
		vector<vector<boost::graph_traits<boost_graph>::edge_descriptor>>(), 
		vector<spprc_resource_container<fuel_level_type>>(), 
		spprc_resource_container<fuel_level_type>(), 
		spprc_ref<mode>(*this, max_fuel_level, include, exclude, redCostF, redCostY, redCostV, mincustomers, maxcustomers), 
		spprc_dominance<fuel_level_type>(), 
		boost::default_r_c_shortest_paths_allocator(), 
		spprc_visitor<fuel_level_type>(*this, convexDuals, varLists)
	);

	for (int v = 0; v < inst.num_vehicles; v++) {
		if (!exclude[v]) {
			if (varLists[v].empty()) {
				states[v] = mode == exact ? DecompSolStatOptimal : DecompSolStatNoSolution;
			} else {
				varList.splice(varList.end(), varLists[v]);
				states[v] = mode == exact ? DecompSolStatOptimal : DecompSolStatFeasible;
			}
		}
	}
}