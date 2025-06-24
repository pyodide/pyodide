use pyo3::prelude::*;

#[pyfunction]
fn panic_test(data: &[u8]) -> bool {
    if data[0] < 6 {
        panic!("this is a {} {message:?}", "fancy", message = data);
    }
    data[0] < 20
}



#[pymodule]
fn rust_panic_test(m: &Bound<'_, PyModule>) -> pyo3::PyResult<()> {
    m.add_function(pyo3::wrap_pyfunction!(panic_test, m)?)?;
    m.add("PanicException", m.py().get_type::<pyo3::panic::PanicException>())?;
    Ok(())
}
