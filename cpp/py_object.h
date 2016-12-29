#pragma once

#include "py_shared_ptr.h"
#include "py_string.h"

class py_object : public py_shared_ptr {

public:

	py_object(PyObject* pObject, py_reference_type reftype);
	py_object(const py_shared_ptr& pObject);
	py_object(py_shared_ptr&& pObject);

	py_shared_ptr getAttr(const char* pAttrName) const;

	py_shared_ptr callMethod(const char* method, const char* format, ...);

	py_string str();
};