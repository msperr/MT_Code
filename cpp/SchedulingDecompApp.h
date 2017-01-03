#pragma once

#define COIN_HAS_CBC 1

#include <memory>
#include <vector>
#include <chrono>

#include "boost/numeric/ublas/matrix.hpp"
#include "compressed_matrix.h"

#include "Python.h"
#include "py_utils.h"
#include "py_object.h"

#include "Instance.h"

#include "DecompApp.h"
#include "DecompVar.h"

#include "label.h"

#include <boost/graph/adjacency_list.hpp>

using std::vector;
using std::pair;
using std::set;
using std::unique_ptr;

//===========================================================================//

struct graph_property
{
	graph_property(const int num_vertices = 0);
};

struct vertex_property
{
	int index;

	vertex_property(int index = -1);
};

struct arc_property
{
	int index;
	int refuelpoint;

	double fuel_s_r;
	double fuel_r;
	double fuel_r_t;
	double fuel_t; // maybe move to spprc_vertex_property or merge with fuel_r_t
	double cost_s_r_t;

	vector<int> drop_routes;

	arc_property(int index, double fuel_s_t, double fuel_t, double cost_s_t, const set<int>& drop_routes);
	arc_property(int index, int refuelpoint, double fuel_s_r, double fuel_r, double fuel_r_t, double fuel_t, double cost_s_r_t, const set<int>& drop_routes);
};

typedef boost::adjacency_list<boost::vecS, boost::vecS, boost::directedS, vertex_property, arc_property, graph_property> boost_graph;

//===========================================================================//

enum algorithm_type {
	heuristic,
	exact
};

class SchedulingDecompApp : public DecompApp {

	friend class SchedulingAlgoPC;

	template<typename> friend struct spprc_visitor;

	struct record {
		int num_columns;
		double upper_bound;
		double lower_bound;
		double approx_lower_bound;

		record(int num_columns, double upper_bound, double lower_bound, double approx_lower_bound) :
			num_columns(num_columns), upper_bound(upper_bound), lower_bound(lower_bound), approx_lower_bound(approx_lower_bound) {}
	};

	struct node {
		node* parent;
		node* branch_down;
		node* branch_up;
		vector<record> statistics;
	};

public:

	const Instance& inst;

	const bool dropUnusedResources = false;
	const bool forbidAlternatives = false;
	const bool findExactCover = true;

private:

	py_object pInitialSolution;

	int column_offset_f;
	int column_offset_y;
	int column_offset_r;
	int column_offset_w;
	int column_offset_v;
	int column_offset_sum_v;
	int column_offset_u;

	const long num_levels = 101;

	// compressed_matrix<compressed_matrix<pair<double, int>>> arc_arcs;
	compressed_matrix<bool> arc_arcs;

	//simple_matrix<discrete_label<int, 100>, cudaMemoryTypeHost> int_labels;
	simple_matrix<discrete_label<int, 100>> int_labels;

	boost_graph graph;
	vector<char*> tex_column_names;
	std::fstream logfile;

	vector<record> history;

public:

	SchedulingDecompApp(UtilParameters& utilParam, Instance& inst, py_object pInitialSolution);
	virtual ~SchedulingDecompApp();

	void createModels();

	void precompute();

	int generateInitVars(DecompVarList& initVars);

	virtual bool solveRelaxedAll(const double* redCost, const double* convexDuals, DecompVarList& varList, vector<DecompSolverStatus>& states);

	virtual DecompSolverStatus solveRelaxed(const int v, const double* redCost, const double convexDual, DecompVarList& varList);

	//template<algorithm_type mode>
	//void solveRelaxedGraph(const double redCostF, const double* redCostY, const double* convexDuals, const bool* include, const bool* exclude, vector<DecompVarList>& varLists, vector<DecompSolverStatus>& states);

	template<class label_type, class label_container_type, bool check_fuel, bool check_length, bool check_alternatives, typename = typename std::enable_if<std::is_base_of<label_container<label_type>, label_container_type>::value>::type>
	void solveRelaxedLabeling(label_container_type& label_container, const double redCostF, const double* redCostY, const double* redCostV, const double* convexDuals, const bool* include, const bool* exclude, const int* mincustomers, const int* maxcustomers, DecompVarList& varList, vector<DecompSolverStatus>& states);

	template<algorithm_type mode>
	void solveRelaxedBoost(const double redCostF, const double* redCostY, const double* redCostV, const double* convexDuals, const bool* include, const bool* exclude, const int* mincustomers, const int* maxcustomers, DecompVarList& varList, vector<DecompSolverStatus>& states);

	virtual bool APPisUserFeasible(const double* x, const int n_cols, const double tolZero);
	virtual int APPheuristics(const double* xhat, const double* origCost, std::vector<DecompSolution*>& xhatIPFeas);
	virtual int generateCuts(const double* x, DecompCutList& newCuts);

	py_object exportSolution(const double* values);

//private:

	inline int indexF(long i) const {
		return column_offset_f + i;
	}

	inline int indexY(long i) const {
		return column_offset_y + i * inst.num_trips;
	}

	inline int indexY(long i, long j) const {
		return column_offset_y + i * inst.num_trips + j;
	}

	inline int indexR(long i) const {
		return column_offset_r + i;
	}

	inline int indexW(long i) const {
		return column_offset_w + i;
	}

	inline int indexV() const {
		return column_offset_v;
	}

	inline int indexV(long i) const {
		return column_offset_v + i;
	}

	inline int indexSumV() const {
		return column_offset_sum_v;
	}

	inline int indexU(long i) const {
		return column_offset_u + i;
	}

	template<typename T>
	DecompVar* path(const label_base<T>& vehicle)  {

		assert(0 <= vehicle.vertex && vehicle.vertex < inst.num_vehicles);

		vector<int> indices;
		vector<double> values;

		indices.reserve(vehicle.length + 3);
		values.reserve(vehicle.length + 3);

		set<int> customerset;

		for (const label_base<T>* l = vehicle.successor; l; l = l->successor) {

			indices.push_back(indexY(vehicle.vertex, l->vertex - inst.num_vehicles));
			values.push_back(1.0);

			if (forbidAlternatives && !customerset.insert(inst.vertex_customer(l->vertex)).second)
				throw std::exception("duplicate customer in column");
		}

		assert(indices.size() == vehicle.length);

		indices.push_back(indexF(vehicle.vertex));
		values.push_back(vehicle.fCost);

		indices.push_back(indexV(vehicle.vertex));
		values.push_back(vehicle.length ? 1.0 : 0.0);

		indices.push_back(indexR(vehicle.vertex));
		values.push_back(vehicle.length);

		DecompVar* var = new DecompVar(indices, values, vehicle.fRedCost, vehicle.fCost);
		var->setBlockId(vehicle.vertex);

		return var;
	}

	void exportSolutionTex(const char* basename, const double* xhat) const;
	void exportSolutionTexCompact(const char* basename, const double* xhat) const;
};