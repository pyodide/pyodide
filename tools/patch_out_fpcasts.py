import json


def create_node(obj):
    if "kind" in obj:
        return Tree(obj)
    else:
        return obj


class Tree:
    def __init__(self, obj):
        self.kind = None
        self.name = None
        self.opcode = None
        self.referencedDecl = None
        self.type = None
        self.value = None
        self.__dict__.update(obj)
        self.children = [x for x in self.inner if x] if hasattr(self, "inner") else []
        for c in self.children:
            c.parent = self

    @property
    def first_child(self):
        return self.children[0]

    def iter_call_exprs(self):
        """Genertor for all CallExpr nodes"""
        next = self.children
        if self.is_call_expr:
            yield self
            next = next[1:]
        for t in next:
            yield from t.iter_call_exprs()

    def find_line(self):
        """
        Annoyingly, information about the line is not always found in the node's own location information.
        Walk up the tree until we find a line. Pray that this is the right line (I haven't really worked out
        the logic llvm uses for its locations...)
        """
        while True:
            range = self.range["begin"]
            if "expansionLoc" in range:
                # I guess use expansionLoc here not spellingLoc? Seems to make more sense
                range = range["expansionLoc"]
            if "line" in range:
                return range["line"]
            self = self.parent

    def get_end_col(self):
        """Get the end column.

        If there's macro funny business, use spellingLoc not expansionLoc b/c that seems to work for some reason...
        """
        end = self.range["end"]
        if "col" in end:
            return end["col"]
        # This only seems to work with spellingLoc...
        return end["spellingLoc"]["col"]

    @property
    def is_null_cast(self):
        """We need this to check for sentinels in the PyMethodDef or PyGetSetDef lists."""
        return hasattr(self, "castKind") and self.castKind == "NullToPointer"

    def descend_to_declref(self):
        """A"""
        while not self.is_decl_ref:
            if self.is_null_cast:
                return
            self = self.first_child
        return self

    def find_decls(self, name):
        for t in self.children:
            if not t.is_var_decl and not t.is_init_list_expr:
                continue
            if not t.children:
                continue
            if t.is_var_decl:
                for c in t.children:
                    if c.is_init_list_expr:
                        t = c
                        break
                else:
                    continue
            if t.type["qualType"] == name or t.type["qualType"] == f"struct {name}":
                yield t
            else:
                yield from t.find_decls(name)

    def __repr__(self) -> str:
        result = [self.kind]
        if hasattr(self, "name"):
            result.append(self.name)
        if self.is_operator:
            result.append(self.opcode)
        if self.kind == "DeclRefExpr":
            result.append(f"==> {self.referencedDecl}")
        if self.is_cast_expr:
            result.append(self.type["qualType"])
        if self.kind == "IntegerLiteral":
            result.append(self.value)
        return " ".join(result)

    @property
    def is_operator(self):
        return self.kind == "UnaryOperator" or self.kind == "BinaryOperator"

    @property
    def is_cast_expr(self):
        return self.kind == "ImplicitCastExpr" or self.kind == "CStyleCastExpr"

    @property
    def is_call_expr(self):
        return self.kind == "CallExpr"

    @property
    def is_func_decl(self):
        return self.kind == "FunctionDecl"

    @property
    def is_var_decl(self):
        return self.kind == "VarDecl"

    @property
    def is_param_decl(self):
        return self.kind == "ParmVarDecl"

    @property
    def is_decl_ref(self):
        return self.kind == "DeclRefExpr"

    @property
    def is_init_list_expr(self):
        return self.kind == "InitListExpr"

    def pretty_lines(self, prefix="", last_child=False, root=True):
        output = prefix
        if last_child:
            output += "`-"
            prefix += " "
        elif not root:
            output += "-"
        if not root:
            prefix += " "
        output += repr(self)
        yield output
        global x
        for child in self.children[:-1]:
            import pdb

            if not child:
                pdb.set_trace()
            yield from child.pretty_lines(prefix + "|", root=False)
        if self.children:
            yield from self.children[-1].pretty_lines(
                prefix, last_child=True, root=False
            )

    def pretty_print(self):
        for line in self.pretty_lines():
            print(line)

    def eval_int(self):
        if self.kind == "IntegerLiteral":
            return int(self.value)
        if self.kind == "ParenExpr":
            return self.first_child.eval_int()
        if self.kind == "BinaryOperator":
            if self.opcode == "|":
                return self.children[0].eval_int() | self.children[1].eval_int()
            raise ValueError("Unexpected binop " + self.opcode)
        raise ValueError("Unexpected type " + self.kind)


METHOD_FLAGS = {
    "METH_VARARGS": 1,
    "METH_KEYWORDS": 2,
    "METH_NOARGS": 4,
    "METH_O": 8,
    "METH_FASTCALL": 128,
}

EXPECTED_ARGS = {
    ("METH_NOARGS",): 2,
    ("METH_O",): 2,
    ("METH_VARARGS",): 2,
    ("METH_KEYWORDS", "METH_VARARGS"): 3,
    (
        "METH_FASTCALL",
        "METH_KEYWORDS",
    ): 4,
    ("METH_FASTCALL",): 3,
}


def is_bad_method_def(c):
    declref = c.children[1].descend_to_declref()
    flags = c.children[2].eval_int()
    meth_flags = []
    for [mty, mflag] in METHOD_FLAGS.items():
        if flags & mflag:
            meth_flags.append(mty)
    meth_flags = tuple(sorted(meth_flags))
    expected_args = EXPECTED_ARGS[meth_flags]
    return count_sig_args(declref.type["qualType"]) != expected_args


