#pragma once

#include "SchedulingDecompApp.h"

#include <vector>
#include <set>
#include <limits>

#include "simple_matrix.h"

using std::vector;
using std::set;

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

template<typename T, typename = typename std::enable_if<std::is_arithmetic<T>::value>::type>
struct label_base {

	int vertex = -1;
	T fuel = 0;
	double fRedCost = 0.0;
	double fCost = 0.0;
	const label_base<T>* successor = NULL;
	int refuelpoint = -1;
	int length = 0;

	//set<int> customers;
	set<int> routes;

	label_base(int vertex, T fuel, double fRedCost, double fCost, int refuelpoint, const label_base<T>* successor, int length) :
		vertex(vertex), fuel(fuel), fRedCost(fRedCost), fCost(fCost), refuelpoint(refuelpoint), successor(successor), length(length) {
	}

	bool operator<(const label_base<T>& rhs) const {
		return fuel < rhs.fuel || (fuel == rhs.fuel && fRedCost < rhs.fRedCost);
	}

	bool operator>(const label_base<T>& rhs) const {
		return fuel > rhs.fuel || (fuel == rhs.fuel && fRedCost > rhs.fRedCost);
	}

	void print() const {
		std::cout << "vertex=" << vertex << " fuel=" << fuel << " redCost=" << fRedCost << " cost=" << fCost << " succVertex=" << (successor ? successor->vertex : -1) << " succFuel=" << (successor ? successor->fuel : -1) << " refuelpoints=" << refuelpoint << " length=" << length << std::endl;
	}
};

template<typename T, T max_fuel_level, typename = typename std::enable_if<std::is_integral<T>::value>::type>
struct discrete_label : label_base<T> {

	discrete_label(int vertex = -1, double fuel = INFINITY) :
		label_base(vertex, fuel < INFINITY ? (T)ceil(max_fuel_level * fuel) : std::numeric_limits<T>::max(), std::numeric_limits<T>::max(), std::numeric_limits<T>::max(), -1, nullptr, -1) {}

	discrete_label(int vertex, double fuel, double fRedCost, double fCost, int refuelpoint, const discrete_label<T, max_fuel_level>* successor, int length) :
		label_base(vertex, (T) ceil(max_fuel_level * fuel), fRedCost, fCost, refuelpoint, successor, length) {}

	double fuellevel() const {
		return (double) fuel / max_fuel_level;
	}
};

template<typename T, typename = typename std::enable_if<std::is_floating_point<T>::value>::type>
struct label : label_base<T> {

	label(int vertex = -1, double fuel = INFINITY) :
		label_base(vertex, fuel, INFINITY, INFINITY, -1, nullptr, -1) {}

	label(int vertex, double fuel, double fRedCost, double fCost, int refuelpoint, const label<T>* successor, int length) :
		label_base(vertex, fuel, fRedCost, fCost, refuelpoint, successor, length) {}

	double fuellevel() const {
		return fuel;
	}
};

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

template<class label_type>
struct label_container {
};

template<class label_type>
class label_container_simple : label_container<label_type> {

private:

	vector<label_type> labels;

public:

	label_container_simple(int num_vehicles) : labels(num_vehicles) {
		reset();
	}

	void reset() {
		for (int t = 0; t < labels.size(); t++)
			labels[t] = std::move(label_type(t));
	}

	void reset(const label_type& label) {
		for (int t = 0; t < labels.size(); t++)
			reset(t, label);
	}

	void reset(int s, label_type& label) {
		labels[s] = label;
	}

	void insert(const label_type& label_s) {
		const int s = label_s.vertex;
		if (label_s.fRedCost < labels[s].fRedCost)
			labels[s] = label_s;
	}

	const label_type& get(int s) const {
		return labels[s];
	}

	const singleton<label_type> operator[] (int s) const {
		return singleton<label_type>(labels[s]);
	}
};

template<class label_type>
class label_container_discrete : label_container<label_type> {

private:

	simple_matrix<label_type> labels;

public:

	label_container_discrete(int num_vehicles, int num_levels) : labels(num_vehicles, num_levels) {
		reset();
	}

	void reset() {
		for (int t = 0; t < labels.rows; t++)
			for (int e = 0; e < labels.cols; e++)
				labels(t, e) = label_type(t, (double)e / (labels.cols - 1));
	}

	void reset(const label_type& label) {
		for (int t = 0; t < labels.rows; t++)
			reset(t, label);
	}

	void reset(int s, const label_type& label) {
		for (int e = 0; e < labels.cols; e++) {
			labels(s, e) = label_type(s, (double)e / (labels.cols - 1), label.fRedCost, label.fCost, label.refuelpoint, lable.successor, label.length);
			//labels(s, e).customers = label.customers;
			label(s, e).routes = label.routes;
		}
	}

	void insert(const label_type& label_s) {
		const int s = label_s.vertex;
		const int e = label_s.fuel;
		if (label_s.fRedCost < labels(s, e).fRedCost)
			labels[s] = label_s;
	}

	const label_type& get(int s) const {
		return labels[s];
	}

	const range<label_type*> operator[] (int s) const {
		return labels.row(s);
	}
};

template<class label_type>
class label_container_pareto : label_container<label_type> {

private:

	vector<set<label_type, std::greater<label_type>>> frontiers;

public:

	label_container_pareto(int num_vehicles) : frontiers(num_vehicles) {
		reset();
	}

	void reset() {
		for (int t = 0; t < frontiers.size(); t++) {
			frontiers[t].clear();
			frontiers[t].emplace(t);
		}
	}

	void reset(const label_type& label) {
		for (int t = 0; t < frontiers.size(); t++)
			reset(t, label);
	}

	void reset(int s, const label_type& label) {
		frontiers[s].clear();
		frontiers[s].insert(label);
	}

	void insert(const label_type& label_s) {
		const int s = label_s.vertex;
		auto it = frontiers[s].lower_bound(label_s);
		if (it == frontiers[s].end() || it->fRedCost > label_s.fRedCost)
			it = frontiers[s].insert(it, label_s);
		auto first = it;
		auto last = it;
		for (; first != frontiers[s].begin() && std::prev(first)->fRedCost >= it->fRedCost; --first);
		frontiers[s].erase(first, last);
	}

	const label_type& get(int s) const {
		return *frontiers[s].begin();
	}

	const reversed<set<label_type, std::greater<label_type>>> operator[] (int s) const {
		return reversed<set<label_type, std::greater<label_type>>>(frontiers[s]);
	}

	const int size() {
		int sum = 0;
		for (auto frontier : frontiers)
			sum += frontier.size();
		return sum;
	}
};