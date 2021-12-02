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
        self.children = (
            [x for x in self.inner if isinstance(x, Tree)]
            if hasattr(self, "inner")
            else []
        )
        for c in self.children:
            c.parent = self

    @property
    def first_child(self):
        return self.children[0]

    def iter_call_exprs(self):
        """Generator for all CallExpr nodes"""
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
        """Function pointers are often wrapped in many nested cast nodes.
        Descend through the cast nodes until we find a function.
        But if we realize it's a null pointer, we bail out and return None.
        """
        while not self.is_decl_ref:
            if not self.children:
                return
            self = self.first_child
        return self

    def find_decls(self, name):
        """Find all variable declarations that declare a variable of type name."""
        for t in self.children:
            if not t.is_var_decl and not t.is_init_list_expr:
                yield from t.find_decls(name)
                continue
            if t.is_var_decl:
                # Usually we have only one child and it's an InitListExpr
                # But sometimes there are also AccessModifier nodes.
                for c in t.children:
                    if c.is_init_list_expr:
                        t = c
                        break
                else:
                    # In this case it's a declaration with no initializer
                    # e.g., "PyMethodDef blah[4];"
                    # ignore it.
                    continue
            # If we made it here, t is definitely an InitListExpr.
            # Check if it has the target type.
            if t.type["qualType"] == name or t.type["qualType"] == f"struct {name}":
                yield t
                continue
            yield from t.find_decls(name)

    def eval_int(self):
        """This is needed to work out which METH_XXX flags are present.

        Evaluate an int expression. We only handle integer literals and bitwise or, which is good enough so far.
        """
        if self.kind == "IntegerLiteral":
            return int(self.value)
        if self.kind == "ParenExpr":
            return self.first_child.eval_int()
        if self.kind == "BinaryOperator":
            if self.opcode == "|":
                return self.children[0].eval_int() | self.children[1].eval_int()
            raise ValueError("Unexpected binop " + self.opcode)
        raise ValueError("Unexpected type " + self.kind)

    def __repr__(self) -> str:
        result = [self.kind]
        if self.name:
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
        """Mimic clang's ast-dump text format"""
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
            yield from child.pretty_lines(prefix + "|", root=False)
        if self.children:
            yield from self.children[-1].pretty_lines(
                prefix, last_child=True, root=False
            )

    def pretty_print(self):
        for line in self.pretty_lines():
            print(line)


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


def method_def_arg_discrepancy(c):
    """Find difference of expected_args - actual_args for function.

    Argument should be a InitList for a PyMethodDef. We can look at the ml_flags field to figure out what the number of args should be,
    and at the ml_meth field to figure out how many args there actually are.
    """
    declref = c.children[1].descend_to_declref()
    flags = c.children[2].eval_int()
    meth_flags = []
    for [mty, mflag] in METHOD_FLAGS.items():
        if flags & mflag:
            meth_flags.append(mty)
    meth_flags = tuple(sorted(meth_flags))
    expected_args = EXPECTED_ARGS[meth_flags]
    actual_args = count_sig_args(declref.type["qualType"])
    return expected_args - actual_args


def get_methods_to_fix(tree):
    """Locate method declarations with argument discrepancies and yield the pairs [name, expected_args - actual_args]."""
    for pymeth_decl in tree.find_decls("PyMethodDef"):
        if pymeth_decl.first_child.is_null_cast:
            continue
        arg_discrepancy = method_def_arg_discrepancy(pymeth_decl)
        if arg_discrepancy:
            declref = pymeth_decl.children[1].descend_to_declref()
            func_name = declref.referencedDecl.name
            yield [func_name, arg_discrepancy]


def count_sig_args(sig):
    """Count the args in the signature -- one more than number of commas."""
    return sig.count(",") + 1


def get_bad_getter_name(pygetset_decl):
    """Helper method for get_getsets_to_fix.

    Argument should be a PyGetSetDef initializer node.
    Check if node has a getter with the wrong number of arguments.
    If so yield [name of getter, expected_args - actual_args]
    """
    if len(pygetset_decl.children) <= 1:
        # There is no getter.
        return
    getter_node = pygetset_decl.children[1]
    if getter_node.kind == "ImplicitValueInitExpr":
        # There is no getter.
        return
    declref = getter_node.descend_to_declref()
    if not declref:
        # The getter is explicitly specified to be NULL (so still no getter).
        return
    sig = declref.type["qualType"]
    sig_args = count_sig_args(sig)
    if count_sig_args(sig) != 2:
        yield [declref.referencedDecl.name, 2 - sig_args]


