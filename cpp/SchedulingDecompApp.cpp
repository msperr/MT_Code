#include "SchedulingDecompApp.h"
#include "SchedulingDecompAppSolveRelaxed.h"
#include "SchedulingDecompAppSolveRelaxedBoost.h"

#include "SchedulingDecompAlgo.h"

#include <assert.h>
#include <algorithm>
#include <utility>
#include <set>
#include <list>

#include "utils.h"

#include "AlpsDecompNodeDesc.h"

#include "py_list.h"
#include "py_dict.h"
#include "py_int.h"

#include "math.h"


#define NOMINMAX
#include "windows.h"

using std::set;
using std::pair;
using std::list;

using std::min;
using std::max;

//===========================================================================//

graph_property::graph_property(const int num_vertices)
{
}

vertex_property::vertex_property(int index) :
index(index)
{
}

arc_property::arc_property(int index, double fuel_s_t, double fuel_t, double cost_s_t, const set<int>& drop_routes) :
index(index), refuelpoint(-1), fuel_s_r(0.0), fuel_r(0.0), fuel_r_t(fuel_s_t), fuel_t(fuel_t), cost_s_r_t(cost_s_t), drop_routes(drop_routes.begin(), drop_routes.end())
{
}

arc_property::arc_property(int index, int refuelpoint, double fuel_s_r, double fuel_r, double fuel_r_t, double fuel_t, double cost_s_r_t, const set<int>& drop_routes) :
index(index), refuelpoint(refuelpoint), fuel_s_r(fuel_s_r), fuel_r(fuel_r), fuel_r_t(fuel_r_t), fuel_t(fuel_t), cost_s_r_t(cost_s_r_t), drop_routes(drop_routes.begin(), drop_routes.end())
{
}

//===========================================================================//

SchedulingDecompApp::SchedulingDecompApp(UtilParameters& utilParam, Instance& inst, py_object pInitialSolution) :
DecompApp(utilParam), inst(inst), pInitialSolution(pInitialSolution), dropUnusedResources(utilParam.GetSetting("dropUnusedResources", false, "CUSTOM")), forbidAlternatives(utilParam.GetSetting("forbidAlternatives", false, "CUSTOM")), findExactCover(utilParam.GetSetting("findExactCover", true, "CUSTOM")) {

	precompute();
	createModels();

	const int num_vertices = inst.num_vehicles + inst.num_trips;
	int_labels.resize(num_vertices, num_levels);

	py_string basename(inst.getAttr("_basename"));
	char* filename(asprintf("%s.progress.txt", (const char*)basename));
	printf("Logfile: %s\n", filename);
	logfile.open(filename, std::fstream::out);
	delete[] filename;
	logfile << "time node iteration cols globlb globub lp status newcols mostnegrc nonzero nonint" << std::endl;
}

SchedulingDecompApp::~SchedulingDecompApp() {

	delete m_modelCore.getModel();
	m_modelCore.setModel(NULL);

	for (auto it : m_modelRelax) {
		delete it.second.getModel();
		it.second.setModel(NULL);
	}

	logfile.close();
}

