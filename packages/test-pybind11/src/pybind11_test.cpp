// A small pybind11 extension that exercises the GIL handling that pybind11
// does around stored Python callables, modelled on highspy's
// `_Highs.setCallback`. See https://github.com/pyodide/pyodide/issues/6479.
//
// pybind11 caches the PyThreadState pointer in `internals.tstate` when it
// initializes and `gil_scoped_acquire` passes it to PyEval_AcquireThread(),
// which aborts with "non-NULL old thread state" if a different thread state is
// current at the time. Copying or destroying the std::function that wraps a
// Python callable, and calling it with the GIL released, all go through
// `gil_scoped_acquire`.

#include <functional>
#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>

namespace py = pybind11;

using Callback = std::function<void(int, const std::string&, py::handle)>;

class Solver
{
public:
  // Like highspy's highs_setCallback: wrap the Python callable (already
  // converted to a std::function by pybind11, which involves a
  // gil_scoped_acquire in func_handle's copy constructor) in a C++ lambda.
  void setCallback(Callback fn, py::handle data)
  {
    if (!fn) {
      callback_ = nullptr;
      data_ = py::none();
      return;
    }
    data_ = py::reinterpret_borrow<py::object>(data);
    callback_ = [fn](int type, const std::string& msg, void* d) {
      fn(type, msg, py::handle(reinterpret_cast<PyObject*>(d)));
    };
  }

  bool hasCallback() const { return static_cast<bool>(callback_); }

  // Called with the GIL released (see call_guard below), like Highs::run.
  // pybind11 reacquires the GIL each time it calls into the Python callable.
  int run(int iterations)
  {
    int fired = 0;
    for (int i = 0; i < iterations; i++) {
      if (callback_) {
        callback_(i, "iteration " + std::to_string(i), data_.ptr());
        fired++;
      }
    }
    return fired;
  }

private:
  std::function<void(int, const std::string&, void*)> callback_ = nullptr;
  py::object data_ = py::none();
};

// Release and reacquire the GIL and then call `fn`. Returns whatever `fn`
// returns.
py::object
round_trip_gil(py::function fn)
{
  {
    py::gil_scoped_release release;
    py::gil_scoped_acquire acquire;
  }
  return fn();
}

// Call `fn` from C++ with the GIL released around the call boundary, the way
// a C++ library would call back into Python from a worker routine. `fn` may
// stack switch.
py::object
call_with_gil_released(std::function<py::object()> fn)
{
  py::object result;
  {
    py::gil_scoped_release release;
    result = fn();
  }
  return result;
}

PYBIND11_MODULE(pybind11_test, m)
{
  py::class_<Solver>(m, "Solver")
    .def(py::init<>())
    .def("setCallback", &Solver::setCallback, py::arg("fn"), py::arg("data"))
    .def("hasCallback", &Solver::hasCallback)
    .def("run",
         &Solver::run,
         py::arg("iterations"),
         py::call_guard<py::gil_scoped_release>());
  m.def("round_trip_gil", &round_trip_gil);
  m.def("call_with_gil_released", &call_with_gil_released);
}
