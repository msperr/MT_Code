#include "Python.h"

#include "SchedulingDecompApp.h"
#include "SchedulingDecompAlgo.h"
#include "AlpsDecompModel.h"
#include "AlpsTreeNode.h"
#include "Instance.h"
#include "simple_matrix.h"

#include "py_shared_ptr.h"
#include "py_string.h"
#include "py_dict.h"

#include <assert.h>

#ifndef DECOMP_INF_DEFINED
#define DECOMP_INF_DEFINED
double DecompInf = COIN_DBL_MAX;
#else
extern double DecompInf;
#endif

#ifdef _WIN32
#define DLLEXPORT extern "C" __declspec(dllexport)
#else
#define DLLEXPORT extern "C"
#endif

DLLEXPORT PyObject* Solve(PyObject* self, PyObject* args)
{

	py_dict<py_string, py_dict<py_string, py_object>> pParameters(PyTuple_GetItem(args, 0), py_borrowed_ref);
	Instance pInstance(py_object(PyTuple_GetItem(args, 1), py_borrowed_ref));
	py_object pInitialSolution(py_object(PyTuple_GetItem(args, 2), py_borrowed_ref));

	if (!pParameters || !pInstance || !pInitialSolution)
		return NULL;

	try {

		UtilParameters utilParam;
		for (auto section : pParameters)
			for (auto param : section.second)
				utilParam.Add(section.first, param.first, param.second.str());

		pInstance.analyse();

		SchedulingDecompApp sip(utilParam, pInstance, pInitialSolution);
		SchedulingAlgoPC* algo = new SchedulingAlgoPC(&sip, utilParam);
		AlpsDecompModel alpsModel(utilParam, algo);
		alpsModel.AlpsPar()->setEntry(AlpsParams::deleteDeadNode, false);
		alpsModel.solve();


		int status = alpsModel.getSolStatus();
		PyObject* pStatus;
		PyObject* pMessage = Py_None;
		/**
		LpStatusOptimal     “Optimal”      1
		LpStatusNotSolved   “Not Solved”   0
		LpStatusInfeasible  “Infeasible”  -1
		LpStatusUnbounded   “Unbounded”   -2
		LpStatusUndefined   “Undefined”   -3
		*/

		switch (status) {
		case AlpsExitStatusOptimal:
			pStatus = PyInt_FromLong(1);
			break;

		case AlpsExitStatusTimeLimit:
			pStatus = PyInt_FromLong(0);
			pMessage = PyString_FromString("Reached time limit");
			break;

		case AlpsExitStatusNodeLimit:
			pStatus = PyInt_FromLong(0);
			pMessage = PyString_FromString("Reached node limit");
			break;

		case AlpsExitStatusSolLimit:
			pStatus = PyInt_FromLong(0);
			pMessage = PyString_FromString("Reached sol limit");
			break;

		case AlpsExitStatusInfeasible:
			pStatus = PyInt_FromLong(-1);
			break;

		case AlpsExitStatusNoMemory:
			throw UtilException("Out of memory", "Solve", "DippySolve");

		case AlpsExitStatusFailed:
			throw UtilException("Solve failed", "Solve", "DippySolve");

		case AlpsExitStatusUnbounded:
			pStatus = PyInt_FromLong(-2);
			break;

		case AlpsExitStatusFeasible:
			throw UtilException("Feasible but not optimal", "Solve", "DippySolve");

		default:
			throw UtilException("Unknown solution status", "Solve", "DippySolve");
		}

		const DecompSolution* solution = alpsModel.getBestSolution();
		const double* values = solution->getValues();
		py_object pSolution = sip.exportSolution(values);
		Py_XINCREF(pSolution.get());

		delete algo;

		PyObject* pOutput = PyTuple_New(3);
		PyTuple_SetItem(pOutput, 0, pStatus);
		PyTuple_SetItem(pOutput, 1, pMessage);
		PyTuple_SetItem(pOutput, 2, pSolution.get());
		return pOutput;
	}
	catch (CoinError& ex) {
		std::cerr << "COIN Exception [ " << ex.message() << " ]" << " at " << ex.fileName() << ":L" << ex.lineNumber() << " in " << ex.className() << "::" << ex.methodName() << std::endl;
		return NULL;
	}

	Py_INCREF(Py_None);
	return Py_None;
}

DLLEXPORT PyObject* Build(PyObject* self, PyObject* pInstance)
{

	return Py_None;

	Instance inst(py_object(pInstance, py_borrowed_ref));
	inst.build();

	const int num_vertices = inst.num_vehicles + inst.num_trips;

	PyObject* pRefuelpoints = PyList_New(num_vertices);
	for (int s = 0; s < num_vertices; s++) {
		PyObject* pRow = PyList_New(num_vertices);
		for (int t = 0; t < num_vertices; t++)
			PyList_SET_ITEM(pRow, t, PyList_New(0));
		PyList_SET_ITEM(pRefuelpoints, s, pRow);
	}

	for (auto row = inst.arc_refuelpoints.begin(); row != inst.arc_refuelpoints.end(); ++row) {
		const int t = row.index();
		for (auto arc = row.begin(); arc != row.end(); ++arc) {
			const int s = arc.index();
			PyObject* pRefuelpointsST = PyList_GetItem(PyList_GetItem(pRefuelpoints, s), t);
			for (int r : *arc)
				PyList_Append(pRefuelpointsST, PyInt_FromLong(r));
		}
	}

	PyObject_SetAttrString(pInstance, "_paretorefuelpoints", pRefuelpoints);

	return Py_None;
}

DLLEXPORT PyObject* Analyse(PyObject* self, PyObject* pInstance)
{
	Instance inst(py_object(pInstance, py_borrowed_ref));
	inst.analyse();
	return Py_None;
}

static PyMethodDef methods[] = {
		{ "Solve", (PyCFunction) Solve, METH_VARARGS, NULL },
		{ "Build", (PyCFunction) Build, METH_O, NULL },
		{ "Analyse", (PyCFunction) Analyse, METH_O, NULL },
		{ NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initscheduling_cpp(void) {
	PyObject* pMod = Py_InitModule("scheduling_cpp", methods);
}