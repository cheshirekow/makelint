if(CMAKE_GENERATOR STREQUAL "Unix Makefiles")
  add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/rst_manifest.txt
    COMMAND python -B ${CMAKE_SOURCE_DIR}/doc/find_rst.py
            --manifest-path ${CMAKE_CURRENT_BINARY_DIR}/rst_manifest.txt
            --touch ${CMAKE_SOURCE_DIR}/makelint
    DEPENDS ${CMAKE_SOURCE_DIR}/doc/find_rst.py
    COMMENT "Scanning RST for makelint")
endif()

add_custom_target(
  scanrst-makelint_docs
  COMMAND python -B ${CMAKE_SOURCE_DIR}/doc/find_rst.py
          --manifest-path ${CMAKE_CURRENT_BINARY_DIR}/rst_manifest.txt
          --touch ${CMAKE_SOURCE_DIR}/makelint
  DEPENDS ${CMAKE_SOURCE_DIR}/doc/find_rst.py
  BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/rst_manifest.txt
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Scanning RST for makelint")

add_custom_command(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/makelint_doc.stamp
  COMMAND env PYTHONPATH=${CMAKE_SOURCE_DIR} sphinx-build -M
          html ${CMAKE_CURRENT_SOURCE_DIR}
          ${CMAKE_CURRENT_BINARY_DIR}
  COMMAND touch
          ${CMAKE_CURRENT_BINARY_DIR}/makelint_doc.stamp
  DEPENDS ${CMAKE_SOURCE_DIR}/doc/conf.py
          ${CMAKE_CURRENT_BINARY_DIR}/rst_manifest.txt
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

add_custom_target(
  makelint_doc
  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/makelint_doc.stamp)

add_dependencies(doc makelint_doc)
