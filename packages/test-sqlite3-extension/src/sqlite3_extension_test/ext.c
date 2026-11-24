// A minimal SQLite loadable extension that registers a `pyodide_answer()` SQL
// function returning 42.
#include "sqlite3ext.h"
SQLITE_EXTENSION_INIT1

static void
answer(sqlite3_context* ctx, int argc, sqlite3_value** argv)
{
  sqlite3_result_int(ctx, 42);
}

int
sqlite3_extension_init(sqlite3* db,
                       char** pzErrMsg,
                       const sqlite3_api_routines* pApi)
{
  SQLITE_EXTENSION_INIT2(pApi);
  return sqlite3_create_function(
    db, "pyodide_answer", 0, SQLITE_UTF8, 0, answer, 0, 0);
}
