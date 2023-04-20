// The point is to make a file that works with JavaScript analysis tools like
// JsDoc and LGTM. They want to parse the file as JavaScript. Thus, it's key
// that included js files should parse as valid JavaScript. `JS_FILE` is a
// specially designed macro to allow us to do this. We need to look like a
// function call to JavaScript parsers. The easiest way to get it to parse is to
// make the macro argument look like a JavaScript anonymous function, which we
// do with `()=>{`. However, `()=>{` is an invalid C string so the macro needs
// to remove it. We put `()=>{0,0;`, JS_FILE removes everything up to
// the comma and replace it with a single open brace.
//

#define UNPAIRED_OPEN_BRACE {
#define UNPAIRED_CLOSE_BRACE } // Just here to help text editors pair braces up
#define JS_FILE(func_name, a, args...)                                         \
  EM_JS_NUM(                                                                   \
    int, func_name, (), UNPAIRED_OPEN_BRACE { args return 0; })

// A macro to allow us to add code that is only intended to influence JsDoc
// output, but shouldn't end up in generated code.
#define FOR_JSDOC_ONLY(x)