void SchedulingDecompApp::precompute() {

	std::cout << ">> precompute()" << std::endl;

	const int num_vertices = inst.num_vehicles + inst.num_trips;

	int numel = 0;
	for (int t = 0; t < num_vertices; t++)
		for (int s = 0; s < num_vertices; s++)
			if (inst.feasible_edge(s, t))
				numel++;

	arc_arcs.resize(num_vertices, num_vertices, numel);

	for (int t = 0; t < num_vertices; t++) {
		arc_arcs.appendRow();
		for (int s = 0; s < num_vertices; s++)
			if (inst.feasible_edge(s, t))
				arc_arcs.appendElement(s) = true;
	}

	for (int t = 0; t < num_vertices + 2; t++)
		boost::add_vertex(vertex_property(t), graph);

	vector<set<int>> preceeding_routes(num_vertices);
	vector<set<int>> succeeding_routes(num_vertices);

	for (int t = inst.num_vehicles; t < num_vertices; t++) {
		preceeding_routes[t].insert(inst.vertex_route(t));
		succeeding_routes[t].insert(inst.vertex_route(t));
		for (int s = inst.num_vehicles; s < num_vertices; s++)
			if (inst.feasible_edge(s, t)) {
				preceeding_routes[t].insert(inst.vertex_route(s));
				succeeding_routes[s].insert(inst.vertex_route(t));
			}
	}

	int index = 0;

	for (int t = 0; t < num_vertices; t++) {

		const double fuel_t = inst.vertex_fuel(t);

		set<int> active_routes;
		std::set_intersection(preceeding_routes[t].begin(), preceeding_routes[t].end(), succeeding_routes[t].begin(), succeeding_routes[t].end(), std::inserter(active_routes, active_routes.begin()));

		for (int s = 0; s < num_vertices; s++) {
			if (inst.feasible_edge(s, t)) {

				set<int> drop_routes;
				if (dropUnusedResources)
					std::set_difference(active_routes.begin(), active_routes.end(), preceeding_routes[s].begin(), preceeding_routes[s].end(), std::inserter(drop_routes, drop_routes.begin()));
				
				const double dist_s_t = inst.arc_dist(s, t);
				const double fuel_s_t = inst.fuel_per_meter * dist_s_t;
				const double cost_s_t = inst.cost_per_meter * dist_s_t + (s < inst.num_vehicles ? inst.cost_per_car : 0.0) + inst.vertex_cost(t);

				boost::add_edge(t, s, arc_property(index++, fuel_s_t, fuel_t, cost_s_t, drop_routes), graph);

				for (int r : inst.arc_refuelpoints(t, s)) {

					const double dist_s_r = inst.arc_dist(s, num_vertices + r);
					const double dist_r_t = inst.arc_dist(num_vertices + r, t);
					const double fuel_s_r = dist_s_r * inst.fuel_per_meter;
					const double fuel_r_t = dist_r_t * inst.fuel_per_meter;
					const double time_r = inst.vertex_starttime(t) - inst.vertex_finishtime(s) - inst.arc_time(s, num_vertices + r) - inst.arc_time(num_vertices + r, t);
					const double fuel_r = std::min(inst.refuel_per_second * time_r, 1.0);
					const double cost_s_r_t = inst.cost_per_meter * (dist_s_r + dist_r_t) + (s < inst.num_vehicles ? inst.cost_per_car : 0.0) + inst.vertex_cost(t);

					boost::add_edge(t, s, arc_property(index++, r, fuel_s_r, fuel_r, fuel_r_t, fuel_t, cost_s_r_t, drop_routes), graph);
				}
			}
		}

		boost::add_edge(num_vertices, t, arc_property(index++, 0.0, 0.0, 0.0, set<int>()), graph); // de
	}

	for (int t = 0; t < inst.num_vehicles; t++)
		boost::add_edge(t, num_vertices + 1, arc_property(index++, 0.0, 0.0, 0.0, set<int>()), graph); // ds

	std::cout << "<< precompute()" << std::endl;
}