def get_method_defs_to_fix(tree):
    for pymeth_decl in tree.find_decls("PyMethodDef"):
        if pymeth_decl.first_child.is_null_cast:
            continue
        if is_bad_method_def(pymeth_decl):
            declref = pymeth_decl.children[1].descend_to_declref()
            func_name = declref.referencedDecl.name
            yield func_name


def count_sig_args(sig):
    return sig.count(",") + 1


def get_bad_getset_names(c):
    if len(c.children) <= 1:
        return
    getter_node = c.children[1]
    if getter_node.kind != "ImplicitValueInitExpr":
        declref = getter_node.descend_to_declref()
        if declref:
            sig = declref.type["qualType"]

            if count_sig_args(sig) != 2:
                yield declref.referencedDecl.name

    if len(c.children) <= 2:
        return
    setter_node = c.children[2]
    if setter_node.kind != "ImplicitValueInitExpr":
        declref = setter_node.descend_to_declref()
        if declref:
            sig = declref.type["qualType"]
            if count_sig_args(sig) != 3:
                yield declref.referencedDecl.name


def get_getset_defs_to_fix(tree):
    for pygetset_decl in tree.find_decls("PyGetSetDef"):
        if pygetset_decl.first_child.is_null_cast:
            continue
        yield from get_bad_getset_names(pygetset_decl)
        if False:
            yield


def fix_func_decls(src_lines, tree, target_names):
    target_names = set(target_names)
    for t in tree.children:
        if not t.is_func_decl:
            continue
        if not t.name in target_names:
            continue
        loc = t.loc
        if "expansionLoc" in loc:
            loc = loc["expansionLoc"]
        lineno = loc["line"]
        # llvm one-indexes line and column
        lineno -= 1
        line: str = src_lines[lineno]
        colno = line.rfind(")")
        if t.name not in line:
            continue
        newline = line[:colno] + ", PyObject *ignored" + line[colno:]
        src_lines[lineno] = newline


def patch_source_file_inner(ast_filename, src_filename, in_place=False):
    tree = json.load(open(ast_filename, "r"), object_hook=create_node)
    # sys.exit(0)
    funcs_to_fix = []
    funcs_to_fix.extend(get_method_defs_to_fix(tree))
    funcs_to_fix.extend(get_getset_defs_to_fix(tree))

    if not funcs_to_fix:
        return
    print(f"Patched fpcasts in {src_filename}!")

    with open(src_filename, "r") as src:
        src_lines = list(src)
    fix_func_decls(src_lines, tree, funcs_to_fix)
    for call_expr in tree.iter_call_exprs():
        decl_ref = call_expr.first_child.descend_to_declref()
        name = decl_ref.referencedDecl.name
        if name in funcs_to_fix:
            lineno = call_expr.find_line()
            colno = call_expr.get_end_col()
            lineno -= 1
            colno -= 1
            line = src_lines[lineno]
            src_lines[lineno] = line[:colno] + ", NULL" + line[colno:]

    if in_place:
        dst_filename = src_filename
        import shutil

        shutil.copy(src_filename, src_filename + ".bak")
    else:
        dst_filename = src_filename + ".patched"

    with open(dst_filename, "w") as dst:
        dst.writelines(src_lines)
    return 0


def patch_source_file(ast_filename, src_filename, in_place=False):
    try:
        return patch_source_file_inner(ast_filename, src_filename, in_place)
    except Exception as e:
        print("\n\n=======================================")
        print("Error processing file", src_filename)
        raise e


def process_compilation_command(cmd, input_file):
    import subprocess
    import os

    PYODIDE_ROOT = os.environ.get("PYODIDE_ROOT")
    if not PYODIDE_ROOT:
        print("no PYODIDE_ROOT, not patching fpcasts")
        return
    res = subprocess.run(["egrep", "-q", "(PyGetSetDef)|(PyMethodDef)", input_file])
    if res.returncode != 0:
        return
    cmd2 = (
        cmd[:1]
        + ["-cc1"]
        + [
            arg
            for arg in cmd
            if arg.startswith("-I") or arg.startswith("-i") or arg.startswith("-D")
        ]
        + [
            f"-I{PYODIDE_ROOT}/emsdk/emsdk/upstream/emscripten/cache/sysroot/include",
            f"-I{PYODIDE_ROOT}/emsdk/emsdk/upstream/lib/clang/13.0.0/include",
            "-Wno-unknown-attributes",
            "-Wno-incompatible-library-redeclaration",
        ]
        + [input_file]
    )
    ast_file = input_file + ".ast"
    with open(ast_file, "w") as f:
        res = subprocess.run(cmd2 + ["-ast-dump=json"], stdout=f)
    patch_source_file(ast_file, input_file, in_place=True)


def main(args):
    import argparse

    parser = argparse.ArgumentParser(
        description="Patch Python C source files to prevent function pointers from being called with the wrong number of arguments."
    )
    parser.add_argument(
        "ast_file",
        type=str,
        help="The ast for the C source (produced by 'clang -cc1 -ast-dump')",
    )
    parser.add_argument("source_file", type=str, help="The C source to patch")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write patched source over the original source file",
    )
    args = parser.parse_args(args)
    patch_source_file(args.ast_file, args.source_file, args.in_place)


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
