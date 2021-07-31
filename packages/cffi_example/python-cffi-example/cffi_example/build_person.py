from cffi import FFI

ffi = FFI()

person_header = """
    typedef struct {
        wchar_t *p_first_name;
        wchar_t *p_last_name;
        int p_age;
    } person_t;

    /* Creates a new person. Names are strdup(...)'d into the person. */
    person_t *person_create(const wchar_t *first_name, const wchar_t *last_name, int age);

    /* Writes the person's full name into *buf, up to n characters.
     * Returns the number of characters written. */
    int person_get_full_name(person_t *p, wchar_t *buf, size_t n);

    /* Destroys a person, including free()ing their names. */
    void person_destroy(person_t *p);
"""

ffi.set_source(
    "cffi_example._person",
    person_header
    + """
    #include <stdlib.h>
    #include <string.h>
    #include <wchar.h>

    person_t *person_create(const wchar_t *first_name, const wchar_t *last_name, int age) {
        person_t *p = malloc(sizeof(person_t));
        if (!p)
            return NULL;
        p->p_first_name = wcsdup(first_name);
        p->p_last_name = wcsdup(last_name);
        p->p_age = age;
        return p;
    }

    int person_get_full_name(person_t *p, wchar_t *buf, size_t n) {
        return swprintf(buf, n, L"%S %S", p->p_first_name, p->p_last_name);
    }

    void person_destroy(person_t *p) {
        if (p->p_first_name)
            free(p->p_first_name);
        if (p->p_last_name)
            free(p->p_last_name);
        free(p);
    }
""",
)

ffi.cdef(person_header)

if __name__ == "__main__":
    ffi.compile()
