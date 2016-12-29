#pragma once

#include <assert.h>
#include <cuda_runtime.h>

template<typename T>
class simple_vector_base {

	template <typename> class simple_vector;

protected:

	int elements = 0;
	T* data = NULL;

	simple_vector_base(int elements) : elements(elements) {}

public:

	simple_vector_base(simple_vector_base<T>& other) : elements(other.elements), data(other.data) {}

	inline __device__ __host__ T& operator() (int i) const {
		assert(0 <= i && i < elements);
		return data[i];
	}
};

template<typename T>
class simple_vector: public simple_vector_base<T>{

public:

	simple_vector(int elements = 0) : simple_vector_base<T>(elements) {
		if (this->elements) {
			data = new T[this->elements];
			assert(data != NULL);
		}
	}

	~simple_vector() {
		if (data)
			delete[] data;
	}

	simple_vector(simple_vector<T>& other) : simple_vector(other.elements) {
		memcpy(data, other.data, other.elements * sizeof(T));
	}

	simple_vector(simple_vector<T>&& other) : simple_vector_base<T>(other) {
		new(&other) simple_vector<T>();
	}

	void resize(int elements) {
		this->~simple_vector();
		new(this) simple_vector<T>(elements);
	}

	void fill(T val) {
		std::fill_n(data, elements, val);
	}
};

// ############################################################################
// # original code
// ############################################################################

/*
#pragma once

#include <assert.h>
#include <cuda_runtime.h>

template<typename T>
class simple_vector_base {

	//template<typename, cudaMemoryType> friend class simple_vector;
	template <typename> class simple_vector;

protected:

	int elements = 0;
	T* data = NULL;

	simple_vector_base(int elements) : elements(elements) {}

public:

	simple_vector_base(simple_vector_base<T>& other) : elements(other.elements), data(other.data) {}

	//	inline __device__ __host__ T& operator() (int i) const {
	inline T& operator() (int i) const {
		assert(0 <= i && i < elements);
		return data[i];
	}
};

//template<typename T, cudaMemoryType type = cudaMemoryTypeHost>
//template<typename T>
//class simple_vector : public simple_vector_base<T> {
//
//};

template<typename T>
//class simple_vector<T, cudaMemoryTypeHost> : public simple_vector_base<T>{
class simple_vector : public simple_vector_base<T>{

public:

	simple_vector(int elements = 0) : simple_vector_base<T>(elements) {
		if (this->elements) {
			data = new T[this->elements];
			assert(data != NULL);
		}
	}

	~simple_vector() {
		if (data)
			delete[] data;
	}

	//	simple_vector(simple_vector<T, cudaMemoryTypeHost>& other) : simple_vector(other.elements) {
	simple_vector(simple_vector<T>& other) : simple_vector(other.elements) {
		memcpy(data, other.data, other.elements * sizeof(T));
	}

	//	simple_vector(simple_vector<T, cudaMemoryTypeDevice>& other) : simple_vector(other.elements) {
	//	simple_vector(simple_vector<T>& other) : simple_vector(other.elements) {
	//		cudaError_t cuda_error = cudaMemcpy(data, other.data, other.elements * sizeof(T), cudaMemcpyDeviceToHost);
	//		assert(cuda_error == cudaSuccess);
	//	}

	//	simple_vector(simple_vector<T, cudaMemoryTypeHost>&& other) : simple_vector_base<T>(other) {
	//		new(&other) simple_vector<T, cudaMemoryTypeHost>();
	//	}
	simple_vector(simple_vector<T>&& other) : simple_vector_base<T>(other) {
		new(&other) simple_vector<T>();
	}

	void resize(int elements) {
		this->~simple_vector();
		//		new(this) simple_vector<T, cudaMemoryTypeHost>(elements);
		new(this) simple_vector<T>(elements);
	}

	void fill(T val) {
		std::fill_n(data, elements, val);
	}
};

/*
template<typename T>
class simple_vector<T, cudaMemoryTypeDevice> : public simple_vector_base<T>{

public:

simple_vector(int elements = 0) : simple_vector_base<T>(elements) {
if (this->elements) {
cudaError_t cuda_error = cudaMalloc((void**)&data, this->elements * sizeof(T));
assert(cuda_error == cudaSuccess);
}
}

~simple_vector() {
if (data)
cudaFree(data);
}

template<cudaMemoryType type>
simple_vector(simple_vector<T, type>& other) : simple_vector(other.elements) {
cudaError_t cuda_error = cudaMemcpy(data, other.data, other.elements * sizeof(T), type == cudaMemoryTypeDevice ? cudaMemcpyDeviceToDevice : cudaMemcpyHostToDevice);
assert(cuda_error == cudaSuccess);
}

simple_vector(simple_vector<T, cudaMemoryTypeDevice>&& other) : simple_vector_base<T>(other) {
new(&other) simple_vector<T, cudaMemoryTypeDevice>();
}

void resize(int elements) {
this->~simple_vector();
new(this) simple_vector<T, cudaMemoryTypeDevice>(elements);
}
};
*/