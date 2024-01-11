
/* FIXME: LONG_BIT is miscalculated to 64 for some reason starting from Emscripten 3.1.50 */
/* https://github.com/emscripten-core/emscripten/pull/20752 this PR is probably related, */
/* but it is not clear why it calculates LONG_BIT incorrectly */

#undef LONG_BIT
#define LONG_BIT 32