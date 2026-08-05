cmake_minimum_required(VERSION 3.10)
project(toio_description)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()

ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/hooks/toio_description.dsv.in")

install(
  DIRECTORY launch
            robot
            meshes
            DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # ament_copyright also requires CONTRIBUTING.md and a LICENSE file in a
  # layout it recognizes; skip it (the copyright test is skipped in
  # toio_ros2 as well)
  set(ament_cmake_copyright_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_urdf test/test_urdf.py)
endif()

ament_auto_package()
