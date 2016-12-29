#include "utils.h"
#include <cstdarg>
#include <utility>
#include <memory>

char* asprintf(char* const _Format, ...) {
	va_list args;
	va_start(args, _Format);
	size_t size = _vscprintf(_Format, args) + 1;
	va_end(args);
	char* buffer = new char[size];
	va_start(args, _Format);
	vsprintf_s(buffer, size, _Format, args);
	va_end(args);
	buffer[size - 1] = '\0';
	return buffer;
}

std::unique_ptr<char[]> sprintf_a(char* const _Format, ...) {
	va_list args;
	va_start(args, _Format);
	size_t size = _vscprintf(_Format, args) + 1;
	va_end(args);
	char* buffer = new char[size];
	va_start(args, _Format);
	vsprintf_s(buffer, size, _Format, args);
	va_end(args);
	buffer[size - 1] = '\0';
	return std::move(std::unique_ptr<char[]>(buffer));
}