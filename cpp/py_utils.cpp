#include "py_utils.h"

//

PyObject* pModuleTime = PyImport_ImportModule("time");
PyObject* pFunctionMkTime = PyObject_GetAttrString(pModuleTime, "mktime");

double PyDateTime_AsDouble(PyObject* pDateTime) {
	PyAssert(pDateTime, "PyDateTime2Double");
	PyObject* pTimeTuple = PyObject_CallMethod(pDateTime, "timetuple", NULL);
	PyAssert(pTimeTuple, "timetuple");
	PyObject* pFloat = PyObject_CallFunctionObjArgs(pFunctionMkTime, pTimeTuple, NULL);
	PyAssert(pFloat, "mktime");
	double f = PyFloat_AsDouble(pFloat);
	Py_XDECREF(pFloat);
	Py_XDECREF(pTimeTuple);
	return f;
}