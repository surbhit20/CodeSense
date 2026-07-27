.PHONY: build clean run

# Compile the C++17 scanner extension into a shared library
CXX      ?= c++
SDK_PATH := $(shell xcrun --sdk macosx15.4 --show-sdk-path 2>/dev/null || xcrun --sdk macosx --show-sdk-path)
CXX_INC  := $(SDK_PATH)/usr/include/c++/v1

build:
	$(CXX) -O2 -std=c++17 -I$(CXX_INC) -shared -fPIC -o src/libscanner.so src/scanner.cpp

clean:
	rm -f src/libscanner.so src/__pycache__/*.pyc

# Run the Chainlit app (build scanner first for best performance)
run: build
	chainlit run app.py --watch
