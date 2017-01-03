#include "SchedulingDecompAlgo.h"
#include "SchedulingDecompApp.h"
#include "AlpsDecompNodeDesc.h"

#include "windows.h"

#include "utils.h"

#include "math.h"

SchedulingAlgoPC::SchedulingAlgoPC(DecompApp* app, UtilParameters& utilParam) : DecompAlgoPC(app, utilParam), branchOnNumberOfVehicles(utilParam.GetSetting("branchOnNumberOfVehicles", false, "CUSTOM")), branchOnLengthOfDuties(utilParam.GetSetting("branchOnLengthOfDuties", false, "CUSTOM")), branchOnAlternativeTrips(utilParam.GetSetting("branchOnAlternativeTrips", false, "CUSTOM")) 
{
	printf("SchedulingAlgoPC");
}

DecompStatus SchedulingAlgoPC::processNode(const AlpsDecompTreeNode* node, const double globalLB, const double globalUB)
{

	SchedulingDecompApp* app = (SchedulingDecompApp*)getDecompApp();

	auto column_names = app->m_modelCore.getModel()->getColNames();

	auto lower_bounds = app->m_modelCore.getModel()->getColLB();
	auto upper_bounds = app->m_modelCore.getModel()->getColUB();

	const int index = node->getIndex();
	const AlpsDecompNodeDesc* desc = (AlpsDecompNodeDesc*)node->getDesc();

	auto node_lower_bounds = desc->getLowerBounds();
	auto node_upper_bounds = desc->getUpperBounds();

	for (int i = 0; i < app->m_modelCore.getModel()->getNumCols(); i++) {
		if (node_lower_bounds[i] != lower_bounds[i] || node_upper_bounds[i] != upper_bounds[i]) {
			if (node_lower_bounds[i] == node_upper_bounds[i])
				printf("%s = %f\n", column_names[i], node_upper_bounds[i]);
			else
				printf("%f <= %s <= %f\n", node_lower_bounds[i], column_names[i], node_upper_bounds[i]);
		}
	}

	//

	app->history.clear();

	return DecompAlgoPC::processNode(node, globalLB, globalUB);
}

void SchedulingAlgoPC::postProcessNode(const AlpsDecompTreeNode* node, DecompStatus decompStatus) {

	const char* DecompStatusStr[] = { "STATUS_FEASIBLE", "STATUS_IP_FEASIBLE", "STATUS_INFEASIBLE", "STATUS_UNKNOWN" };

	SchedulingDecompApp* app = (SchedulingDecompApp*)getDecompApp();
	AlpsDecompNodeDesc* desc = dynamic_cast<AlpsDecompNodeDesc*> (node->getDesc());

	desc->decompStatus = decompStatus;

	int noninteger = 0;
	int nonzero = 0;
	const double* xhat = getXhat();
	for (int i = 0; i < app->inst.num_vehicles; i++) {
		for (int j = 0; j < app->inst.num_trips; j++) {
			if (xhat[app->indexY(i, j)] > DecompEpsilon)
				nonzero++;
			if (abs(xhat[app->indexY(i, j)] - round(xhat[app->indexY(i, j)])) > DecompEpsilon)
				noninteger++;
		}
	}

	app->logfile << globalTimer.getRealTime() << " "
		<< node->getIndex() << " "
		<< 0 << " "
		<< getMasterOSI()->getNumCols() << " "
		<< getObjBestBoundLB() << " "
		<< getObjBestBoundUB() << " "
		<< getMasterObjValue() << " "
		<< DecompStatusStr[decompStatus] << " "
		<< 0 << " "
		<< 0 << " "
		<< nonzero << " "
		<< noninteger << " "
		<< std::endl;

	desc->bestlp = getMasterObjValue();
	desc->bestip = getObjBestBoundUB();

	//const AlpsDecompTreeNode* root = node;
	//while (root->getParent())
	//	root = (AlpsDecompTreeNode*) root->getParent();
	//printBranchAndBoundTreeNode(root, 0);
}