void SchedulingDecompApp::createModels()
{
	std::cout << ">> createModel()" << std::endl;

	DecompConstraintSet* modelCore = new DecompConstraintSet();

	long numCols = 0;

	column_offset_f = numCols;
	for (int i = 0; i < inst.num_vehicles; i++) {
		tex_column_names.push_back(asprintf("f_{%d}", i));
		modelCore->colNames.push_back(asprintf("f_%03d", i));
		modelCore->colLB.push_back(0.0);
		modelCore->colUB.push_back(m_infinity);
		numCols++;
	}

	column_offset_y = numCols;
	for (int i = 0; i < inst.num_vehicles; i++) {
		for (int j = 0; j < inst.num_trips; j++) {
			tex_column_names.push_back(asprintf("y^{%d}_{%d}", i, j));
			modelCore->colNames.push_back(asprintf("y_%03d_%04d", i, j));
			modelCore->colLB.push_back(0.0);
			modelCore->colUB.push_back(1.0);
			modelCore->integerVars.push_back(numCols++);
		}
	}

	column_offset_v = numCols;
	for (int i = 0; i < inst.num_vehicles; i++) {
		tex_column_names.push_back(asprintf("v_{%d}", i));
		modelCore->colNames.push_back(asprintf("v_%03d", i));
		modelCore->colLB.push_back(0.0);
		modelCore->colUB.push_back(1.0);
		modelCore->integerVars.push_back(numCols++);
	}

	column_offset_r = numCols;
	for (int i = 0; i < inst.num_vehicles; i++) {
		tex_column_names.push_back(asprintf("\\sum_{t \\in \\mathcal{T}} y^{%d}_t", i));
		modelCore->colNames.push_back(asprintf("r_%03d", i));
		modelCore->colLB.push_back(-m_infinity);
		modelCore->colUB.push_back(m_infinity);
		//modelCore->masterOnlyCols.push_back(numCols);
		modelCore->integerVars.push_back(numCols++);
	}

	column_offset_w = numCols;
	for (int j = 0; j < inst.num_trips; j++) {
		tex_column_names.push_back(asprintf("\\sum_{v \\in \\mathcal{V}} y^v_{%d}", j));
		modelCore->colNames.push_back(asprintf("w_%04d", j));
		modelCore->colLB.push_back(0.0);
		modelCore->colUB.push_back(1.0);
		modelCore->masterOnlyCols.push_back(numCols);
		modelCore->integerVars.push_back(numCols++);
	}

	column_offset_sum_v = numCols;
	tex_column_names.push_back(asprintf("v_{sum}"));
	modelCore->colNames.push_back("v_sum");
	modelCore->colLB.push_back(0.0);
	modelCore->colUB.push_back(m_infinity);
	modelCore->masterOnlyCols.push_back(numCols);
	modelCore->integerVars.push_back(numCols++);

	column_offset_u = numCols;
	for (int m = 0; m < inst.num_routes; m++) {
		tex_column_names.push_back(asprintf("\\u_{%d}", m));
		modelCore->colNames.push_back(asprintf("u_%03d", m));
		modelCore->colLB.push_back(0.0);
		modelCore->colUB.push_back(1.0);
		modelCore->integerVars.push_back(numCols++);
	}

	//

	double* objective = new double[numCols];
	std::fill_n(objective, numCols, 0.0);
	for (int i = 0; i < inst.num_vehicles; i++)
		objective[indexF(i)] = 1.0;
	setModelObjective(objective, numCols);
	delete[] objective;

	//

	//int size = (inst.num_vehicles * inst.num_trips)/* + inst.num_vehicles * (inst.num_trips + 1)*/ + (inst.num_vehicles + 1) * inst.num_trips + (inst.num_vehicles + 1) + inst.num_trips;
	int size = inst.num_routes + (inst.num_vehicles + 1) * inst.num_trips + (inst.num_vehicles + 1) + (inst.num_vehicles + 1) * inst.num_trips;
	int* rowInds = new int[size];
	int* colInds = new int[size];
	double* values = new double[size];
	std::fill_n(values, size, 1.0);

	int numRows = 0;
	int el = 0;

	//

	for (int i = 0; i < inst.num_customers; i++) {
		modelCore->rowNames.push_back(asprintf("customer_%03d", i));
		modelCore->rowLB.push_back(1.0);
		modelCore->rowUB.push_back(findExactCover ? 1.0 : m_infinity);
	}

	/*for (int i = 0; i < inst.num_vehicles; i++) {
		for (int j = 0; j < inst.num_trips; j++) {
			rowInds[el] = numRows + inst.vertex_customer(inst.num_vehicles + j);
			colInds[el] = indexY(i, j);
			el++;
		}
	}*/

	for (int i = 0; i < inst.num_routes; i++) {
		rowInds[el] = numRows + inst.route_customer(i);
		colInds[el] = indexU(i);
		el++;
	}

	numRows += inst.num_customers;

	for (int j = 0; j < inst.num_trips; j++) {

		modelCore->rowNames.push_back(asprintf("w_%03d", j));
		modelCore->rowLB.push_back(0.0);
		modelCore->rowUB.push_back(0.0);

		for (int i = 0; i < inst.num_vehicles; i++) {
			rowInds[el] = numRows;
			colInds[el] = indexY(i, j);
			el++;
		}

		rowInds[el] = numRows;
		colInds[el] = indexW(j);
		values[el] = -1.0;
		el++;

		numRows++;
	}

	//

	modelCore->rowNames.push_back("v_sum");
	modelCore->rowLB.push_back(0.0);
	modelCore->rowUB.push_back(0.0);

	for (int i = 0; i < inst.num_vehicles; i++) {
		rowInds[el] = numRows;
		colInds[el] = indexV(i);
		values[el] = 1.0;
		el++;
	}

	rowInds[el] = numRows;
	colInds[el] = indexSumV();
	values[el] = -1.0;
	el++;

	numRows++;

	for (int j = 0; j < inst.num_trips; j++) {
		modelCore->rowNames.push_back(asprintf("route_%04d", j));
		modelCore->rowLB.push_back(0.0);
		modelCore->rowUB.push_back(0.0);
	}

	for (int i = 0; i < inst.num_vehicles; i++) {
		for (int j = 0; j < inst.num_trips; j++) {
			rowInds[el] = numRows + j;
			colInds[el] = indexY(i, j);
			el++;
		}
	}

	for (int j = 0; j < inst.num_trips; j++) {
		rowInds[el] = numRows + j;
		colInds[el] = indexU(inst.vertex_route(j) - inst.num_customers);
		values[el] = -1.0;
		el++;
	}

	numRows += inst.num_trips;

	//

	assert(el == size);
	assert(numRows == modelCore->rowNames.size());

	modelCore->M = new CoinPackedMatrix(false, rowInds, colInds, values, size);
	modelCore->M->setDimensions(numRows, numCols);

	setModelCore(modelCore, "CORE");

	//

	for (int i = 0; i < inst.num_vehicles; i++) {

		DecompConstraintSet* modelRelax = new DecompConstraintSet();

		modelRelax->colLB.insert(modelRelax->colLB.end(), modelCore->colLB.begin(), modelCore->colLB.end());
		modelRelax->colUB.insert(modelRelax->colUB.end(), modelCore->colLB.begin(), modelCore->colLB.end());
		modelRelax->integerVars.insert(modelRelax->integerVars.end(), modelCore->integerVars.begin(), modelCore->integerVars.end());

		modelRelax->colUB[indexF(i)] = modelCore->colUB[indexF(i)];
		modelRelax->activeColumns.push_back(indexF(i));
		modelRelax->colUB[indexR(i)] = modelCore->colUB[indexR(i)];
		modelRelax->activeColumns.push_back(indexR(i));
		modelRelax->colUB[indexV(i)] = modelCore->colUB[indexV(i)];
		modelRelax->activeColumns.push_back(indexV(i));
		for (int j = 0; j < inst.num_trips; j++) {
			modelRelax->colUB[indexY(i, j)] = modelCore->colUB[indexY(i, j)];
			modelRelax->activeColumns.push_back(indexY(i, j));
		}

		modelRelax->rowNames.push_back(asprintf("dummy_%03d", i));
		modelRelax->rowLB.push_back(-m_infinity);
		modelRelax->rowUB.push_back(m_infinity);

		modelRelax->M = new CoinPackedMatrix(false, new int[] { 0 }, new int[]{ indexF(i) }, new double[] { 0.0 }, 1);
		modelRelax->M->setDimensions(1, numCols);

		setModelRelax(modelRelax, "BLOCK", i);
	}

	std::cout << "<< createModel()" << std::endl;

}

