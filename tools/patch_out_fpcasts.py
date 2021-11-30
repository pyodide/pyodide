import re
from typing import List, Optional

first_interesting_char_re = re.compile(".*?(?=[a-zA-Z<])")
func_decl_name_re = re.compile("([A-Za-z0-9_]*) '")
parm_column_re = re.compile("col:([0-9]*)")
location_info_re = re.compile(
    "<([a-zA-Z._/]*):([0-9]*)(:[0-9]*)?(, ([a-z]*):([0-9]*)(:[0-9]*)?)?>( ([a-z]*):([0-9]*)(:[0-9]*)?)?"
)


class Tree:
    def __init__(self, ty: str, info: str):
        self.children: List[Tree] = []
        self.parent: Optional[Tree] = None
        self.type: str = ty
        self.info: str = info
        self.start_loc = (0, 0)
        self.end_loc = (0, 0)
        self.next_loc = (0, 0)
        self.file = None

    @property
    def first_child(self):
        return self.children[0]

    def add_child(self, child: "Tree"):
        self.children.append(child)
        child.parent = self

    def walk(self):
        yield self
        for t in self.children:
            yield from t.walk()

    def iter_call_exprs(self):
        next = self.children
        if self.is_call_expr:
            yield self
            next = next[1:]
        for t in next:
            yield from t.iter_call_exprs()

    def descend_to_declref(self):
        while not self.is_decl_ref:
            if "NullToPointer" in self.info:
                return
            self = self.first_child
        return self

    def get_declref_name(self):
        lidx = self.info.rfind("'", 0, -1)
        func_name_idx = self.info.rfind("'", 0, lidx - 2)
        func_name = self.info[func_name_idx + 1 : lidx - 2]
        return func_name

    def get_declref_sig(self):
        lidx = self.info.rfind("'", 0, -1)
        sig = self.info[lidx + 1 : -1]
        return sig

    def find_decls(self, name):
        for t in self.children:
            if not t.is_var_decl and not t.is_init_list_expr:
                continue
            if not t.children:
                continue
            if t.is_var_decl:
                t = t.first_child
            if t.info.find(f"'{name}'") != -1 or t.info.find(f"'struct {name}'") != -1:
                yield t
            else:
                yield from t.find_decls(name)

    @property
    def is_call_expr(self):
        return self.type == "CallExpr"

    @property
    def is_func_decl(self):
        return self.type == "FunctionDecl"

    @property
    def is_var_decl(self):
        return self.type == "VarDecl"

    @property
    def is_param_decl(self):
        return self.type == "ParmVarDecl"

    @property
    def is_decl_ref(self):
        return self.type == "DeclRefExpr"

    @property
    def is_init_list_expr(self):
        return self.type == "InitListExpr"

    def get_func_decl_name(self):
        return func_decl_name_re.search(self.info).groups()[0]

    def get_func_decl_line(self):
        if not self.is_func_decl:
            raise TypeError("Only makes sense on FunctionDecl nodes.")
        if "line:" in self.info:
            linestr = self.info.rpartition("line:")[2].partition(":")[0]
        else:
            linestr = self.info.rpartition(", col")[0].split(":")[1]
        line = int(linestr)
        return line

    def pretty_lines(self, prefix="", last_child=False, root=True):
        output = prefix
        if last_child:
            output += "`-"
            prefix += " "
        elif not root:
            output += "-"
        if not root:
            prefix += " "
        output += self.type + " " + self.info
        yield output
        for child in self.children[:-1]:
            yield from child.pretty_lines(prefix + "|", root=False)
        if self.children:
            yield from self.children[-1].pretty_lines(
                prefix, last_child=True, root=False
            )

    def pretty_print(self):
        for line in self.pretty_lines():
            print(line)

    def eval_int(self):
        if self.type == "IntegerLiteral":
            return int(self.info.rpartition(" ")[-1])
        if self.type == "ParenExpr":
            return self.first_child.eval_int()
        if self.type == "BinaryOperator":
            binop = self.info.rpartition(" ")[-1]
            if binop == "'|'":
                return self.children[0].eval_int() | self.children[1].eval_int()
            raise ValueError("Unexpected binop" + binop)
        raise ValueError("Unexpected type " + self.type)


