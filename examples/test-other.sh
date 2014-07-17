#!/bin/bash

if [ -x test-other ] && [ test-other -nt test-other.cpp ]; then
    echo "test-other: exists" >&2
else
    echo "test-other: compiling" >&2
    g++ -g -std=c++0x -Wall -Wextra -o test-other test-other.cpp ||
    {
        echo "compilation failed" >&2
        exit 1
    }
fi
echo "test-other: invoking gdb" >&2
gdb test-other -x test-other.gdb
