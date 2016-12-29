#pragma once

#include <memory>

#define MEASURETIME(start, result, code) \
	auto start = std::chrono::high_resolution_clock::now(); \
	code; \
	auto result = std::chrono::duration_cast<std::chrono::duration<double>>(std::chrono::high_resolution_clock::now() - start).count();

template<typename InputIterator, class UnaryPredicate>
bool all_of_iter(InputIterator first, InputIterator last, UnaryPredicate pred)
{
	while (first != last) {
		if (!pred(first)) return false;
		++first;
	}
	return true;
}

template<class T>
struct reversed {

	const T& range;

	reversed(const T& range) : range(range) {}

	typename T::reverse_iterator begin() const {
		return range.rbegin();
	}

	typename T::reverse_iterator end() const {
		return range.rend();
	}
};

template<class T>
struct range {

	struct iterator {

		T* value;
		const int step;

		iterator(T* value, int step) : value(value), step(step) {}

		bool operator!=(const range<T> other) {
			return value != other.value;
		}

		T operator*() const {
			return *value;
		}

		iterator& operator++() {
			value += step;
			return *this;
		}
	};

	const T* begin_value;
	const T* end_value;
	const int step;

	range(const T* begin, const T* end, int step = 1) : begin_value(begin), end_value(end), step(step) {}

	const iterator begin() const {
		return iterator(begin_value, step);
	}

	const iterator end() const {
		return iterator(end_value, step);
	}
};

template<class T>
struct singleton {

	const T& item;

	singleton(const T& item) : item(item) {}

	const T* begin() const {
		return &item;
	}

	const T* end() const {
		return &item + 1;
	}
};



char* asprintf(char* const _Format, ...);
std::unique_ptr<char[]> sprintf_a(char* const _Format, ...);