#include "Instance.h"

#include "py_int.h"
#include "py_object.h"
#include "py_list.h"
#include "py_dict.h"
#include "py_utils.h"

Instance::Instance(PyObject* pInstance, py_reference_type reftype) : py_object(pInstance, reftype) {
	parse();
}

Instance::Instance(const py_shared_ptr& pInstance) : py_object(pInstance) {
	parse();
}

Instance::Instance(py_shared_ptr&& pInstance) : py_object(pInstance) {
	parse();
}

void Instance::parse() {

	printf(">> Instance::parse() \n");

	py_dict<> pCustomers = getAttr("_customers");
	py_dict<> pRoutes = getAttr("_routes");
	py_list<> pVehicles = getAttr("vehicles");
	py_list<> pTrips = getAttr("trips");
	py_list<> pRefuelpoints = getAttr("refuelpoints");
	py_list<py_object> pVertices = getAttr("vertices");

	py_list<py_list<py_list<py_int>>> pParetoRefuelPoints = getAttr("_paretorefuelpoints");

	cost_per_car = PyFloat_AsDouble(getAttr("_costpercar"));
	cost_per_meter = PyFloat_AsDouble(getAttr("_costpermeter"));
	fuel_per_meter = PyFloat_AsDouble(getAttr("_fuelpermeter"));
	refuel_per_second = PyFloat_AsDouble(getAttr("_refuelpersecond"));

	num_customers = pCustomers.size();
	num_routes = pRoutes.size();
	num_vehicles = pVehicles.size();
	num_trips = pTrips.size();
	num_refuelpoints = pRefuelpoints.size();

	const int num_vertices = num_vehicles + num_trips;
	const int num_ext_vertices = num_vehicles + num_trips + num_refuelpoints;

	printf("Customers: %d, Routes: %d, Vehicles: %d, Trips: %d, Refuelpoints: %d\n", num_customers, num_routes, num_vehicles, num_trips, num_refuelpoints);

	py_shared_ptr pInitialFuel = getAttr("_initialfuel");

	vehicle_initial_fuel.resize(num_vehicles);
	for (int s = 0; s < num_vehicles; s++)
		vehicle_initial_fuel(s) = PyArray_GET<double>(pInitialFuel, s);

	py_shared_ptr pTime = getAttr("_time");

	arc_time.resize(num_ext_vertices, num_ext_vertices, num_ext_vertices);
	for (int s = 0; s < num_ext_vertices; s++)
		for (int t = 0; t < num_ext_vertices; t++)
			arc_time(s, t) = PyArray_GET<double>(pTime, s, t);

	py_shared_ptr pDist = getAttr("_dist");

	arc_dist.resize(num_ext_vertices, num_ext_vertices, num_ext_vertices);
	for (int s = 0; s < num_ext_vertices; s++)
		for (int t = 0; t < num_ext_vertices; t++)
			arc_dist(s, t) = PyArray_GET<double>(pDist, s, t);
	
	py_shared_ptr pRouteCustomerTable = getAttr("_routecustomertable");
	py_shared_ptr pCustomerTable = getAttr("_customertable");
	py_shared_ptr pRouteTable = getAttr("_routetable");

	customer_routes.resize(num_customers);
	route_customer.resize(num_routes);
	for (int t = 0; t < num_routes; t++) {
		route_customer(t) = PyArray_GET<int>(pRouteCustomerTable, t);
		customer_routes(route_customer(t)).push_back(t);
	}

	// deprecated
	customer_vertices.resize(num_customers);
	route_vertices.resize(num_routes);

	customerroute_vertices.resize(num_customers + num_routes);
	vertex_customer.resize(num_vertices);
	vertex_route.resize(num_vertices);
	for (int t = 0; t < num_vertices; t++) {
		vertex_customer(t) = PyArray_GET<int>(pCustomerTable, t);
		vertex_route(t) = PyArray_GET<int>(pRouteTable, t);
		if (t >= num_vehicles) {
			customerroute_vertices(vertex_customer(t)).push_back(t);
			customerroute_vertices(vertex_route(t)).push_back(t);
			customer_vertices(vertex_customer(t)).push_back(t);
			route_vertices(vertex_route(t)-num_customers).push_back(t);
		}
	}

	vertex_starttime.resize(num_vertices);
	for (auto item : pVertices)
		vertex_starttime(item.first) = PyDateTime_AsDouble(item.second.getAttr("start_time"));

	vertex_finishtime.resize(num_vertices);
	for (auto item : pVertices)
		vertex_finishtime(item.first) = PyDateTime_AsDouble(item.second.getAttr("finish_time"));

	vertex_cost.resize(num_vertices);
	for (auto item : pVertices)
		vertex_cost(item.first) = PyFloat_AsDouble(callMethod("cost", "O", item.second.get()));

	vertex_fuel.resize(num_vertices);
	for (auto item : pVertices)
		vertex_fuel(item.first) = PyFloat_AsDouble(callMethod("fuel", "O", item.second.get()));

	arc_dist.resize(num_ext_vertices, num_ext_vertices, num_ext_vertices);
	for (int s = 0; s < num_ext_vertices; s++)
		for (int t = 0; t < num_ext_vertices; t++)
			arc_dist(s, t) = PyArray_GET<double>(pDist, s, t);

	int numel = 0;
	feasible_edge.resize(num_vertices, num_vertices, num_vertices);
	for (int s = 0; s < num_vertices; s++) {
		for (int t = 0; t < num_vehicles; t++)
			feasible_edge(s, t) = false;
		for (int t = num_vehicles; t < num_vertices; t++) {
			feasible_edge(s, t) = (vertex_customer(s) != vertex_customer(t) || vertex_route(s) == vertex_route(t)) && vertex_finishtime(s) + arc_time(s, t) <= vertex_starttime(t);
			if (feasible_edge(s, t))
				numel++;
		}
	}

	printf("Numel: %d\n", numel);

	if (pParetoRefuelPoints.get() != Py_None) {

		arc_refuelpoints.resize(num_vertices, num_vertices, numel);

		for (int t = 0; t < num_vertices; t++) {

			arc_refuelpoints.appendRow();

			for (int s = 0; s < num_vertices; s++) {
				if (feasible_edge(s, t)) {

					auto& refuelpoints = arc_refuelpoints.appendElement(s);

					auto pRefuelpoints = pParetoRefuelPoints[s][t];
					refuelpoints.reserve(pRefuelpoints.size());
					for (auto item : pRefuelpoints)
						refuelpoints.push_back((long) item.second);
				}
			}
		}

	}

	customer_type.resize(num_customers);
	for (int c = 0; c < num_customers; c++)
		customer_type(c) = unknown_alternatives;
	
	printf("<< Instance::parse()\n");
}

