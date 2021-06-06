exports.handlers = {
  jsdocCommentFound: function (e) {
    // JsDoc cannot handle Typescript type guards. Replace them with "boolean"
    // for JsDoc. Without this output docs get messed up.
    e.comment = e.comment.replace(/\{\s*\w*\s*\bis\b\s*\w*\s*\}/g, "{boolean}");
    // Remove typedefs from file. JsDoc can't parse these. Docs are produced
    // correctly without this but JsDoc produces very very noisy error messages.
    e.comment = e.comment.replace(/@typedef[^*]*/g, "");
    // There's still a couple of JsDoc parse errors we could fix...
  },
};