int SchedulingDecompApp::generateInitVars(DecompVarList& initVars)
{
	printf(">> generateInitVars()\n");
	py_dict<py_shared_ptr, py_int> pIndex = inst.getAttr("_index");
	py_dict<py_shared_ptr, py_list<>> pDuties = pInitialSolution.getAttr("duties");

	printf("Number of Duties: %d\n", pDuties.size());

	for (auto pair : pDuties) {

		const int v = (long) pIndex[pair.first];

		const int n = pair.second.size();

		vector<int> indices;
		vector<double> values;
		indices.reserve(n + 3);
		values.reserve(n + 3);

		for (auto item : pair.second) {
			py_shared_ptr pTrip(item.second.get(), py_borrowed_ref);
			if ((long)pIndex[pTrip] < inst.num_trips + inst.num_vehicles) {
				indices.push_back(indexY(v, (long)pIndex[pTrip] - inst.num_vehicles));
				values.push_back(1.0);
			}
		}

		const double fCost = PyFloat_AsDouble(pInitialSolution.callMethod("evaluate", "O", pair.first.get()));

		indices.push_back(indexF(v));
		values.push_back(fCost);

		indices.push_back(indexR(v));
		values.push_back(n);

		indices.push_back(indexV(v));
		values.push_back(n ? 1.0 : 0.0);

		DecompVar* var = new DecompVar(indices, values, 0.0, fCost, DecompVar_Point);
		var->setBlockId(v);
		initVars.push_back(var);
	}

	printf("<< generateInitVars()\n");

	return pDuties.size();
}

