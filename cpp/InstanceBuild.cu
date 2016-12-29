#include "Instance.h"

#include <cuda.h>
#include <cuda_runtime.h>
#include <cuda_runtime_api.h>
#include <device_launch_parameters.h>
#include <device_functions.h>
#include <helper_cuda.h>
#include <helper_timer.h>

#include "simple_vector.h"
#include "simple_matrix.h"

__global__ void calcParetoRefuelpoints(
	int ds,
	int dt,
	int num_vertices,
	int num_refuelpoints,
	double cost_per_meter,
	double fuel_per_meter,
	double refuel_per_second,
	simple_vector_base<double> vertex_starttime,
	simple_vector_base<double> vertex_finishtime,
	simple_matrix_base<double> arc_time,
	simple_matrix_base<double> arc_dist,
	simple_matrix_base<bool> output
	)
{

	extern __shared__ unsigned char mem[];

	volatile bool* dominance = (bool*)mem;
	double* time = (double*)(dominance + 4 * blockDim.x * blockDim.y); // use more memory in order to avoid bank conflicts
	double* phi_0 = time + num_refuelpoints;
	double* phi_1 = phi_0 + num_refuelpoints;
	double* phi_2 = phi_1 + num_refuelpoints;
	double* phi_3 = phi_2 + num_refuelpoints;

	const int s = ds + blockIdx.x;
	const int t = dt + blockIdx.y;

	const int tx = threadIdx.x;
	const int ty = threadIdx.y;

	if (s < num_vertices && t < num_vertices) {

		if (vertex_finishtime(s) + arc_time(s, t) <= vertex_starttime(t)) {

			for (int p = ty * blockDim.x + tx; p < num_refuelpoints; p += blockDim.x * blockDim.y) {
				const int r = num_vertices + p;
				const double time_r = vertex_starttime(t) - arc_time(r, t) - arc_time(s, r) - vertex_finishtime(s);
				const double dist_s_r = arc_dist(s, r);
				const double dist_r_t = arc_dist(r, t);
				time[p] = time_r;
				phi_0[p] = cost_per_meter * (dist_s_r + dist_r_t);
				phi_1[p] = fuel_per_meter * dist_s_r + max(-min(refuel_per_second * time_r, 1.0) + fuel_per_meter * dist_r_t, 0.0);
				phi_2[p] = max(fuel_per_meter * dist_s_r - min(refuel_per_second * time_r, 1.0), 0.0) + fuel_per_meter * dist_r_t;
				phi_3[p] = fuel_per_meter * dist_s_r - min(refuel_per_second * time_r, 1.0) + fuel_per_meter * dist_r_t;
			}

			__syncthreads();

			for (int p = ty; p < num_refuelpoints; p += blockDim.y) {
				
				if (time[p] < 0.0) {
					if (!tx)
						output(blockIdx.y * num_vertices + s, p) = true;
				} else {

					bool dominated = false;
					for (int q = tx; q < num_refuelpoints; q += blockDim.x) {
						const bool dominance_p_q = phi_0[p] <= phi_0[q] && phi_1[p] <= phi_1[q] && phi_2[p] <= phi_2[q] && phi_3[p] <= phi_3[q];
						const bool dominance_q_p = phi_0[p] >= phi_0[q] && phi_1[p] >= phi_1[q] && phi_2[p] >= phi_2[q] && phi_3[p] >= phi_3[q];
						dominated |= dominance_q_p && (p < q || !dominance_p_q);
					}
					dominance[(ty * blockDim.x + tx) << 2] = dominated;

					// use warp sync
					if (blockDim.x == 32) {
						if (tx < 16) {
							dominance[(ty * blockDim.x + tx) << 2] |= dominance[(ty * blockDim.x + tx + 16) << 2];
							dominance[(ty * blockDim.x + tx) << 2] |= dominance[(ty * blockDim.x + tx + 8) << 2];
							dominance[(ty * blockDim.x + tx) << 2] |= dominance[(ty * blockDim.x + tx + 4) << 2];
							dominance[(ty * blockDim.x + tx) << 2] |= dominance[(ty * blockDim.x + tx + 2) << 2];
							dominance[(ty * blockDim.x + tx) << 2] |= dominance[(ty * blockDim.x + tx + 1) << 2];
						}
					} else {
						if (tx < blockDim.x >> 1)
							for (unsigned int stride = blockDim.x >> 1; stride; stride >>= 1)
								dominance[(ty * blockDim.x + tx) << 2] |= dominance[(ty * blockDim.x + tx + stride) << 2];
					}

					if (!tx)
						output(blockIdx.y * num_vertices + s, p) = dominance[(ty * blockDim.x + tx) << 2];
				}
			}

		} else {
			for (int p = ty * blockDim.x + tx; p < num_refuelpoints; p += blockDim.x * blockDim.y)
				output(blockIdx.y * num_vertices + s, p) = true;
		}
	}
}

