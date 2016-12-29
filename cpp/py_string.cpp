#include "py_string.h"

py_string::py_string(PyObject* pObject, py_reference_type reftype) : py_shared_ptr(pObject, reftype) {}

py_string::py_string(const py_shared_ptr& pObject) : py_shared_ptr(pObject) {}

py_string::py_string(py_shared_ptr&& pObject) : py_shared_ptr(pObject) {}

py_string::operator char*() const {
	return PyString_AsString(*this);
}