import pytest
from pytest_pyodide import run_in_pyodide

INPUT_SQL = """SELECT DISTINCT table_a.id, table_a.a, table_a.p_type, table_a.b, table_a.c, table_b.id AS id_1
FROM table_a JOIN table_x ON table_a.id = table_x.table_a_id JOIN table_c ON table_a.table_c_id = table_c.id JOIN table_d ON table_c.table_d_id = table_d.id JOIN table_e ON table_c.table_e_id = table_e.id JOIN table_f ON table_c.table_f_id = table_f.id JOIN table_b ON table_f.table_b_id = table_b.id JOIN table_y ON table_d.table_y_id = table_y.id JOIN table_g ON table_c.id = table_g.table_c_id JOIN h_item ON table_g.h_item_id = h_item.id
WHERE table_b.id = :id_2 AND table_a.p_type = :p_type_1 AND table_a.enabled = :enabled_1 AND h_item.enabled = :enabled_2 ORDER BY table_a.id DESC
"""

OUTPUT_SQL = """SELECT DISTINCT table_a.id,
                table_a.a,
                table_a.p_type,
                table_a.b,
                table_a.c,
                table_b.id AS id_1
FROM table_a
JOIN table_x ON table_a.id = table_x.table_a_id
JOIN table_c ON table_a.table_c_id = table_c.id
JOIN table_d ON table_c.table_d_id = table_d.id
JOIN table_e ON table_c.table_e_id = table_e.id
JOIN table_f ON table_c.table_f_id = table_f.id
JOIN table_b ON table_f.table_b_id = table_b.id
JOIN table_y ON table_d.table_y_id = table_y.id
JOIN table_g ON table_c.id = table_g.table_c_id
JOIN h_item ON table_g.h_item_id = h_item.id
WHERE table_b.id = :id_2
  AND table_a.p_type = :p_type_1
  AND table_a.enabled = :enabled_1
  AND h_item.enabled = :enabled_2
ORDER BY table_a.id DESC"""


@pytest.mark.parametrize("input_sql, output_sql", [INPUT_SQL, OUTPUT_SQL])
@run_in_pyodide(packages=["sqlparse"])
def test_resample(selenium, input_sql, output_sql):
    import sqlparse

    parsed_output_sql = sqlparse.format(input_sql, reindent=True, keyword_case="upper")
    assert parsed_output_sql == output_sql
