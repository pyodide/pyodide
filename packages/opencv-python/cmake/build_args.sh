#!/bin/bash

export CMAKE_ARGS=" \
-DCMAKE_TOOLCHAIN_FILE=$PYODIDE_CMAKE_TOOLCHAIN_FILE \
-DPYTHON3_INCLUDE_PATH=$PYTHONINCLUDE \
-DPYTHON3_LIBRARY=$PYTHONINCLUDE/../libpython$PYMAJOR.$PYMINOR.a \
-DPYTHON3_VERSION_MAJOR=$PYMAJOR \
-DPYTHON3_VERSION_MINOR=$PYMINOR \
-DPYTHON3_NUMPY_INCLUDE_DIRS=$NUMPY_INCLUDE_DIR \
\
-DWITH_ADE=ON \
-DWITH_JPEG=ON \
-DWITH_PNG=ON \
-DWITH_WEBP=ON \
-DBUILD_WEBP=OFF \
-DWEBP_INCLUDE_DIR=$WASM_LIBRARY_DIR/include \
-DWEBP_LIBRARY=$WASM_LIBRARY_DIR/lib/libwebp.a \
-DWITH_TIFF=ON \
-DBUILD_TIFF=OFF \
-DTIFF_INCLUDE_DIR=$WASM_LIBRARY_DIR/include \
-DTIFF_LIBRARY=$WASM_LIBRARY_DIR/lib/libtiff.a \
\
-DBUILD_opencv_python3=ON \
-DBUILD_opencv_world=ON \
-DBUILD_opencv_imgcodecs=ON \
-DBUILD_opencv_videoio=ON \
-DBUILD_opencv_gapi=ON \
-DBUILD_opencv_photo=ON \
-DBUILD_opencv_stitching=ON \
-DBUILD_opencv_highgui=ON \
-DBUILD_opencv_features2d=ON \
-DBUILD_opencv_flann=ON \
-DBUILD_opencv_calib3d=ON \
-DBUILD_opencv_dnn=ON \
-DBUILD_opencv_ml=ON \
-DBUILD_opencv_objdetect=ON \
-DWITH_OPENCL=OFF \
-DOPENCV_DNN_OPENCL=OFF \
-DWITH_PROTOBUF=ON \
-DWITH_FFMPEG=ON \
\
-DPYTHON3_EXECUTABLE=python \
-DPYTHON3_LIMITED_API=ON \
-DPYTHON_DEFAULT_EXECUTABLE=python \
-DENABLE_PIC=FALSE \
-DCMAKE_BUILD_TYPE=Release \
-DCPU_BASELINE='' \
-DCPU_DISPATCH='' \
-DCV_TRACE=OFF \
-DBUILD_SHARED_LIBS=OFF \
-DWITH_1394=OFF \
-DWITH_VTK=OFF \
-DWITH_EIGEN=OFF \
-DWITH_GSTREAMER=OFF \
-DWITH_GTK=OFF \
-DWITH_GTK_2_X=OFF \
-DWITH_QT=OFF \
-DWITH_IPP=OFF \
-DWITH_JASPER=OFF \
-DWITH_OPENJPEG=OFF \
-DWITH_OPENEXR=OFF \
-DWITH_OPENGL=OFF \
-DWITH_OPENVX=OFF \
-DWITH_OPENNI=OFF \
-DWITH_OPENNI2=OFF \
-DWITH_TBB=OFF \
-DWITH_V4L=OFF \
-DWITH_OPENCL_SVM=OFF \
-DWITH_OPENCLAMDFFT=OFF \
-DWITH_OPENCLAMDBLAS=OFF \
-DWITH_GPHOTO2=OFF \
-DWITH_LAPACK=OFF \
-DWITH_ITT=OFF \
-DWITH_QUIRC=OFF \
-DBUILD_ZLIB=OFF \
-DBUILD_opencv_apps=OFF \
-DBUILD_opencv_shape=OFF \
-DBUILD_opencv_videostab=OFF \
-DBUILD_opencv_superres=OFF \
-DBUILD_opencv_java=OFF \
-DBUILD_opencv_js=OFF \
-DBUILD_opencv_python2=OFF \
-DBUILD_EXAMPLES=OFF \
-DBUILD_PACKAGE=OFF \
-DBUILD_TESTS=OFF \
-DBUILD_PERF_TESTS=OFF \
-DBUILD_DOCS=OFF \
-DWITH_PTHREADS_PF=OFF \
-DCV_ENABLE_INTRINSICS=OFF \
-DBUILD_WASM_INTRIN_TESTS=OFF \
-DCMAKE_INSTALL_PREFIX=../cmake-install \
-DCMAKE_VERBOSE_MAKEFILE=ON \
-DOPENCV_HAVE_FILESYSTEM_SUPPORT=1 \
-DOPENCV_PYTHON_SKIP_LINKER_EXCLUDE_LIBS=TRUE \
"
