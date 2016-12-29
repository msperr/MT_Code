#pragma once

#include <vector>

#include "py_object.h"

#include "simple_vector.h"
#include "simple_matrix.h"
#include "compressed_matrix.h"

using std::vector;

class Instance : public py_object {

private:

	py_object::swap;
	py_object::operator=;
	py_object::reset;

public:

	enum customer_alternative_type {
		unknown_alternatives,
		parallel_alternatives,
		consecutive_alternatives,
		intermittent_alternatives,
		overlapping_alternatives
	};

	int num_customers;
	int num_vehicles;
	int num_trips;
	int num_refuelpoints;

	double cost_per_car;
	double cost_per_meter;
	double fuel_per_meter;
	double refuel_per_second;

	simple_vector<vector<int>> customer_vertices;

	simple_vector<double> vehicle_initial_fuel;

	simple_vector<int>    vertex_customer;
	simple_vector<double> vertex_starttime;
	simple_vector<double> vertex_finishtime;
	simple_vector<double> vertex_cost;
	simple_vector<double> vertex_fuel;

	simple_matrix<double> arc_time;
	simple_matrix<double> arc_dist;

	compressed_matrix<vector<int>> arc_refuelpoints;

	simple_vector<customer_alternative_type> customer_type;

public:

	Instance(PyObject* pInstance, py_reference_type reftype);
	Instance(const py_shared_ptr& pInstance);
	Instance(py_shared_ptr&& pInstance);

	void build();
	void analyse();

private:

	void parse();

};