class TreeBuilder:
    def __init__(self):
        self.last_depth: int = -1
        self.last_tree: Optional[Tree] = None
        self.tree: Optional[Tree] = None
        self.file: Optional[str] = None

    def add_node(self, depth: int, ty: str, info: str):
        info = info.partition(" ")[2]
        tree = Tree(ty, info)
        parent = self.last_tree
        last_depth = self.last_depth
        self.last_depth = depth
        self.last_tree = tree
        if depth == 0:
            self.tree = tree
            return
        levels_up = last_depth + 1 - depth
        for _ in range(levels_up):
            if not parent:
                raise RuntimeError()
            parent = parent.parent
        if not parent:
            raise RuntimeError()
        if parent.children:
            last_sibling = parent.children[-1]
            last_loc = last_sibling.end_loc
        else:
            last_loc = parent.next_loc
        m = location_info_re.search(info)
        start_line = 0
        start_col = 0
        end_line = 0
        end_col = 0
        next_line = 0
        next_col = 0
        if m:
            gps = m.groups()
            if gps[0] == "col":
                start_line = last_loc[0]
                start_col = int(gps[1])
            else:
                start_line = int(gps[1])
                start_col = int(gps[2][1:])
                if gps[0] != "line":
                    file = gps[0]

            if gps[4] == "col":
                end_line = start_line
                end_col = int(gps[5])
            elif gps[4]:
                end_line = int(gps[5])
                end_col = int(gps[6][1:])
            else:
                end_line = start_line
                end_col = start_col

            if gps[8] == "col":
                next_line = start_line
                next_col = int(gps[9])
            elif gps[8]:
                next_line = int(gps[9])
                next_col = int(gps[10][1:])
            else:
                next_line = start_line
                next_col = start_col

        tree.start_loc = (start_line, start_col)
        tree.end_loc = (end_line, end_col)
        tree.next_loc = (next_line, next_col)
        parent.add_child(tree)

    def build_from_iter(self, iter):
        for line in iter:
            indent = first_interesting_char_re.search(line).end()
            rest = line[indent:-1]
            [ty, _, info] = rest.partition(" ")
            depth: int = indent // 2
            self.add_node(depth, ty, info)
        return self


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
    sig = declref.get_declref_sig()

    flags = c.children[2].eval_int()
    meth_flags = []
    for [mty, mflag] in METHOD_FLAGS.items():
        if flags & mflag:
            meth_flags.append(mty)
    meth_flags = tuple(sorted(meth_flags))
    expected_args = EXPECTED_ARGS[meth_flags]
    return count_sig_args(sig) != expected_args


def get_method_defs_to_fix(tree):
    for pymeth_decl in tree.find_decls("PyMethodDef"):
        if "NullToPointer" in pymeth_decl.first_child.info:
            continue
        if is_bad_method_def(pymeth_decl):
            declref = pymeth_decl.children[1].descend_to_declref()
            func_name = declref.get_declref_name()
            yield func_name


def count_sig_args(sig):
    return sig.count(",") + 1


def get_bad_getset_names(c):
    if len(c.children) <= 1:
        return
    getter_node = c.children[1]
    if getter_node.type != "ImplicitValueInitExpr":
        declref = getter_node.descend_to_declref()
        if declref:
            sig = declref.get_declref_sig()

            if count_sig_args(sig) != 2:
                yield declref.get_declref_name()

    if len(c.children) <= 2:
        return
    setter_node = c.children[2]
    if setter_node.type != "ImplicitValueInitExpr":
        declref = setter_node.descend_to_declref()
        if declref:
            sig = declref.get_declref_sig()
            if count_sig_args(sig) != 3:
                yield declref.get_declref_name()


def get_getset_defs_to_fix(tree):
    for pygetset_decl in tree.find_decls("PyGetSetDef"):
        if "NullToPointer" in pygetset_decl.first_child.info:
            continue
        yield from get_bad_getset_names(pygetset_decl)
        if False:
            yield


def fix_func_decls(src_lines, tree, target_names):
    target_names = set(target_names)
    for t in tree.children:
        if not t.is_func_decl:
            continue
        fname = t.get_func_decl_name()
        if not fname in target_names:
            continue
        lineno = t.next_loc[0]
        # llvm one-indexes line and column
        lineno -= 1
        line: str = src_lines[lineno]
        colno = line.rfind(")")
        if fname not in line:
            continue
        newline = line[:colno] + ", PyObject *ignored" + line[colno:]
        src_lines[lineno] = newline


def patch_source_file_inner(ast_filename, src_filename, in_place=False):
    with open(ast_filename, "r") as ast:
        tree = TreeBuilder().build_from_iter(ast).tree
    # sys.exit(0)
    funcs_to_fix = []
    funcs_to_fix.extend(get_method_defs_to_fix(tree))
    funcs_to_fix.extend(get_getset_defs_to_fix(tree))

    if not funcs_to_fix:
        return
    print("Patched fpcasts in", src_filename, "!")

    with open(src_filename, "r") as src:
        src_lines = list(src)
    fix_func_decls(src_lines, tree, funcs_to_fix)
    for call_expr in tree.iter_call_exprs():
        decl_ref = call_expr.first_child.descend_to_declref()
        name = decl_ref.get_declref_name()
        if name in funcs_to_fix:
            lineno, colno = call_expr.end_loc
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
