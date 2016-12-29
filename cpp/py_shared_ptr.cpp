#include "py_shared_ptr.h"

py_shared_ptr::py_shared_ptr() : pObject(NULL) {
}

py_shared_ptr::py_shared_ptr(PyObject* pObject, py_reference_type reftype) : py_shared_ptr() {
	reset(pObject, reftype);
}

py_shared_ptr::py_shared_ptr(const py_shared_ptr& other) : py_shared_ptr() {
	reset(other.pObject, py_borrowed_ref);
}

py_shared_ptr::py_shared_ptr(py_shared_ptr&& other) : py_shared_ptr() {
	reset(other.pObject, py_new_ref);
	other.pObject = NULL;
}

py_shared_ptr::~py_shared_ptr() {
	reset();
}

py_shared_ptr& py_shared_ptr::operator=(const py_shared_ptr& rhs) {
	reset(rhs.pObject, py_borrowed_ref);
	return *this;
}

py_shared_ptr& py_shared_ptr::operator=(py_shared_ptr&& rhs) {
	reset(rhs.pObject, py_new_ref);
	rhs.pObject = NULL;
	return *this;
}

void py_shared_ptr::reset() {
	Py_XDECREF(this->pObject);
	this->pObject = NULL;
}

void py_shared_ptr::reset(PyObject* pObject, py_reference_type reftype) {
	Py_XDECREF(this->pObject);
	this->pObject = pObject;
	if (reftype == py_borrowed_ref)
		Py_XINCREF(this->pObject);
}

void py_shared_ptr::swap(py_shared_ptr& other) {
	PyObject* pObject = other.pObject;
	other.pObject = this->pObject;
	this->pObject = pObject;
}


py_shared_ptr::operator PyObject*() const {
	return get();
}

PyObject* py_shared_ptr::get() const {
	return pObject;
}

PyObject& py_shared_ptr::operator*() const {
	return *pObject;
}

PyObject* py_shared_ptr::operator->() const {
	return pObject;
}

py_shared_ptr::operator bool() const {
	return !!pObject;
}