bool SchedulingAlgoPC::chooseBranchSet(std::vector< std::pair<int, double> >& downBranchLB, std::vector< std::pair<int, double> >& downBranchUB, std::vector< std::pair<int, double> >& upBranchLB, std::vector< std::pair<int, double> >& upBranchUB)
{

	const SchedulingDecompApp* app = (SchedulingDecompApp*) getDecompApp();
	const Instance& inst = app->inst;
	const AlpsDecompTreeNode* node = (AlpsDecompTreeNode*) getCurrentNode();

	//

	std::unique_ptr<char[]> basename(sprintf_a("%s.xhat.%03d", (const char*)py_string(app->inst.getAttr("_basename")), node->getIndex()));
	app->exportSolutionTexCompact(basename.get(), m_xhat);

	//

	if (branchOnNumberOfVehicles) {

		const double sum_v = m_xhat[app->indexSumV()];
		if (abs(sum_v - round(sum_v)) > DecompEpsilon) {

			m_branchingImplementation = DecompBranchInMaster;

			downBranchUB.push_back(std::pair<int, double>(app->indexSumV(), floor(sum_v)));
			upBranchLB.push_back(std::pair<int, double>(app->indexSumV(), ceil(sum_v)));

			printf("Branching on %s = %f\n", m_modelCore.getModel()->colNames[app->indexSumV()], sum_v);
			return true;
		}
	}

	//

	if (branchOnAlternativeTrips) {

		int branch_j = -1;
		double branch_dist = DecompEpsilon;
		for (int j = 0; j < app->inst.num_trips; j++) {
			const double w = m_xhat[app->indexW(j)];
			const double dist = abs(w - round(w));
			if (dist > branch_dist) {
				branch_j = j;
				branch_dist = dist;
			}
		}

		if (branch_j + 1) {

			m_branchingImplementation = DecompBranchInSubproblem;

			downBranchUB.push_back(std::pair<int, double>(app->indexW(branch_j), 0.0));
			for (int v = 0; v < app->inst.num_vehicles; v++)
				downBranchUB.push_back(std::pair<int, double>(app->indexY(v, branch_j), 0.0));

			upBranchLB.push_back(std::pair<int, double>(app->indexW(branch_j), 1.0));
			for (int t : inst.customer_vertices(inst.vertex_customer(inst.num_vehicles + branch_j))) {
				if (t - inst.num_vehicles != branch_j) {
					upBranchUB.push_back(std::pair<int, double>(app->indexW(t - inst.num_vehicles), 0.0));
					for (int v = 0; v < app->inst.num_vehicles; v++)
						upBranchUB.push_back(std::pair<int, double>(app->indexY(v, t - inst.num_vehicles), 0.0));
				}
			}

			printf("Branching on %s = %f\n", m_modelCore.getModel()->colNames[app->indexW(branch_j)], m_xhat[app->indexW(branch_j)]);
			return true;
		}
	}

	//

	if (branchOnLengthOfDuties) {

		int branch_i = -1;
		double branch_dist = DecompEpsilon;

		for (int i = 0; i < app->inst.num_customers; i++) {
			const double r = m_xhat[app->indexR(i)];
			const double dist = abs(r - round(r));
			if (dist > branch_dist) {
				branch_i = i;
				branch_dist = dist;
			}
		}

		if (branch_i + 1) {

			m_branchingImplementation = DecompBranchInSubproblem;

			downBranchUB.push_back(std::pair<int, double>(app->indexR(branch_i), floor(m_xhat[app->indexR(branch_i)])));
			upBranchLB.push_back(std::pair<int, double>(app->indexR(branch_i), ceil(m_xhat[app->indexR(branch_i)])));

			printf("Branching on %s = %f\n", m_modelCore.getModel()->colNames[app->indexR(branch_i)], m_xhat[app->indexR(branch_i)]);
			return true;
		}
	}

	//

	int branch_i = -1;
	int branch_j = -1;
	double branch_dist = DecompEpsilon;

	for (int i = 0; i < app->inst.num_vehicles; i++) {
		for (int j = 0; j < app->inst.num_trips; j++) {
			const double y = m_xhat[app->indexY(i, j)];
			const double dist = abs(y - round(y));
			if (dist > branch_dist) {
				branch_i = i;
				branch_j = j;
				branch_dist = dist;
			}
		}
	}

	if (branch_i + 1 && branch_j + 1) {

		m_branchingImplementation = DecompBranchInSubproblem;

		downBranchUB.push_back(std::pair<int, double>(app->indexY(branch_i, branch_j), 0.0));
		upBranchLB.push_back(std::pair<int, double>(app->indexY(branch_i, branch_j), 1.0));

		printf("Branching on %s = %f\n", m_modelCore.getModel()->colNames[app->indexY(branch_i, branch_j)], m_xhat[app->indexY(branch_i, branch_j)]);
		return true;
	}

	//

	if (this->DecompAlgo::chooseBranchSet(downBranchLB, downBranchUB, upBranchLB, upBranchUB))
		throw new std::exception("Branching error");
	return false;
}