bool SchedulingDecompApp::solveRelaxedAll(const double* redCost, const double* convexDuals, DecompVarList& varList, vector<DecompSolverStatus>& states) {

	SchedulingAlgoPC* algo = (SchedulingAlgoPC*)getDecompAlgo();

	const int num_vertices = inst.num_vehicles + inst.num_trips;

	const AlpsDecompTreeNode* node = getDecompAlgo()->getCurrentNode();
	const AlpsDecompNodeDesc* desc = (AlpsDecompNodeDesc*)node->getDesc();

	const double* lowerbounds = desc->getLowerBounds();
	const double* upperbounds = desc->getUpperBounds();

	bool* excludes = new bool[inst.num_vehicles * num_vertices];
	for (int v = 0; v < inst.num_vehicles; v++) {
		bool* exclude = excludes + v * num_vertices;
		std::fill_n(exclude, inst.num_vehicles, true);
		for (int t = 0; t < inst.num_trips; t++)
			exclude[inst.num_vehicles + t] = upperbounds[indexY(v, t)] < DecompEpsilon || upperbounds[indexW(t)] < DecompEpsilon;
	}

	bool* includes = new bool[inst.num_vehicles * num_vertices];
	for (int v = 0; v < inst.num_vehicles; v++) {
		bool* include = includes + v * num_vertices;
		std::fill_n(include, inst.num_vehicles, false);
		for (int t = 0; t < inst.num_trips; t++) {
			include[inst.num_vehicles + t] = lowerbounds[indexY(v, t)] > 1.0 - DecompEpsilon;
		}
	}

	int* mincustomers = new int[inst.num_vehicles];
	std::fill_n(mincustomers, inst.num_vehicles, 0);
	for (int v = 0; v < inst.num_vehicles; v++)
		mincustomers[v] = (int)ceil(max(lowerbounds[indexR(v)], 0.0) - DecompEpsilon);

	bool nontrivial = false;
	for (int v = 0; v < inst.num_vehicles; v++)
		if (mincustomers[v] > 0)
			nontrivial = true;
	if (!nontrivial) {
		delete[] mincustomers;
		mincustomers = NULL;
	}

	int* maxcustomers = new int[inst.num_vehicles];
	std::fill_n(maxcustomers, inst.num_vehicles, inst.num_trips);
	for (int v = 0; v < inst.num_vehicles; v++)
		maxcustomers[v] = (int)floor(min(upperbounds[indexR(v)], (double)inst.num_trips) + DecompEpsilon);

	nontrivial = false;
	for (int v = 0; v < inst.num_vehicles; v++)
		if (maxcustomers[v] < inst.num_trips)
			nontrivial = true;
	if (!nontrivial) {
		delete[] maxcustomers;
		maxcustomers = NULL;
	}

	std::fill(states.begin(), states.end(), DecompSolStatNoSolution);

	//

	struct block {
		const bool* include;
		const bool* exclude;
		const double redCostF;
		const double* redCostY;
		const double* redCostV;
		DecompVarList varList;
		double time;

		block(const bool* include, const bool* exclude, const double redCostF, const double* redCostY, const double* redCostV) :
			include(include), exclude(exclude), redCostF(redCostF), redCostY(redCostY), redCostV(redCostV) {}
	};

	vector<block> blocks;

	list<int> remaining_vehicles;
	for (int v = 0; v < inst.num_vehicles; v++)
		remaining_vehicles.push_back(v);

	while (!remaining_vehicles.empty()) {

		const int v = remaining_vehicles.front();
		remaining_vehicles.pop_front();

		bool* include_v = includes + v * num_vertices;
		bool* exclude_v = excludes + v * num_vertices;
		exclude_v[v] = false;

		for (auto iter = remaining_vehicles.begin(); iter != remaining_vehicles.end(); iter = exclude_v[*iter] ? std::next(iter) : remaining_vehicles.erase(iter)) {

			const int w = *iter;
			const bool* exclude_w = excludes + w * num_vertices;
			const bool* include_w = includes + w * num_vertices;

			if (abs(redCost[indexF(v)] - redCost[indexF(w)]) > DecompEpsilon)
				continue;

			if (!all_of_iter(0, (int)inst.num_trips, [&](int t) { return abs(redCost[indexY(v, t)] - redCost[indexY(w, t)]) < DecompEpsilon; }))
				continue;

			if (!all_of_iter(inst.num_vehicles, num_vertices, [=](int t) { return exclude_v[t] == exclude_w[t]; }))
				continue;

			if (!all_of_iter(inst.num_vehicles, num_vertices, [=](int t) { return include_v[t] == include_w[t]; }))
				continue;

			exclude_v[w] = false;
		}

		blocks.emplace_back(include_v, exclude_v, redCost[indexF(v)], redCost + indexY(v), redCost + indexV());
	}

	//

	const int num_blocks = blocks.size();
#pragma omp parallel for schedule(dynamic) if(num_blocks > 1)
	for (int i = 0; i < num_blocks; i++) {

		block& current_block = blocks[i];

		auto time_start = std::chrono::high_resolution_clock::now();

		label_container_pareto<discrete_label<int, 100>> labels(num_vertices);
		solveRelaxedLabeling<discrete_label<int, 100>, label_container_pareto<discrete_label<int, 100>>, true, true, true>(labels, current_block.redCostF, current_block.redCostY, current_block.redCostV, convexDuals, current_block.include, current_block.exclude, mincustomers, maxcustomers, current_block.varList, states);

		bool nosolution = true;
		for (DecompVar* var : current_block.varList)
			nosolution &= var->getReducedCost() >= -m_param.RedCostEpsilon;

		if (nosolution) {
			solveRelaxedBoost<exact>(current_block.redCostF, current_block.redCostY, current_block.redCostV, convexDuals, current_block.include, current_block.exclude, mincustomers, maxcustomers, current_block.varList, states);

			for (int w = 0; w < inst.num_vehicles; w++)
				if (!current_block.exclude[w])
					states[w] = DecompSolStatOptimal;
		}

		current_block.time = std::chrono::duration_cast<std::chrono::duration<double>>(std::chrono::high_resolution_clock::now() - time_start).count();
	}

	//

	const char* DecompSolverStatusStrings[] = {
		"DecompSolStatError",
		"DecompSolStatOptimal",
		"DecompSolStatFeasible",
		"DecompSolStatInfeasible",
		"DecompSolStatNoSolution"
	};

	vector<double> mostnegrc(inst.num_vehicles, 0.0);
	for (block& current_block : blocks)
		for (DecompVar* var : current_block.varList)
			if (var->getReducedCost() - convexDuals[var->getBlockId()] < mostnegrc[var->getBlockId()])
				mostnegrc[var->getBlockId()] = var->getReducedCost() - convexDuals[var->getBlockId()];


	for (block& current_block : blocks) {

		DecompSolverStatus state = DecompSolStatNoSolution;
		for (int w = 0; w < inst.num_vehicles; w++)
			if (!current_block.exclude[w])
				state = std::min(state, states[w]);

		double mostnegrcsum = 0.0;
		for (int w = 0; w < inst.num_vehicles; w++)
			if (!current_block.exclude[w])
				mostnegrcsum += mostnegrc[w];

		printf("solveRelaxedAll() Time: % 3.3f Columns: % 5d MostNegRC: % 3.5f Status: %s Subproblems: ", current_block.time, current_block.varList.size(), mostnegrcsum, DecompSolverStatusStrings[state]);

		for (int w = 0; w < inst.num_vehicles; w++)
			if (!current_block.exclude[w])
				printf("%d ", w);

		printf("\n");
	}

	//

	DecompSolverStatus state = DecompSolStatNoSolution;
	for (int w = 0; w < inst.num_vehicles; w++)
		state = std::min(state, states[w]);

	double mostnegrcsum = 0.0;
	for (double rc : mostnegrc)
		mostnegrcsum += rc;

	history.emplace_back(algo->getMasterOSI()->getNumCols(), algo->getMasterObjValue(), NAN, algo->getMasterObjValue() + mostnegrcsum);

	const int tailoff_length = 500000;
	const double tailoff_percent = 0.00;

	double abs_change = INFINITY;
	double rel_change = INFINITY;
	if (history.size() > tailoff_length) {
		abs_change = history[history.size() - tailoff_length - 1].upper_bound - history.back().upper_bound;
		rel_change = abs_change / history[history.size() - tailoff_length - 1].upper_bound;
	}
	if (rel_change < tailoff_percent)
		history.clear();

	printf("LP: %f UB: %f RC: %f absChange: %f, relChange: %f\n", algo->getMasterObjValue(), algo->getObjBestBoundUB(), mostnegrcsum, abs_change, rel_change);

	if (state > DecompSolStatOptimal && (algo->getObjBestBoundUB() < algo->getMasterObjValue() + mostnegrcsum * 1.0 || rel_change < tailoff_percent)) {

		printf("Resolve Optimally\n");

		const int num_blocks = blocks.size();
#pragma omp parallel for schedule(dynamic) if(num_blocks > 1)
		for (int i = 0; i < num_blocks; i++) {

			block& current_block = blocks[i];

			DecompSolverStatus state = DecompSolStatNoSolution;
			for (int w = 0; w < inst.num_vehicles; w++)
				if (!current_block.exclude[w])
					state = std::min(state, states[w]);

			if (state != DecompSolStatOptimal) {

				auto time_start = std::chrono::high_resolution_clock::now();

				for (DecompVar* var : current_block.varList)
					delete var;
				current_block.varList.clear();

				solveRelaxedBoost<exact>(current_block.redCostF, current_block.redCostY, current_block.redCostV, convexDuals, current_block.include, current_block.exclude, mincustomers, maxcustomers, current_block.varList, states);

				for (int w = 0; w < inst.num_vehicles; w++)
					if (!current_block.exclude[w])
						states[w] = DecompSolStatOptimal;

				current_block.time += std::chrono::duration_cast<std::chrono::duration<double>>(std::chrono::high_resolution_clock::now() - time_start).count();
			}
		}

		std::fill(mostnegrc.begin(), mostnegrc.end(), 0.0);
		for (block& current_block : blocks)
			for (DecompVar* var : current_block.varList)
				if (var->getReducedCost() - convexDuals[var->getBlockId()] < mostnegrc[var->getBlockId()])
					mostnegrc[var->getBlockId()] = var->getReducedCost() - convexDuals[var->getBlockId()];

		for (block& current_block : blocks) {

			DecompSolverStatus state = DecompSolStatNoSolution;
			for (int w = 0; w < inst.num_vehicles; w++)
				if (!current_block.exclude[w])
					state = std::min(state, states[w]);

			double mostnegrcsum = 0.0;
			for (int w = 0; w < inst.num_vehicles; w++)
				if (!current_block.exclude[w])
					mostnegrcsum += mostnegrc[w];

			printf("solveRelaxedAll() Time: % 3.3f Columns: % 5d MostNegRC: % 3.5f Status: %s Subproblems: ", current_block.time, current_block.varList.size(), mostnegrcsum, DecompSolverStatusStrings[state]);

			for (int w = 0; w < inst.num_vehicles; w++)
				if (!current_block.exclude[w])
					printf("%d ", w);

			printf("\n");
		}

		double mostnegrcsum = 0.0;
		for (double rc : mostnegrc)
			mostnegrcsum += rc;

		history.emplace_back(algo->getMasterOSI()->getNumCols(), algo->getMasterObjValue(), NAN, algo->getMasterObjValue() + mostnegrcsum);
	}

	//

	for (block& current_block : blocks)
		varList.splice(varList.end(), current_block.varList);

	//

	state = DecompSolStatNoSolution;
	for (int w = 0; w < inst.num_vehicles; w++)
		state = std::min(state, states[w]);

	int noninteger = 0;
	int nonzero = 0;
	const double* xhat = algo->getXhat();
	for (int i = 0; i < inst.num_vehicles; i++) {
		for (int j = 0; j < inst.num_trips; j++) {
			if (xhat[indexY(i, j)] > DecompEpsilon)
				nonzero++;
			if (abs(xhat[indexY(i, j)] - round(xhat[indexY(i, j)])) > DecompEpsilon)
				noninteger++;
		}
	}


	logfile << globalTimer.getRealTime() << " "
		<< algo->m_nodeStats.nodeIndex << " "
		<< algo->m_nodeStats.priceCallsTotal << " "
		<< algo->getMasterOSI()->getNumCols() << " "
		<< algo->getObjBestBoundLB() << " "
		<< algo->getObjBestBoundUB() << " "
		<< algo->getMasterObjValue() << " "
		<< DecompSolverStatusStrings[state] << " "
		<< varList.size() << " "
		<< mostnegrcsum << " "
		<< nonzero << " "
		<< noninteger << " "
		<< std::endl;

	//

	delete[] excludes;
	delete[] includes;

	if (mincustomers)
		delete[] mincustomers;
	if (maxcustomers)
		delete[] maxcustomers;

	return true;
}

