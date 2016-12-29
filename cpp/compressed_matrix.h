#pragma once

#include <algorithm>
#include <iostream>

using std::pair;

template<typename T> class compressed_matrix {

public:

	struct indexcomp {

		bool operator() (pair<int, T>& p, int i) const {
			return p.first < i;
		}

		bool operator() (int i, pair<int, T>& p) const {
			return i < p.first;
		}
	};

	struct valuecomp {

		bool operator() (pair<int, T>& p, T& t) const {
			return p.second < t;
		}

		bool operator() (T& t, pair<int, T>& p) const {
			return t < p.second;
		}
	};

	class element_iterator {

	private:
		pair<int, T>* data;

	public:

		element_iterator(pair<int, T>* data) : data(data) {
		}

		bool operator!=(const element_iterator& other) {
			return data != other.data;
		}

		T& operator*() const {
			return data->second;
		}

		const element_iterator& operator++() {
			data++;
			return *this;
		}

		int index() {
			return data->first;
		}

		void print() {
			std::cout << data->first << " " << data << std::endl;
		}

	};

	class row_iterator {

	private:
		pair<int, T>** data;
		int i;

	public:

		row_iterator(pair<int, T>** data, int i) : data(data), i(i) {
		}

		bool operator!=(const row_iterator& other) {
			return data != other.data;
		}

		const row_iterator& operator++() {
			data++;
			i++;
			return *this;
		}

		int index() {
			return i;
		}

		element_iterator begin() const {
			return element_iterator(data[0]);
		}

		element_iterator end() const {
			return element_iterator(data[1]);
		}

		element_iterator find(int i) {
			return element_iterator(std::lower_bound(data[0], data[1], i, indexcomp()));
		}

		void print() {
			std::cout << i << " " << data[0] << " " << data[1] << std::endl;
		}
	};

	class row_reverse_iterator {

	private:
		pair<int, T>** data;
		int i;

	public:

		row_reverse_iterator(pair<int, T>** data, int i) : data(data), i(i) {
		}

		bool operator!=(const row_reverse_iterator& other) {
			return data != other.data;
		}

		const row_reverse_iterator& operator++() {
			data--;
			i--;
			return *this;
		}

		int index() {
			return i - 1;
		}

		element_iterator begin() const {
			return element_iterator(data[-1]);
		}

		element_iterator end() const {
			return element_iterator(data[0]);
		}

		element_iterator find(int i) const {
			return element_iterator(std::lower_bound(data[-1], data[0], i, indexcomp()));
		}

		void print() {
			std::cout << i-1 << " " << data[-1] << " " << data[0] << std::endl;
		}
	};

public:

	int rows = 0;
	int cols = 0;
	int usedrows = 0;
	pair<int, T>** data = 0;
	pair<int, T>* dataend = 0;

	compressed_matrix() {
	}

	compressed_matrix(int rows, int cols) : compressed_matrix(rows, cols, 0) {
	}

	compressed_matrix(int rows, int cols, int size) : rows(rows), cols(cols), usedrows(0) {
		data = new pair<int, T>*[rows + 1];
		assert(data);
		std::fill_n(data, rows + 1, new pair<int, T>[size]);
		dataend = *data + size;
	}

	~compressed_matrix() {
		if (data) {
			delete[] data[0];
			delete[] data;
		}
	}

	void resize(int rows, int cols, int size) {
		this->~compressed_matrix();
		new(this) compressed_matrix(rows, cols, size);
	}

	void appendRow() {
		if (usedrows < rows) {
			data[usedrows + 1] = data[usedrows];
			usedrows++;
		} else {
			throw new std::exception("Cannot append row");
		}
	}

	T& appendElement(int col) {
		if ((data[usedrows - 1] == data[usedrows] || data[usedrows][-1].first < col) && data[usedrows] != dataend) {
			data[usedrows]->first = col;
			return (data[usedrows]++)->second;
		} else {
			throw new std::exception("Cannot append element");
		}
	}

	T& operator() (int i, int j) const {
		assert(0 <= i && i < usedrows && 0 <= j && j < cols);
		pair<int, T>* element = std::lower_bound(data[i], data[i + 1], j, indexcomp());
		assert(element != data[i + 1] && element->first == j);
		return element->second;
	}

	row_iterator begin() const {
		return row_iterator(data, 0);
	}

	row_iterator end() const {
		return row_iterator(data + usedrows, usedrows);
	}

	row_iterator find(int i) const {
		if (0 <= i && i < usedrows)
			return row_iterator(data + i, i);
		else
			return end();
	}

	row_reverse_iterator rbegin() const {
		return row_reverse_iterator(data + usedrows, usedrows);
	}

	row_reverse_iterator rend() const {
		return row_reverse_iterator(data, 0);
	}

	row_reverse_iterator rfind(int i) const {
		if (0 <= i && i < usedrows)
			return row_reverse_iterator(data + i, i);
		else
			return rend();
	}

	void print() const {
		for (int i = 0; i <= usedrows; i++)
			std::cout << data[i] << std::endl;
	}
};