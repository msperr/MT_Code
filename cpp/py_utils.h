#pragma once

#include "Python.h"
#include "py_shared_ptr.h"

#include "numpy/ndarrayobject.h"

#include <exception>

#define PyAssert(cond,msg) if(!cond) { PyErr_Print(); throw new std::exception(msg); }

template<typename T>
inline T PyArray_GET(py_shared_ptr& pObject, int i) {
	T* x = (T*)PyArray_GETPTR1(pObject.get(), i);
	return *(x);
}

template<typename T>
inline T PyArray_GET(py_shared_ptr& pObject, int i, int j) {
	T* x = (T*)PyArray_GETPTR2(pObject.get(), i, j);
	return *(x);
}

template<typename T>
inline T PyArray_GET(py_shared_ptr& pObject, int i, int j, int k) {
	return *((T*)PyArray_GETPTR3(pObject.get(), i, j, k));
}

template<typename T>
inline T PyArray_GET(PyObject* pObject, int i, int j, int k, int l) {
	return *((T*)PyArray_GETPTR4(pObject, i, j, k, l));
}

extern PyObject* pModuleTime;
extern PyObject* pFunctionMkTime;

double PyDateTime_AsDouble(PyObject* pDateTime);