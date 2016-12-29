#include "py_int.h"

py_int::py_int(PyObject* pObject, py_reference_type reftype) : py_shared_ptr(pObject, reftype) {}

py_int::py_int(const py_shared_ptr& pObject) : py_shared_ptr(pObject) {}

py_int::py_int(py_shared_ptr&& pObject) : py_shared_ptr(pObject) {}

py_int::operator long() const {
	return PyInt_AsLong(*this);
}