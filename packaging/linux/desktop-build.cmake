# Included at project() time; defer registration until the mixxx target exists.
include_guard(GLOBAL)

function(nautic_register_desktop_build)
  if(NOT TARGET mixxx OR NOT UNIX OR APPLE)
    return()
  endif()
  find_program(NAUTIC_DESKTOP_PYTHON NAMES python3 REQUIRED)
  get_filename_component(nautic_work "${CMAKE_BINARY_DIR}" DIRECTORY)
  set(nautic_linux "${CMAKE_CURRENT_FUNCTION_LIST_DIR}")
  get_filename_component(nautic_project "${nautic_linux}/../.." ABSOLUTE)
  file(GLOB_RECURSE nautic_desktop_inputs CONFIGURE_DEPENDS
    "${nautic_project}/controllers/*" "${nautic_project}/skins/XDJ_RX3_Mixxx/*"
    "${nautic_project}/effects/chains/*" "${nautic_project}/profile/*"
    "${nautic_linux}/*.py")
  set_property(TARGET mixxx APPEND PROPERTY LINK_DEPENDS ${nautic_desktop_inputs})
  add_custom_command(TARGET mixxx POST_BUILD
    COMMAND "${NAUTIC_DESKTOP_PYTHON}" "${nautic_linux}/desktop.py"
      --publish-build "${nautic_work}"
    VERBATIM)
endfunction()

cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL nautic_register_desktop_build)
