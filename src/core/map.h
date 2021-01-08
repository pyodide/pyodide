// From:
// https://github.com/Erlkoenig90/map-macro/blob/37c567dbe6a6b7710e5272ab1f81ac721f98cabd/map.h
// We need this fork of the original because it adds MAP_UD which we'll use.
// clang-format off
// original file starts here:
/*
 * Copyright (C) 2012 William Swanson
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY
 * CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
 * WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * Except as contained in this notice, the names of the authors or
 * their institutions shall not be used in advertising or otherwise to
 * promote the sale, use or other dealings in this Software without
 * prior written authorization from the authors.
 */
#ifndef MAP_H_INCLUDED
#define MAP_H_INCLUDED

#define EVAL0(...) __VA_ARGS__
#define EVAL1(...) EVAL0(EVAL0(EVAL0(__VA_ARGS__)))
#define EVAL2(...) EVAL1(EVAL1(EVAL1(__VA_ARGS__)))
#define EVAL3(...) EVAL2(EVAL2(EVAL2(__VA_ARGS__)))
#define EVAL4(...) EVAL3(EVAL3(EVAL3(__VA_ARGS__)))
#define EVAL5(...) EVAL4(EVAL4(EVAL4(__VA_ARGS__)))

#ifdef _MSC_VER
// MSVC needs more evaluations
#define EVAL6(...) EVAL5(EVAL5(EVAL5(__VA_ARGS__)))
#define EVAL(...)  EVAL6(EVAL6(__VA_ARGS__))
#else
#define EVAL(...)  EVAL5(__VA_ARGS__)
#endif

#define MAP_END(...)
#define MAP_OUT

#define EMPTY()
#define DEFER(id) id EMPTY()

#define MAP_GET_END2() 0, MAP_END
#define MAP_GET_END1(...) MAP_GET_END2
#define MAP_GET_END(...) MAP_GET_END1
#define MAP_NEXT0(test, next, ...) next MAP_OUT
#define MAP_NEXT1(test, next) DEFER ( MAP_NEXT0 ) ( test, next, 0)
#define MAP_NEXT(test, next)  MAP_NEXT1(MAP_GET_END test, next)
#define MAP_INC(X) MAP_INC_ ## X

#define MAP0(f, x, peek, ...) f(x) DEFER ( MAP_NEXT(peek, MAP1) ) ( f, peek, __VA_ARGS__ )
#define MAP1(f, x, peek, ...) f(x) DEFER ( MAP_NEXT(peek, MAP0) ) ( f, peek, __VA_ARGS__ )

#define MAP0_UD(f, userdata, x, peek, ...) f(x,userdata) DEFER ( MAP_NEXT(peek, MAP1_UD) ) ( f, userdata, peek, __VA_ARGS__ )
#define MAP1_UD(f, userdata, x, peek, ...) f(x,userdata) DEFER ( MAP_NEXT(peek, MAP0_UD) ) ( f, userdata, peek, __VA_ARGS__ )

#define MAP0_UD_I(f, userdata, index, x, peek, ...) f(x,userdata,index) DEFER ( MAP_NEXT(peek, MAP1_UD_I) ) ( f, userdata, MAP_INC(index), peek, __VA_ARGS__ )
#define MAP1_UD_I(f, userdata, index, x, peek, ...) f(x,userdata,index) DEFER ( MAP_NEXT(peek, MAP0_UD_I) ) ( f, userdata, MAP_INC(index), peek, __VA_ARGS__ )

#define MAP_LIST0(f, x, peek, ...) , f(x) DEFER ( MAP_NEXT(peek, MAP_LIST1) ) ( f, peek, __VA_ARGS__ )
#define MAP_LIST1(f, x, peek, ...) , f(x) DEFER ( MAP_NEXT(peek, MAP_LIST0) ) ( f, peek, __VA_ARGS__ )
#define MAP_LIST2(f, x, peek, ...)   f(x) DEFER ( MAP_NEXT(peek, MAP_LIST1) ) ( f, peek, __VA_ARGS__ )