def get_bad_setter_name(c):
    """Helper method for get_getsets_to_fix.

    Argument should be a PyGetSetDef initializer node.
    Check if node has a setter with the wrong number of arguments.
    If so yield [name of setter, expected_args - actual_args]
    """
    if len(c.children) <= 2:
        # There is no setter.
        return
    setter_node = c.children[2]
    if setter_node.kind == "ImplicitValueInitExpr":
        # There is no setter.
        return
    declref = setter_node.descend_to_declref()
    if not declref:
        # The setter is explicitly specified to be NULL (so still no setter).
        return
    sig = declref.type["qualType"]
    sig_args = count_sig_args(sig)
    if sig_args != 3:
        yield [declref.referencedDecl.name, 3 - sig_args]


def get_getsets_to_fix(tree):
    """Locate getters and setters with argument discrepancies and yield the pairs [name, expected_args - actual_args].
    expected_args - actual_args should be 1 but we keep track of it so if something weird happens we can throw an error.
    """
    for pygetset_decl in tree.find_decls("PyGetSetDef"):
        if pygetset_decl.first_child.is_null_cast:
            # In this case, we're the sentinel in a list.
            continue
        yield from get_bad_getter_name(pygetset_decl)
        yield from get_bad_setter_name(pygetset_decl)


def fix_func_decls(src_lines, tree, funcs_to_fix):
    """Fix the"""
    for t in tree.children:
        if not t.is_func_decl:
            continue
        if not t.name in funcs_to_fix:
            continue
        loc = t.loc
        if "expansionLoc" in loc:
            loc = loc["expansionLoc"]
        lineno = loc["line"]
        # llvm one-indexes line and column
        lineno -= 1
        line: str = src_lines[lineno]
        colno = line.rfind(")")
        arg_discrepancy = funcs_to_fix[t.name]
        if arg_discrepancy == 1:
            newline = line[:colno] + f", PyObject *ignored" + line[colno:]
        elif arg_discrepancy == -1:
            last_comma = line.rfind(",")
            newline = line[:last_comma] + ")\n"
        else:
            raise Exception(
                f"Can't change number of args in method declaration by {arg_discrepancy}."
                "Either patch the source file or update this script."
            )

        src_lines[lineno] = newline


def fix_call_exprs(src_lines, tree, funcs_to_fix):
    for call_expr in tree.iter_call_exprs():
        decl_ref = call_expr.first_child.descend_to_declref()
        if not decl_ref:
            continue
        name = decl_ref.referencedDecl.name
        if name not in funcs_to_fix:
            continue
        lineno = call_expr.find_line()
        colno = call_expr.get_end_col()
        lineno -= 1
        colno -= 1
        line: str = src_lines[lineno]
        arg_discrepancy = funcs_to_fix[name]
        if arg_discrepancy == 1:
            newline = line[:colno] + f", PyObject *ignored" + line[colno:]
        else:
            raise Exception(
                f"Can't change number of args in method call by {arg_discrepancy}."
                "Either patch the source file or update this script."
            )

        src_lines[lineno] = newline


def patch_source_file_inner(ast_filename, src_filename, in_place=False):
    tree = json.load(open(ast_filename, "r"), object_hook=create_node)
    # funcs_to_fix will be of the form:
    # name_of_func ==> expected_args - actual_args
    funcs_to_fix = {}
    funcs_to_fix.update(get_methods_to_fix(tree))
    funcs_to_fix.update(get_getsets_to_fix(tree))
    print(funcs_to_fix)

    if not funcs_to_fix:
        return
    print(f"Patched fpcasts in {src_filename}!")

    with open(src_filename, "r") as src:
        src_lines = list(src)
    fix_func_decls(src_lines, tree, funcs_to_fix)
    fix_call_exprs(src_lines, tree, funcs_to_fix)

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