void SchedulingAlgoPC::postProcessBranch(DecompStatus decompStatus) 
{
}


void SchedulingAlgoPC::exportProtocolTex(const AlpsDecompTreeNode* root) {

	if (hTexProcess) {
		TerminateProcess(hTexProcess, 0);
		hTexProcess = NULL;
	}


	const SchedulingDecompApp* app = (SchedulingDecompApp*)getDecompApp();

	std::unique_ptr<char[]> filenamebbtree(sprintf_a("%s.bbtree.tex", (const char*)py_string(app->inst.getAttr("_basename"))));
	exportBranchAndBoundTreeTex(filenamebbtree.get(), root);

	STARTUPINFO si;
	PROCESS_INFORMATION pi;
	memset(&si, 0, sizeof(si));
	memset(&pi, 0, sizeof(pi));
	si.cb = sizeof(si);

	std::unique_ptr<char[]> cmdline = sprintf_a("pdflatex.exe -extra-mem-bot=10000000 -extra-mem-bot=10000000-interaction=nonstopmode -quiet -enable-write18 -job-name=\"%s\" output", (const char*)py_string(app->inst.getAttr("_basename")));
	CreateProcess(NULL, cmdline.get(), NULL, NULL, false, CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
	hTexProcess = pi.hProcess;
}

void SchedulingAlgoPC::exportBranchAndBoundTreeTex(const char* filename, const AlpsDecompTreeNode* root) {

	std::fstream f;
	f.open(filename, std::fstream::out);
	f << "\\documentclass[tikz, border = 10pt]{standalone}" << std::endl;
	f << "\\usetikzlibrary{graphdrawing}" << std::endl;
	f << "\\usetikzlibrary{graphs}" << std::endl;
	f << "\\usegdlibrary{trees}" << std::endl;
	f << "\\usepackage{amssymb}" << std::endl;
	f << "\\begin{document}" << std::endl;
	f << "\\begin{tikzpicture}[>= stealth, every node/.style={circle,draw=gray}";
	f << ", candidate/.append style={}";
	f << ", evaluated/.append style={}";
	f << ", pregnant/.append style={fill=gray}";
	f << ", branched/.append style={}";
	f << ", fathomed/.append style={draw=green}";
	f << ", discarded/.append style={draw=red}";
	f << ", lpfeasible/.append style={}";
	f << ", ipfeasible/.append style={fill=green}";
	f << ", infeasible/.append style={fill=red}";
	f << ", unknown/.append style={fill=yellow}";
	f << ", hv/.append style={to path={-| (\\tikztotarget) \\tikztonodes}}";
	f << "]" << std::endl;
	f << "\\graph[tree layout,grow=down,fresh nodes,level distance = 0.5in,sibling distance=0.5in, edges={nodes={rectangle,draw=none,anchor=mid,fill=white}}]" << std::endl;
	f << "{" << std::endl;
	exportBranchAndBoundTreeTexNode(f, root);
	f << "};" << std::endl;
	f << "\\end{tikzpicture}" << std::endl;
	f << "\\end{document}" << std::endl;
	f.close();
}

void SchedulingAlgoPC::exportBranchAndBoundTreeTexNode(std::fstream& f, const AlpsDecompTreeNode* node) {

	const char* AlpsNodeStatusStr[] = { "candidate", "evaluated", "pregnant", "branched", "fathomed", "discarded" };
	const char* DecompStatusStr[] = { "lpfeasible", "ipfeasible", "infeasible", "unknown" };

	const SchedulingDecompApp* app = (SchedulingDecompApp*) getDecompApp();
	const AlpsDecompNodeDesc* desc = (AlpsDecompNodeDesc*) node->getDesc();
	const AlpsDecompTreeNode* parent = (AlpsDecompTreeNode*) node->getParent();
	
	f << node->getIndex() << "[" << AlpsNodeStatusStr[node->getStatus()] << "," << DecompStatusStr[desc->decompStatus];


	if (parent) {
		if (parent->getNumChildren() > 1)
			f << ",>hv,>edge node={node[near end]{\\tiny $";
		else
			f << ",>edge node={node[]{\\tiny $";
		const int branchedvar = parent->getBranchedVar();
		if (branchedvar + 1) {
			f << app->tex_column_names[branchedvar];
			if (desc->getBranchedDir() > 0)
				f << " \\ge " << std::fixed << std::setprecision(0) << (desc->getLowerBounds()[branchedvar] + DecompEpsilon);
			else
				f << " \\le " << std::fixed << std::setprecision(0) << (desc->getUpperBounds()[branchedvar] + DecompEpsilon);
		}
		f << "$}}";
	}

	f << ",label={[xshift=-4pt,align=left]right:\\tiny " << std::fixed << std::setprecision(2) << desc->bestip << "\\\\[-0.5em]\\tiny " << std::fixed << std::setprecision(2) << desc->bestlp << "}";

	f << "] -> {";

	if (node->getNumChildren()) {
		for (int i = 0; i < node->getNumChildren(); i++) {
			if (i)
				f << ",";
			exportBranchAndBoundTreeTexNode(f, (AlpsDecompTreeNode*)node->getChild(i));
		}
	} else {
		f << "\"\"[>draw=none, draw=none, fill=none],";
		f << "\"\"[>draw=none, draw=none, fill=none]";
	}

	f << "}" << std::endl;
}

void SchedulingAlgoPC::finish(const AlpsDecompTreeNode* root) {
	exportProtocolTex(root);
}



void SchedulingAlgoPC::printBranchAndBoundTreeNode(const AlpsDecompTreeNode* node, int depth) {

	const char* AlpsNodeStatusStr[] = { "candidate", "evaluated", "pregnant", "branched", "fathomed", "discarded" };
	const char* DecompStatusStr[] = { "lpfeasible", "ipfeasible", "infeasible", "unknown" };

	const SchedulingDecompApp* app = (SchedulingDecompApp*)getDecompApp();
	const AlpsDecompNodeDesc* desc = (AlpsDecompNodeDesc*)node->getDesc();
	const AlpsDecompTreeNode* parent = (AlpsDecompTreeNode*)node->getParent();

	for (int i = 0; i < depth; i++)
		printf("  ");
	printf("%d [%s,%s]", node->getIndex(), AlpsNodeStatusStr[node->getStatus()], DecompStatusStr[desc->decompStatus]);

	if (node->getNumChildren()) {

		printf(" {\n");

		for (int i = 0; i < node->getNumChildren(); i++)
			printBranchAndBoundTreeNode((AlpsDecompTreeNode*)node->getChild(i), depth + 1);

		for (int i = 0; i < depth; i++)
			printf("  ");
		printf("}\n");
	}
	else {
		printf("\n");
	}
}

void SchedulingAlgoPC::setMasterBounds(const double* lbs, const double* ubs)
{
	printf("setMasterBounds\n");

	DecompConstraintSet* modelCore = m_modelCore.getModel();

	//

	const int nCols = modelCore->getNumCols();
	double* denseS = new double[nCols];

	for (auto var : m_vars) {

		const int masterColIndex = var->getColMasterIndex();
		assert(isMasterColStructural(masterColIndex));
		auto mit = m_modelRelax.find(var->getBlockId());
		assert(mit != m_modelRelax.end());

		if (!var->doesSatisfyBounds(nCols, denseS, mit->second, lbs, ubs)) {
			m_masterSI->setColBounds(masterColIndex, 0.0, 0.0);
		} else {
			m_masterSI->setColBounds(masterColIndex, 0.0, m_infinity);
		}
	}

	UTIL_DELARR(denseS);

	//

	const int  nIntVars = modelCore->getNumInts();
	const int* integerVars = modelCore->getIntegerVars();

	for (int c = 0; c < nIntVars; c++) {
		const int coreColIndex = integerVars[c];
		if (std::find(m_masterOnlyCols.begin(), m_masterOnlyCols.end(), coreColIndex) != m_masterOnlyCols.end())
			m_masterSI->setColBounds(m_masterOnlyColsMap[coreColIndex], lbs[coreColIndex], ubs[coreColIndex]);
	}
}