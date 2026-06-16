#!/bin/bash
# Run this after every recompile to update all .so locations
BASE=/remote/pi313b/yuvaraj/class_public_free_f
BUILD=$BASE/python/build/lib.linux-x86_64-cpython-39
SRC=$BASE/python/classy.cpython-39-x86_64-linux-gnu.so

# Update build directory .so (top level)
cp $SRC $BUILD/classy.cpython-39-x86_64-linux-gnu.so

# Update build/classy/.so (what Cobaya actually imports)
cp $SRC $BUILD/classy/classy.cpython-39-x86_64-linux-gnu.so

# Ensure external data files are accessible from the classy package location
# (CLASS uses importlib.resources to find sBBN_2025.dat etc. relative to the .so)
if [ ! -L "$BUILD/classy/external" ]; then
    ln -s $BASE/external $BUILD/classy/external
    echo "Created external data symlink."
fi

echo "All .so locations updated."
