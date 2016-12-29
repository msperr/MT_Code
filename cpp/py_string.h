#pragma once

#include "py_shared_ptr.h"

class py_string : public py_shared_ptr {

public:

	py_string(PyObject* pObject, py_reference_type reftype);
	py_string(const py_shared_ptr& pObject);
	py_string(py_shared_ptr&& pObject);

	operator char*() const;

};