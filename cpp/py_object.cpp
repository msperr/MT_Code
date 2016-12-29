#include "py_object.h"

#include <cstring>

py_object::py_object(PyObject* pObject, py_reference_type reftype) : py_shared_ptr(pObject, reftype) {}

py_object::py_object(const py_shared_ptr& pObject) : py_shared_ptr(pObject) {}

py_object::py_object(py_shared_ptr&& pObject) : py_shared_ptr(pObject) {}

py_shared_ptr py_object::getAttr(const char* pAttrName) const {
	return py_shared_ptr(PyObject_GetAttrString(*this, pAttrName), py_new_ref);
}

py_shared_ptr py_object::callMethod(const char* method, const char* format, ...) {
	va_list args;
	va_start(args, format);
	const int n = std::strlen(format) + 3;
	char* tupleformat = new char[n];
	sprintf_s(tupleformat, n, "(%s)", format);
	py_shared_ptr pArgs(Py_VaBuildValue(tupleformat, args), py_new_ref);
	delete[] tupleformat;
	va_end(args);
	py_shared_ptr pMethod = getAttr(method);
	return py_shared_ptr(PyObject_Call(pMethod, pArgs, NULL), py_new_ref);
}

py_string py_object::str() {
	return py_string(PyObject_Str(*this), py_new_ref);
}