#define MAP_LIST0_UD(f, userdata, x, peek, ...) , f(x, userdata) DEFER ( MAP_NEXT(peek, MAP_LIST1_UD) ) ( f, userdata, peek, __VA_ARGS__ )
#define MAP_LIST1_UD(f, userdata, x, peek, ...) , f(x, userdata) DEFER ( MAP_NEXT(peek, MAP_LIST0_UD) ) ( f, userdata, peek, __VA_ARGS__ )
#define MAP_LIST2_UD(f, userdata, x, peek, ...)   f(x, userdata) DEFER ( MAP_NEXT(peek, MAP_LIST1_UD) ) ( f, userdata, peek, __VA_ARGS__ )

#define MAP_LIST0_UD_I(f, userdata, index, x, peek, ...) , f(x, userdata, index) DEFER ( MAP_NEXT(peek, MAP_LIST1_UD_I) ) ( f, userdata, MAP_INC(index), peek, __VA_ARGS__ )
#define MAP_LIST1_UD_I(f, userdata, index, x, peek, ...) , f(x, userdata, index) DEFER ( MAP_NEXT(peek, MAP_LIST0_UD_I) ) ( f, userdata, MAP_INC(index), peek, __VA_ARGS__ )
#define MAP_LIST2_UD_I(f, userdata, index, x, peek, ...)   f(x, userdata, index) DEFER ( MAP_NEXT(peek, MAP_LIST0_UD_I) ) ( f, userdata, MAP_INC(index), peek, __VA_ARGS__ )

/**
 * Applies the function macro `f` to each of the remaining parameters.
 */
#define MAP(f, ...) EVAL(MAP1(f, __VA_ARGS__, ()()(), ()()(), ()()(), 0))

/**
 * Applies the function macro `f` to each of the remaining parameters and
 * inserts commas between the results.
 */
#define MAP_LIST(f, ...) EVAL(MAP_LIST2(f, __VA_ARGS__, ()()(), ()()(), ()()(), 0))

/**
 * Applies the function macro `f` to each of the remaining parameters and passes userdata as the second parameter to each invocation,
 * e.g. MAP_UD(f, x, a, b, c) evaluates to f(a, x) f(b, x) f(c, x)
 */
#define MAP_UD(f, userdata, ...) EVAL(MAP1_UD(f, userdata, __VA_ARGS__, ()()(), ()()(), ()()(), 0))

/**
 * Applies the function macro `f` to each of the remaining parameters, inserts commas between the results,
 * and passes userdata as the second parameter to each invocation,
 * e.g. MAP_LIST_UD(f, x, a, b, c) evaluates to f(a, x), f(b, x), f(c, x)
 */
#define MAP_LIST_UD(f, userdata, ...) EVAL(MAP_LIST2_UD(f, userdata, __VA_ARGS__, ()()(), ()()(), ()()(), 0))

/**
 * Applies the function macro `f` to each of the remaining parameters, passes userdata as the second parameter to each invocation,
 * and the index of the invocation as the third parameter,
 * e.g. MAP_UD_I(f, x, a, b, c) evaluates to f(a, x, 0) f(b, x, 1) f(c, x, 2)
 */
#define MAP_UD_I(f, userdata, ...) EVAL(MAP1_UD_I(f, userdata, 0, __VA_ARGS__, ()()(), ()()(), ()()(), 0))

/**
 * Applies the function macro `f` to each of the remaining parameters, inserts commas between the results,
 * passes userdata as the second parameter to each invocation, and the index of the invocation as the third parameter,
 * e.g. MAP_LIST_UD_I(f, x, a, b, c) evaluates to f(a, x, 0), f(b, x, 1), f(c, x, 2)
 */
#define MAP_LIST_UD_I(f, userdata, ...) EVAL(MAP_LIST2_UD_I(f, userdata, 0, __VA_ARGS__, ()()(), ()()(), ()()(), 0))