void Instance::build() {

	int devID = 0;

	cudaError_t cuda_error;
	cudaDeviceProp deviceProp;
	cuda_error = cudaGetDevice(&devID);
	assert(cuda_error == cudaSuccess);

	cuda_error = cudaGetDeviceProperties(&deviceProp, devID);
	assert(cuda_error == cudaSuccess);

	printf("Building instance on GPU Device %d: \"%s\" with compute capability %d.%d\n", devID, deviceProp.name, deviceProp.major, deviceProp.minor);

	int block_size = (deviceProp.major < 2) ? 16 : 32;
	int grid_size = 32;

	const int num_vertices = num_vehicles + num_trips;

	simple_matrix<double, cudaMemoryTypeDevice> d_arc_dist(arc_dist);
	simple_matrix<double, cudaMemoryTypeDevice> d_arc_time(arc_time);
//	simple_vector<double, cudaMemoryTypeDevice> d_vertex_starttime(vertex_starttime);
	simple_vector<double> d_vertex_starttime(vertex_starttime);
//	simple_vector<double, cudaMemoryTypeDevice> d_vertex_finishtime(vertex_finishtime);
	simple_vector<double> d_vertex_finishtime(vertex_finishtime);

	assert(num_vertices * grid_size * num_refuelpoints < deviceProp.totalGlobalMem);
	simple_matrix<bool, cudaMemoryTypeDevice> d_output(grid_size * num_vertices, num_refuelpoints);

	dim3 threads(block_size, block_size);
	dim3 grid(grid_size, grid_size);

	const int size = 4 * threads.x * threads.y * sizeof(bool) + 5 * num_refuelpoints * sizeof(double);
	assert(size < deviceProp.sharedMemPerBlock);



	int numel = 0;
	for (int t = 0; t < num_vertices; t++)
		for (int s = 0; s < num_vertices; s++)
			if ((vertex_customer(s) != vertex_customer(t)) && (vertex_finishtime(s) + arc_time(s, t) <= vertex_starttime(t)))
				numel++;

	arc_refuelpoints.resize(num_vertices, num_vertices, numel);


	StopWatchWin stopwatch;
	stopwatch.start();

	for (int dt = 0; dt < num_vertices; dt += grid_size) {
		for (int ds = 0; ds < num_vertices; ds += grid_size) {

			calcParetoRefuelpoints <<< grid, threads, size >>> (ds, dt, num_vertices, num_refuelpoints, cost_per_meter, fuel_per_meter, refuel_per_second, d_vertex_starttime, d_vertex_finishtime, d_arc_time, d_arc_dist, d_output);

			checkCudaErrors(cudaPeekAtLastError());
			checkCudaErrors(cudaDeviceSynchronize());

			const double percentage = (double) (dt * num_vertices + std::min(ds + grid_size, num_vertices) * std::min(grid_size, num_vertices - dt)) / num_vertices / num_vertices;
			printf("[%.*s%.*s] % 3.1f%% in %.1fs %d %d\r", 
				(int)(100 * percentage), "####################################################################################################",
				100 - (int)(100 * percentage), "                                                                                                    ",
				100.0 * percentage,
				stopwatch.getTime() / 1000.0, ds, dt);
		}

		simple_matrix<bool, cudaMemoryTypeHost> output(d_output);

		for (int t = dt; t < dt + grid_size && t < num_vertices; t++) {
			arc_refuelpoints.appendRow();
			for (int s = 0; s < num_vertices; s++) {
				if ((vertex_customer(s) != vertex_customer(t)) && (vertex_finishtime(s) + arc_time(s, t) <= vertex_starttime(t))) {
					auto& refuelpoints = arc_refuelpoints.appendElement(s);
					for (int r = 0; r < num_refuelpoints; r++)
						if (!output((t - dt) * num_vehicles + s, r))
							refuelpoints.push_back(r);
				}
			}
		}
	}
	stopwatch.stop();
	printf("\n");
}