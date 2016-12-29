#pragma once

#include "DecompAlgoPC.h"

#include <vector>

using std::vector;

class SchedulingAlgoPC : public DecompAlgoPC {

	friend class SchedulingDecompApp;

public:

	const bool branchOnNumberOfVehicles = false;
	const bool branchOnLengthOfDuties = false;
	const bool branchOnAlternativeTrips = false;

public:

	SchedulingAlgoPC(DecompApp* app, UtilParameters& utilParam);

	//

	virtual void setMasterBounds(const double* lbs, const double* ubs);

	virtual DecompStatus processNode(const AlpsDecompTreeNode* node, const double globalLB, const double globalUB);
	virtual void postProcessNode(const AlpsDecompTreeNode* node, DecompStatus decompStatus);

	virtual bool chooseBranchSet(std::vector< std::pair<int, double> >& downBranchLB, std::vector< std::pair<int, double> >& downBranchUB, std::vector< std::pair<int, double> >& upBranchLB, std::vector< std::pair<int, double> >& upBranchUB);
	virtual void postProcessBranch(DecompStatus decompStatus);

	virtual void finish(const AlpsDecompTreeNode* root);

	//

	void exportProtocolTex(const AlpsDecompTreeNode* root);

	void printBranchAndBoundTreeNode(const AlpsDecompTreeNode* node, int depth);

private:

	void* hTexProcess;

	void exportBranchAndBoundTreeTex(const char* filename, const AlpsDecompTreeNode* root);
	void exportBranchAndBoundTreeTexNode(std::fstream& f, const AlpsDecompTreeNode* node);
};