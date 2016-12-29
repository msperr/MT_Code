#pragma once

#include "py_shared_ptr.h"

#include <utility>

template<class T = py_shared_ptr>
class py_list : public py_shared_ptr {

private:

	class iterator {

	private:

		const py_list& pList;
		Py_ssize_t pos;

	public:

		iterator(const py_list& pList, Py_ssize_t pos) : pList(pList), pos(pos) {}

		bool operator!=(const iterator& other) const {
			return pList.get() != other.pList.get() || pos != other.pos;
		}

		std::pair<Py_ssize_t, T> operator*() const {
			return std::pair<Py_ssize_t, T>(pos, T(PyList_GetItem(pList, pos), py_borrowed_ref));
		}

		const iterator& operator++() {
			pos++;
			return *this;
		}
	};

public:

	py_list(PyObject* pList, py_reference_type reftype) : py_shared_ptr(pList, reftype) {}
	py_list(const py_shared_ptr& pList) : py_shared_ptr(pList) {}
	py_list(py_shared_ptr&& pList) : py_shared_ptr(pList) {}

	int size() {
		return (int)PyList_Size(*this);
	}

	T operator[](int pos) const {
		return T(PyList_GetItem(*this, pos), py_borrowed_ref);
	}

	iterator begin() const {
		return iterator(*this, 0);
	}

	iterator end() const {
		return iterator(*this, PyList_Size(get()));
	}
};