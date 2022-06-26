#define PY(x, y...) x y

#define ENTER(arg1, rest...)                                                   \
  try {                                                                        \
    Module.HEAP32[Module._entry_depth]++;                                      \
    arg1;                                                                      \
    rest;                                                                      \
    Module.HEAP32[Module._entry_depth]--;                                      \
  } catch (e) {                                                                \
    API.fatal_error(e);                                                        \
  }

#define WHILE(cond, body...)                                                   \
  while (cond) {                                                               \
    body;                                                                      \
  }

#define DO(args...) args

#define FINALLY(args...)                                                       \
  finally                                                                      \
  {                                                                            \
    args                                                                       \
  }
