#pragma once

#include "Python.h"

enum py_reference_type {
	py_new_ref,
	py_borrowed_ref
};

class py_shared_ptr {

private:

	PyObject* pObject;

public:

	py_shared_ptr();
	py_shared_ptr(PyObject* pObject, py_reference_type reftype);
	py_shared_ptr(const py_shared_ptr& other);
	py_shared_ptr(py_shared_ptr&& other);

	~py_shared_ptr();

	py_shared_ptr& operator=(const py_shared_ptr& rhs);
	py_shared_ptr& operator=(py_shared_ptr&& rhs);

	void reset();
	void reset(PyObject* pObject, py_reference_type reftype);
	void swap(py_shared_ptr& other);
	PyObject* get() const;

	operator PyObject*() const;
	PyObject& operator*() const;
	PyObject* operator->() const;
	operator bool() const;
};