#pragma once

#include "py_shared_ptr.h"

#include <utility>

template<class S = py_shared_ptr, class T = py_shared_ptr>
class py_dict : public py_shared_ptr {

private:

	class iterator {

	private:

		const py_dict& pDict;
		bool last;
		Py_ssize_t pos;
		PyObject* pKey;
		PyObject* pValue;

	public:

		iterator(const py_dict& pDict, bool last) : pDict(pDict), last(last), pos(0) {
			if (!last)
				++(*this);
		}

		bool operator!=(const iterator& other) {
			return (last != other.last) || (!last && pos != other.pos);
		}

		std::pair<S, T> operator*() const {
			return std::pair<S, T>(S(pKey, py_borrowed_ref), T(pValue, py_borrowed_ref));
		}

		const iterator& operator++() {
			last = !PyDict_Next(pDict, &pos, &pKey, &pValue);
			return *this;
		}
	};

public:

	py_dict(PyObject* pDict, py_reference_type reftype) : py_shared_ptr(pDict, reftype) {}
	py_dict(const py_shared_ptr& pDict) : py_shared_ptr(pDict) {}
	py_dict(py_shared_ptr&& pDict) : py_shared_ptr(pDict) {}

	int size() {
		return (int)PyDict_Size(*this);
	}

	T operator[] (S key) const {
		return T(PyDict_GetItem(*this, key.get()), py_borrowed_ref);
	}

	iterator begin() const {
		return iterator(*this, false);
	}

	iterator end() const {
		return iterator(*this, true);
	}
};