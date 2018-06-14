#ifndef HIWIRE_H
#define HIWIRE_H

// TODO: Document me

void
hiwire_setup();

int
hiwire_incref(int idval);

void
hiwire_decref(int idval);

int
hiwire_int(int val);

int
hiwire_double(double val);

int
hiwire_string_utf8_length(int ptr, int len);

int
hiwire_string_utf8(int ptr);

int
hiwire_bytes(int ptr, int len);

int
hiwire_undefined();

int
hiwire_null();

int
hiwire_true();

int
hiwire_false();

int
hiwire_array();

int
hiwire_push_array(int idobj, int idval);

int
hiwire_object();

int
hiwire_push_object_pair(int idobj, int idkey, int idval);

int
hiwire_throw_error(int idmsg);

int
hiwire_get_global(int ptrname);

int
hiwire_get_member_string(int idobj, int ptrname);

void
hiwire_set_member_string(int idobj, int ptrname, int idval);

int
hiwire_get_member_int(int idobj, int idx);

void
hiwire_set_member_int(int idobj, int idx, int idval);

int
hiwire_call(int idobj, int idargs);

int
hiwire_call_member(int idobj, int ptrname, int idargs);

int
hiwire_new(int idobj, int idargs);

int
hiwire_get_length(int idobj);

int
hiwire_is_function(int idobj);

int
hiwire_to_string(int idobj);

#endif /* HIWIRE_H */
