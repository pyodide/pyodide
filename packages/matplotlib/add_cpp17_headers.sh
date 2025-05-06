#!/bin/bash

set -e

echo ">>> Starting script to add C++17 headers to Matplotlib sources <<<"

HEADERS_TO_INSERT="#include <variant>\\n#include <optional>\\n#include <string>\\n#include <vector>\\n#include <utility>\\n#include <type_traits>"
CHECK_MARKER_HEADER="#include <variant>"

TARGET_FILES=(
    "src/ft2font_wrapper.cpp"
    "src/ft2font.cpp"
    "src/_image_wrapper.cpp"
    "src/_backend_agg.cpp"
    "src/_backend_agg_wrapper.cpp"
    "src/_path_wrapper.cpp"
    "src/_backend_agg_basic_types.h"
    "src/_image_resample.h"
    "src/_enums.h"
    "src/_backend_agg.h"
    "src/_path.h"
)

for target_file in "${TARGET_FILES[@]}"; do
    echo "Processing file: ${target_file}"
    if [ -f "${target_file}" ]; then
        if grep -qF "${CHECK_MARKER_HEADER}" "${target_file}"; then
            echo "Headers might already be present in ${target_file}. Skipping addition."
        else
            echo "Adding C++17 headers to ${target_file}..."
            awk -v headers_block="${HEADERS_TO_INSERT}" 'BEGIN {print headers_block} {print $0}' "${target_file}" > "${target_file}.tmp"

            if [ $? -eq 0 ]; then
                mv "${target_file}.tmp" "${target_file}"
                echo "Successfully added headers to ${target_file}."
            else
                echo "ERROR: Failed to process ${target_file} with awk. Original file remains unchanged."
                rm -f "${target_file}.tmp"
                exit 1
            fi
        fi
    else
        echo "WARNING: Target file ${target_file} not found. Skipping."
    fi
    echo "----------------------------------------"
done

echo ">>> Finished adding C++17 headers. <<<"