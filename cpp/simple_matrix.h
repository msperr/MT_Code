#pragma once

#include <assert.h>
//#include <cuda_runtime.h>

#include "utils.h"

template<typename T>
class simple_matrix_base {

	template<typename, cudaMemoryType> friend class simple_matrix;

protected:

	int rows = 0;
	int cols = 0;
	int stride = 0;
	T* data = NULL;

	simple_matrix_base(int rows, int cols, int stride) : rows(rows), cols(cols), stride(stride ? stride : cols) {}

public:

	simple_matrix_base(simple_matrix_base<T>& other) : rows(other.rows), cols(other.cols), stride(other.stride), data(other.data) {}

	inline __device__ __host__ T& operator() (int i, int j) const {
		assert(0 <= i && i < rows && 0 <= j && j < cols);
		return data[i * stride + j];
	}

	range<T> row(int i) {
		assert(0 <= i && i < rows);
		return range<T>(data + i * stride, data + (i + 1) * stride);
	}

	range<T> col(int j) {
		assert(0 <= j && j < cols);
		return range<T>(data + j, data + rows * stride + j, stride);
	}
};

template<typename T, cudaMemoryType type = cudaMemoryTypeHost>
class simple_matrix : public simple_matrix_base<T> {

};

template<typename T>
class simple_matrix<T, cudaMemoryTypeHost> : public simple_matrix_base<T>{

public:

	simple_matrix(int rows = 0, int cols = 0, int stride = 0) : simple_matrix_base<T>(rows, cols, stride) {
		const int size = this->rows * this->stride;
		if (size) {
			data = new T[size];
			assert(data != NULL);
		}
	}

	~simple_matrix() {
		if (data)
			delete[] data;
	}

	simple_matrix(simple_matrix<T, cudaMemoryTypeHost>& other) : simple_matrix(other.rows, other.cols, other.stride) {
		memcpy(data, other.data, other.rows * other.stride * sizeof(T));
	}

	simple_matrix(simple_matrix<T, cudaMemoryTypeDevice>& other) : simple_matrix(other.rows, other.cols, other.stride) {
		cudaError cuda_error = cudaMemcpy(data, other.data, other.rows * other.stride * sizeof(T), cudaMemcpyDeviceToHost);
		assert(cuda_error == cudaSuccess);
	}

	simple_matrix(simple_matrix<T, cudaMemoryTypeHost>&& other) : simple_matrix_base<T>(other) {
		new(&other) simple_matrix<T, cudaMemoryTypeHost>();
	}

	void resize(int rows, int cols, int stride = 0) {
		this->~simple_matrix();
		new(this) simple_matrix<T, cudaMemoryTypeHost>(rows, cols, stride);
	}

	void fill(T val) {
		std::fill_n(data, rows * stride, val);
	}
};

template<typename T>
class simple_matrix<T, cudaMemoryTypeDevice> : public simple_matrix_base<T>{

public:

	simple_matrix(int rows = 0, int cols = 0, int stride = 0) : simple_matrix_base<T>(rows, cols, stride) {
		const int size = this->rows * this->stride;
		if (size) {
			cudaError_t cuda_error = cudaMalloc((void**)&data, size * sizeof(T));
			assert(cuda_error == cudaSuccess);
		}
	}

	~simple_matrix() {
		if (data)
			cudaFree(data);
	}

	template<cudaMemoryType type>
	simple_matrix(simple_matrix<T, type>& other) : simple_matrix(other.rows, other.cols, other.stride) {
		cudaError_t cuda_error = cudaMemcpy(data, other.data, other.rows * other.stride * sizeof(T), type == cudaMemoryTypeDevice ? cudaMemcpyDeviceToDevice : cudaMemcpyHostToDevice);
		assert(cuda_error == cudaSuccess);
	}

	simple_matrix(simple_matrix<T, cudaMemoryTypeDevice>&& other) : simple_matrix_base<T>(other) {
		new(&other) simple_matrix<T, cudaMemoryTypeDevice>();
	}

	void resize(int rows, int cols, int stride = 0) {
		this->~simple_matrix();
		new(this) simple_matrix<T, cudaMemoryTypeDevice>(rows, cols, stride);
	}
};