#include "py_shared_ptr.h"

class py_int : public py_shared_ptr {

public:

	py_int(PyObject* pObject, py_reference_type reftype);
	py_int(const py_shared_ptr& pObject);
	py_int(py_shared_ptr&& pObject);

	operator long() const;

};