/*
 * Because the preprocessor can't do arithmetic that produces integer literals for the *_I macros, we have to do it manually.
 * Since the number of parameters is limited anyways, this is sufficient for all cases. If extra EVAL layers are added, these
 * definitions have to be extended. This is equivalent to the way Boost.preprocessor does it:
 * https://github.com/boostorg/preprocessor/blob/develop/include/boost/preprocessor/arithmetic/inc.hpp
 * The *_I macros could alternatively pass C expressions such as (0), (0+1), (0+1+1...) to the user macro, but passing 0, 1, 2 ...
 * allows the user to incorporate the index into C identifiers, e.g. to define a function like test_##index () for each
 * macro invocation.
 */
#define MAP_INC_0 1
#define MAP_INC_1 2
#define MAP_INC_2 3
#define MAP_INC_3 4
#define MAP_INC_4 5
#define MAP_INC_5 6
#define MAP_INC_6 7
#define MAP_INC_7 8
#define MAP_INC_8 9
#define MAP_INC_9 10
#define MAP_INC_10 11
#define MAP_INC_11 12
#define MAP_INC_12 13
#define MAP_INC_13 14
#define MAP_INC_14 15
#define MAP_INC_15 16
#define MAP_INC_16 17
#define MAP_INC_17 18
#define MAP_INC_18 19
#define MAP_INC_19 20
#define MAP_INC_20 21
#define MAP_INC_21 22
#define MAP_INC_22 23
#define MAP_INC_23 24
#define MAP_INC_24 25
#define MAP_INC_25 26
#define MAP_INC_26 27
#define MAP_INC_27 28
#define MAP_INC_28 29
#define MAP_INC_29 30
#define MAP_INC_30 31
#define MAP_INC_31 32
#define MAP_INC_32 33
#define MAP_INC_33 34
#define MAP_INC_34 35
#define MAP_INC_35 36
#define MAP_INC_36 37
#define MAP_INC_37 38
#define MAP_INC_38 39
#define MAP_INC_39 40
#define MAP_INC_40 41
#define MAP_INC_41 42
#define MAP_INC_42 43
#define MAP_INC_43 44
#define MAP_INC_44 45
#define MAP_INC_45 46
#define MAP_INC_46 47
#define MAP_INC_47 48
#define MAP_INC_48 49
#define MAP_INC_49 50
#define MAP_INC_50 51
#define MAP_INC_51 52
#define MAP_INC_52 53
#define MAP_INC_53 54
#define MAP_INC_54 55
#define MAP_INC_55 56
#define MAP_INC_56 57
#define MAP_INC_57 58
#define MAP_INC_58 59
#define MAP_INC_59 60
#define MAP_INC_60 61
#define MAP_INC_61 62
#define MAP_INC_62 63
#define MAP_INC_63 64
#define MAP_INC_64 65
#define MAP_INC_65 66
#define MAP_INC_66 67
#define MAP_INC_67 68
#define MAP_INC_68 69
#define MAP_INC_69 70
#define MAP_INC_70 71
#define MAP_INC_71 72
#define MAP_INC_72 73
#define MAP_INC_73 74
#define MAP_INC_74 75
#define MAP_INC_75 76
#define MAP_INC_76 77
#define MAP_INC_77 78
#define MAP_INC_78 79
#define MAP_INC_79 80
#define MAP_INC_80 81
#define MAP_INC_81 82
#define MAP_INC_82 83
#define MAP_INC_83 84
#define MAP_INC_84 85
#define MAP_INC_85 86
#define MAP_INC_86 87
#define MAP_INC_87 88
#define MAP_INC_88 89
#define MAP_INC_89 90
#define MAP_INC_90 91
#define MAP_INC_91 92
#define MAP_INC_92 93
#define MAP_INC_93 94
#define MAP_INC_94 95
#define MAP_INC_95 96
#define MAP_INC_96 97
#define MAP_INC_97 98
#define MAP_INC_98 99
#define MAP_INC_99 100
#define MAP_INC_100 101
#define MAP_INC_101 102
#define MAP_INC_102 103
#define MAP_INC_103 104
#define MAP_INC_104 105
#define MAP_INC_105 106
#define MAP_INC_106 107
#define MAP_INC_107 108
#define MAP_INC_108 109
#define MAP_INC_109 110
#define MAP_INC_110 111
#define MAP_INC_111 112
#define MAP_INC_112 113
#define MAP_INC_113 114
#define MAP_INC_114 115
#define MAP_INC_115 116
#define MAP_INC_116 117
#define MAP_INC_117 118
#define MAP_INC_118 119
#define MAP_INC_119 120
#define MAP_INC_120 121
#define MAP_INC_121 122
#define MAP_INC_122 123
#define MAP_INC_123 124
#define MAP_INC_124 125
#define MAP_INC_125 126
#define MAP_INC_126 127
#define MAP_INC_127 128
#define MAP_INC_128 129
#define MAP_INC_129 130
#define MAP_INC_130 131
#define MAP_INC_131 132
#define MAP_INC_132 133
#define MAP_INC_133 134
#define MAP_INC_134 135
#define MAP_INC_135 136
#define MAP_INC_136 137
#define MAP_INC_137 138
#define MAP_INC_138 139
#define MAP_INC_139 140
#define MAP_INC_140 141
#define MAP_INC_141 142
#define MAP_INC_142 143
#define MAP_INC_143 144
#define MAP_INC_144 145
#define MAP_INC_145 146
#define MAP_INC_146 147
#define MAP_INC_147 148
#define MAP_INC_148 149
#define MAP_INC_149 150
#define MAP_INC_150 151
#define MAP_INC_151 152
#define MAP_INC_152 153
#define MAP_INC_153 154
#define MAP_INC_154 155
#define MAP_INC_155 156
#define MAP_INC_156 157
#define MAP_INC_157 158
#define MAP_INC_158 159
#define MAP_INC_159 160
#define MAP_INC_160 161
#define MAP_INC_161 162
#define MAP_INC_162 163
#define MAP_INC_163 164
#define MAP_INC_164 165
#define MAP_INC_165 166
#define MAP_INC_166 167
#define MAP_INC_167 168
#define MAP_INC_168 169
#define MAP_INC_169 170
#define MAP_INC_170 171
#define MAP_INC_171 172
#define MAP_INC_172 173
#define MAP_INC_173 174
#define MAP_INC_174 175
#define MAP_INC_175 176
#define MAP_INC_176 177
#define MAP_INC_177 178
#define MAP_INC_178 179
#define MAP_INC_179 180
#define MAP_INC_180 181
#define MAP_INC_181 182
#define MAP_INC_182 183
#define MAP_INC_183 184
#define MAP_INC_184 185
#define MAP_INC_185 186
#define MAP_INC_186 187
#define MAP_INC_187 188
#define MAP_INC_188 189
#define MAP_INC_189 190
#define MAP_INC_190 191
#define MAP_INC_191 192
#define MAP_INC_192 193
#define MAP_INC_193 194
#define MAP_INC_194 195
#define MAP_INC_195 196
#define MAP_INC_196 197
#define MAP_INC_197 198
#define MAP_INC_198 199
#define MAP_INC_199 200
#define MAP_INC_200 201
#define MAP_INC_201 202
#define MAP_INC_202 203
#define MAP_INC_203 204
#define MAP_INC_204 205
#define MAP_INC_205 206
#define MAP_INC_206 207
#define MAP_INC_207 208
#define MAP_INC_208 209
#define MAP_INC_209 210
#define MAP_INC_210 211
#define MAP_INC_211 212
#define MAP_INC_212 213
#define MAP_INC_213 214
#define MAP_INC_214 215
#define MAP_INC_215 216
#define MAP_INC_216 217
#define MAP_INC_217 218
#define MAP_INC_218 219
#define MAP_INC_219 220
#define MAP_INC_220 221
#define MAP_INC_221 222
#define MAP_INC_222 223
#define MAP_INC_223 224
#define MAP_INC_224 225
#define MAP_INC_225 226
#define MAP_INC_226 227
#define MAP_INC_227 228
#define MAP_INC_228 229
#define MAP_INC_229 230
#define MAP_INC_230 231
#define MAP_INC_231 232
#define MAP_INC_232 233
#define MAP_INC_233 234
#define MAP_INC_234 235
#define MAP_INC_235 236
#define MAP_INC_236 237
#define MAP_INC_237 238
#define MAP_INC_238 239
#define MAP_INC_239 240
#define MAP_INC_240 241
#define MAP_INC_241 242
#define MAP_INC_242 243
#define MAP_INC_243 244
#define MAP_INC_244 245
#define MAP_INC_245 246
#define MAP_INC_246 247
#define MAP_INC_247 248
#define MAP_INC_248 249
#define MAP_INC_249 250
#define MAP_INC_250 251
#define MAP_INC_251 252
#define MAP_INC_252 253
#define MAP_INC_253 254
#define MAP_INC_254 255
#define MAP_INC_255 256
#define MAP_INC_256 257
#define MAP_INC_257 258
#define MAP_INC_258 259
#define MAP_INC_259 260
#define MAP_INC_260 261
#define MAP_INC_261 262
#define MAP_INC_262 263
#define MAP_INC_263 264
#define MAP_INC_264 265
#define MAP_INC_265 266
#define MAP_INC_266 267
#define MAP_INC_267 268
#define MAP_INC_268 269
#define MAP_INC_269 270
#define MAP_INC_270 271
#define MAP_INC_271 272
#define MAP_INC_272 273
#define MAP_INC_273 274
#define MAP_INC_274 275
#define MAP_INC_275 276
#define MAP_INC_276 277
#define MAP_INC_277 278
#define MAP_INC_278 279
#define MAP_INC_279 280
#define MAP_INC_280 281
#define MAP_INC_281 282
#define MAP_INC_282 283
#define MAP_INC_283 284
#define MAP_INC_284 285
#define MAP_INC_285 286
#define MAP_INC_286 287
#define MAP_INC_287 288
#define MAP_INC_288 289
#define MAP_INC_289 290
#define MAP_INC_290 291
#define MAP_INC_291 292
#define MAP_INC_292 293
#define MAP_INC_293 294
#define MAP_INC_294 295
#define MAP_INC_295 296
#define MAP_INC_296 297
#define MAP_INC_297 298
#define MAP_INC_298 299
#define MAP_INC_299 300
#define MAP_INC_300 301
#define MAP_INC_301 302
#define MAP_INC_302 303
#define MAP_INC_303 304
#define MAP_INC_304 305
#define MAP_INC_305 306
#define MAP_INC_306 307
#define MAP_INC_307 308
#define MAP_INC_308 309
#define MAP_INC_309 310
#define MAP_INC_310 311
#define MAP_INC_311 312
#define MAP_INC_312 313
#define MAP_INC_313 314
#define MAP_INC_314 315
#define MAP_INC_315 316
#define MAP_INC_316 317
#define MAP_INC_317 318
#define MAP_INC_318 319
#define MAP_INC_319 320
#define MAP_INC_320 321
#define MAP_INC_321 322
#define MAP_INC_322 323
#define MAP_INC_323 324
#define MAP_INC_324 325
#define MAP_INC_325 326
#define MAP_INC_326 327
#define MAP_INC_327 328
#define MAP_INC_328 329
#define MAP_INC_329 330
#define MAP_INC_330 331
#define MAP_INC_331 332
#define MAP_INC_332 333
#define MAP_INC_333 334
#define MAP_INC_334 335
#define MAP_INC_335 336
#define MAP_INC_336 337
#define MAP_INC_337 338
#define MAP_INC_338 339
#define MAP_INC_339 340
#define MAP_INC_340 341
#define MAP_INC_341 342
#define MAP_INC_342 343
#define MAP_INC_343 344
#define MAP_INC_344 345
#define MAP_INC_345 346
#define MAP_INC_346 347
#define MAP_INC_347 348
#define MAP_INC_348 349
#define MAP_INC_349 350
#define MAP_INC_350 351
#define MAP_INC_351 352
#define MAP_INC_352 353
#define MAP_INC_353 354
#define MAP_INC_354 355
#define MAP_INC_355 356
#define MAP_INC_356 357
#define MAP_INC_357 358
#define MAP_INC_358 359
#define MAP_INC_359 360
#define MAP_INC_360 361
#define MAP_INC_361 362
#define MAP_INC_362 363
#define MAP_INC_363 364
#define MAP_INC_364 365
#define MAP_INC_365 366

#endif
