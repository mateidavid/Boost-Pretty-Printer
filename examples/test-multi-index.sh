#!/bin/bash

if [ -x test-multi-index ] && [ test-multi-index -nt test-multi-index.cpp ]; then
    echo "test-multi-index: exists" >&2
else
    echo "test-multi-index: compiling" >&2
    g++ -g -std=c++0x -Wall -Wextra -o test-multi-index test-multi-index.cpp ||
    {
        echo "compilation failed" >&2
        exit 1
    }
fi
echo "test-multi-index: invoking gdb" >&2
gdb test-multi-index -x test-multi-index.gdb
