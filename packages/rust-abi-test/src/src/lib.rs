use std::fs;
use pyo3::prelude::*;


#[pyfunction]
fn get_file_length(data: &str) ->  PyResult<u64> {
    let metadata = fs::metadata(data)?;
    Ok(metadata.len())
}



#[pymodule]
fn rust_abi_test(m: &Bound<'_, PyModule>) -> pyo3::PyResult<()> {
    m.add_function(wrap_pyfunction!(get_file_length, m)?)?;
    Ok(())
}
