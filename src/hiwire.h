#ifndef HIWIRE_H
#define HIWIRE_H

// TODO: Document me

void hiwire_setup();
int hiwire_incref(int);
void hiwire_decref(int);
int hiwire_int(int);
int hiwire_double(double);
int hiwire_string_utf8_length(int, int);
int hiwire_string_utf8(int);
int hiwire_bytes(int, int);
int hiwire_undefined();
int hiwire_null();
int hiwire_true();
int hiwire_false();
int hiwire_array();
int hiwire_push_array(int, int);
int hiwire_object();
int hiwire_push_object_pair(int, int, int);
int hiwire_throw_error(int);
int hiwire_get_global(int);
int hiwire_get_member_string(int, int);
void hiwire_set_member_string(int, int, int);
int hiwire_get_member_int(int, int);
void hiwire_set_member_int(int, int, int);
int hiwire_call(int, int);
int hiwire_call_member(int, int, int);
int hiwire_new(int, int);
int hiwire_length(int);
int hiwire_is_function(int);
int hiwire_to_string(int);

#endif /* HIWIRE_H */
