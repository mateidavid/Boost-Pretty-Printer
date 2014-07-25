#!/bin/bash

if [ -x test-other ] && [ test-other -nt test-other.cpp ]; then
    echo "test-other: exists" >&2
else
    echo "test-other: compiling" >&2
    g++ -O0 -g3 -fno-inline -std=c++11 -Wall -Wextra -pedantic -o test-other test-other.cpp ||
    {
        echo "compilation failed" >&2
        exit 1
    }
fi
echo "test-other: invoking gdb" >&2
gdb test-other -x test-other.gdb