DecompSolverStatus SchedulingDecompApp::solveRelaxed(const int v, const double* redCost, const double convexDual, DecompVarList& varList)
{
	throw new std::exception("not implemented");
}

bool SchedulingDecompApp::APPisUserFeasible(const double* x, const int n_cols, const double tolZero)
{
	return true;
}

int SchedulingDecompApp::generateCuts(const double* x, DecompCutList& cutList)
{
	return 0;
}

int SchedulingDecompApp::APPheuristics(const double* xhat, const double* origCost, std::vector<DecompSolution*>& xhatIPFeas)
{
	return 0;
}

void SchedulingDecompApp::exportSolutionTex(const char* basename, const double* xhat) const {

	std::fstream f;
	unique_ptr<char[]> filename = sprintf_a("%s.tex", basename);
	f.open(filename.get(), std::fstream::out);
	f << "\\documentclass{standalone}" << std::endl;
	f << "\\usepackage{amsmath}" << std::endl;
	f << "\\usepackage{xcolor}" << std::endl;
	f << "\\definecolor{lightgray}{gray}{0.75}" << std::endl;
	f << "\\setcounter{MaxMatrixCols}{" << (inst.num_trips + 1) << "}" << std::endl;
	f << "\\begin{document}" << std::endl;
	f << "$v = \\begin{pmatrix}" << std::endl;

	bool anynonzero = false;
	bool anynoninteger = false;

	for (int i = 0; i < inst.num_vehicles; i++) {

		const bool nonzero = xhat[indexV(i)] > DecompEpsilon;
		const bool noninteger = nonzero && xhat[indexV(i)] < 1 - DecompEpsilon;

		if (noninteger)
			f << "\\textcolor{red}{" << std::setprecision(2) << xhat[indexV(i)] << "}";
		else if (nonzero)
			f << "1";
		else
			f << "\\textcolor{lightgray}0";

		f << "\\\\" << std::endl;

		anynonzero |= nonzero;
		anynoninteger |= noninteger;
	}

	const double sum = xhat[indexSumV()];
	f << (anynoninteger ? "\\textcolor{red}" : (anynonzero ? "" : "\\textcolor{lightgray}")) << (abs(sum - round(sum)) < DecompEpsilon ? "{\\bullet}" : "{\\ast}");
	f << "\\end{pmatrix}$" << std::endl;
	f << "$y = \\begin{pmatrix}" << std::endl;

	for (int i = 0; i < inst.num_vehicles; i++) {

		bool anynoninteger = false;

		for (int j = 0; j < inst.num_trips; j++) {
			const bool noninteger = abs(xhat[indexY(i, j)] - round(xhat[indexY(i, j)])) > DecompEpsilon;

			if (j)
				f << " & ";

			if (noninteger)
				f << "\\textcolor{red}{" << std::setprecision(2) << xhat[indexY(i, j)] << "}";
			else if (xhat[indexY(i, j)] > DecompEpsilon)
				f << "1";
			else
				f << "\\textcolor{lightgray}0";

			anynoninteger |= noninteger;
		}

		const double sum = xhat[indexR(i)];
		f << " & " << (anynoninteger ? "\\textcolor{red}" : (sum > DecompEpsilon ? "" : "\\textcolor{lightgray}")) << (abs(sum - round(sum)) < DecompEpsilon ? "{\\bullet}" : "{\\ast}");
		f << "\\\\" << std::endl;
	}

	for (int j = 0; j < inst.num_trips; j++) {

		bool anynoninteger = false;
		for (int i = 0; i < inst.num_vehicles; i++)
			anynoninteger |= abs(xhat[indexY(i, j)] - round(xhat[indexY(i, j)])) > DecompEpsilon;

		if (j)
			f << " & ";

		const double sum = xhat[indexW(j)];
		f << (anynoninteger ? "\\textcolor{red}" : (sum > DecompEpsilon ? "" : "\\textcolor{lightgray}")) << (abs(sum - round(sum)) < DecompEpsilon ? "{\\bullet}" : "{\\ast}");
	}
	f << " & " << std::endl;

	f << "\\end{pmatrix}$" << std::endl;
	f << "\\end{document}" << std::endl;
	f.close();

	STARTUPINFO si;
	PROCESS_INFORMATION pi;
	memset(&si, 0, sizeof(si));
	memset(&pi, 0, sizeof(pi));
	si.cb = sizeof(si);
	std::unique_ptr<char[]> cmdline = sprintf_a("pdflatex.exe -extra-mem-bot=10000000 -extra-mem-bot=10000000 -interaction=nonstopmode -quiet -job-name=\"%s\" \"%s\"", basename, filename.get());
	CreateProcess(NULL, cmdline.get(), NULL, NULL, false, CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
}

void SchedulingDecompApp::exportSolutionTexCompact(const char* basename, const double* xhat) const {

	std::fstream f;
	unique_ptr<char[]> filename = sprintf_a("%s.tex", basename);
	f.open(filename.get(), std::fstream::out);
	f << "\\documentclass[tikz]{standalone}" << std::endl;
	f << "\\usetikzlibrary{matrix}" << std::endl;
	f << "\\begin{document}" << std::endl;

	f << "\\begin{tikzpicture}[" << std::endl;
	f << "  zero/.append style={fill=white,circle}," << std::endl;
	f << "  every node/.style={inner sep=0pt,minimum size=3pt}," << std::endl;
	f << "  int/.append style={fill=black,circle}," << std::endl;
	f << "  nonint/.append style={fill=red,circle}" << std::endl;
	f << "]" << std::endl;
	f << "\\matrix[matrix of math nodes,column sep=0.5pt,row sep=0.5pt] {" << std::endl;
	
	for (int i = 0; i < inst.num_vehicles; i++) {

		if (i)
			f << "\\\\" << std::endl;

		for (int j = 0; j < inst.num_trips; j++) {

			if (j)
				f << "&";

			const bool noninteger = abs(xhat[indexY(i, j)] - round(xhat[indexY(i, j)])) > DecompEpsilon;
			if (noninteger)
				f << "|[nonint]|";
			else if (xhat[indexY(i, j)] > DecompEpsilon)
				f << "|[int]|";
		}

		const double sum = xhat[indexR(i)];
		f << "&[3ex]" << (sum > DecompEpsilon ? (abs(sum - round(sum)) > DecompEpsilon ? "|[nonint]|" : "|[int]|") : "|[zero]|");
	}

	f << "\\\\[2ex]" << std::endl;

	for (int j = 0; j < inst.num_trips; j++) {

		if (j)
			f << "&";

		const double sum = xhat[indexW(j)];
		f << (sum > DecompEpsilon ? (abs(sum - round(sum)) > DecompEpsilon ? "|[nonint]|" : "|[int]|") : "|[zero]|");
	}
	f << "&[3ex]\\\\" << std::endl;

	f << "};" << std::endl;
	f << "\\end{tikzpicture}" << std::endl;
	f << "\\end{document}" << std::endl;
	f.close();

	STARTUPINFO si;
	PROCESS_INFORMATION pi;
	memset(&si, 0, sizeof(si));
	memset(&pi, 0, sizeof(pi));
	si.cb = sizeof(si);
	std::unique_ptr<char[]> cmdline = sprintf_a("pdflatex.exe -extra-mem-bot=10000000 -extra-mem-bot=10000000 -interaction=nonstopmode -quiet -job-name=\"%s\" \"%s\"", basename, filename.get());
	CreateProcess(NULL, cmdline.get(), NULL, NULL, false, CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
}