void Instance::analyse() {

	printf(">> Instance::analyse()\n");

	struct lookupcomp {

		simple_vector<int>& lookuptable;

		lookupcomp(simple_vector<int>& lookuptable) : lookuptable(lookuptable) {}

		bool operator() (int i, int j) const {
			return lookuptable(i) < lookuptable(j);
		}
	};

	const int num_vertices = num_vehicles + num_trips;

	vector<int> vertices(num_vertices);
	for (int t = 0; t < num_vertices; t++)
		vertices[t] = t;

	std::sort(vertices.begin(), vertices.end(), lookupcomp(vertex_customer));

	int i = 0;
	while (i < num_vertices && vertex_customer(vertices[i]) == -1)
		i++;
	while (i < num_vertices) {

		const int c = vertex_customer(vertices[i]);

		customer_type(c) = parallel_alternatives;

		for (int j = i; j < num_vertices && vertex_customer(vertices[j]) == c; j++) {
			const int s = vertices[j];

			for (int k = i; k < num_vertices && vertex_customer(vertices[k]) == c; k++) {
				const int t = vertices[k];

				if (vertex_finishtime(s) + arc_time(s, t) <= vertex_starttime(t)) {
					customer_type(c) = std::max(customer_type(c), consecutive_alternatives);
					for (int p = 0; p < num_vertices; p++)
						if (vertex_customer(p) != c && vertex_finishtime(s) + arc_time(s, p) <= vertex_starttime(p) && vertex_finishtime(p) + arc_time(p, t) <= vertex_starttime(t))
							customer_type(c) = std::max(customer_type(c), intermittent_alternatives);
				}
			}
		}

		for (; i < num_vertices && vertex_customer(vertices[i]) == c; i++);
	}

	i = 0;
	while (i < num_vertices && vertex_customer(vertices[i]) == -1)
		i++;
	while (i < num_vertices) {

		const int c = vertex_customer(vertices[i]);

		for (int j = i; j < num_vertices && vertex_customer(vertices[j]) == c; j++) {
			const int s = vertices[j];

			for (int k = i; k < num_vertices && vertex_customer(vertices[k]) == c; k++) {
				const int t = vertices[k];

				if (vertex_finishtime(s) + arc_time(s, t) <= vertex_starttime(t)) {
					for (int p = 0; p < num_vertices; p++)
						if (vertex_customer(p) >= 0 && vertex_customer(p) != c && customer_type(vertex_customer(p)) == intermittent_alternatives && vertex_finishtime(s) + arc_time(s, p) <= vertex_starttime(p) && vertex_finishtime(p) + arc_time(p, t) <= vertex_starttime(t))
							customer_type(c) = std::max(customer_type(c), overlapping_alternatives);
				}
			}
		}

		for (; i < num_vertices && vertex_customer(vertices[i]) == c; i++);
	}

	char* customer_alternative_type_strings[] = { "unknown", "parallel", "consecutive", "intermittent", "overlapping" };
	int customer_alternative_type_counter[] = { 0, 0, 0, 0, 0 };

	for (int c = 0; c < num_customers; c++) {
		printf("customer % 4d has type %s\n", c, customer_alternative_type_strings[customer_type(c)]);
		customer_alternative_type_counter[customer_type(c)]++;
	}

	for (int i = 0; i < sizeof(customer_alternative_type_strings) / sizeof(char*); i++)
		printf("type %s occures %d times\n", customer_alternative_type_strings[i], customer_alternative_type_counter[i]);
	
	printf("<< Instance::analyse()\n");
}