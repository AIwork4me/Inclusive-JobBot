# Added via CMAKE_PROJECT_TOP_LEVEL_INCLUDES, leaving upstream files untouched.
function(ij06_attach_native_probe)
    add_executable(ij06-native-probe "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/native_probe.cpp")
    target_link_libraries(ij06-native-probe PRIVATE llama-common)
    target_compile_features(ij06-native-probe PRIVATE cxx_std_17)
endfunction()
cmake_language(DEFER CALL ij06_attach_native_probe)
