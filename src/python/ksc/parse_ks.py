#####################################################################
# parse_ks: Convert s-expressions to Expr
from functools import partial
import sexpdata

from ksc.type import Type
from ksc.utils import ensure_list_of_lists
from ksc.expr import Def, EDef, GDef, Rule, Const, Var, Lam, Call, Let, If, Assert
from ksc.expr import pystr, StructuredName, make_structured_name

#####################################################################
## S-expression Utils

parser_source_file = "<unknown>"

# Exception for parse errors
class ParseError(Exception):
    pass


# Raise ParseError if cond not true
def check(cond, *message):
    def tostr(s):
        if isinstance(s, (sexpdata.SExpBase, list)):
            return sexpdata.dumps(s)
        else:
            return str(s)

    if not cond:
        message = "".join(tostr(s) for s in message)
        raise ParseError(f"{parser_source_file}: {message}")


# Parse a fixed-length s-exp into a list given a set of parsers, e.g.
# parse_seq(se, parse_name, parse_int, parse_int)
# would accept (fred 3 4)
def parse_seq(se, *parsers):
    check(len(se) == len(parsers), "Cannot parse ", se, " with ", parsers)

    return [parser(term) for (parser, term) in zip(parsers, se)]


# Reserved word constants
_def = sexpdata.Symbol("def")
_edef = sexpdata.Symbol("edef")
_gdef = sexpdata.Symbol("gdef")
_assert = sexpdata.Symbol("assert")
_if = sexpdata.Symbol("if")
_let = sexpdata.Symbol("let")
_lam = sexpdata.Symbol("lam")
_tuple = sexpdata.Symbol("tuple")
_rule = sexpdata.Symbol("rule")
_colon = sexpdata.Symbol(":")
_None = sexpdata.Symbol("None")


def parse_type_maybe(se, allow_Any: bool):
    """ Converts an S-Expression representing a type, like (Tensor 1 Float) or (Tuple Float (Tensor 1 Float)),
        into a Type object, e.g. Type.Tensor(1,Type.Float) or Type.Tuple(Type.Float, Type.Tensor(1,Type.Float)).
    """
    while isinstance(se, list) and len(se) == 1:
        se = se[0]  # Discard ((pointless)) brackets

    if isinstance(se, sexpdata.Symbol):
        if se == _None:
            return True, None
        sym = se.value()
        if Type.is_type_introducer(sym) and (allow_Any or sym != "Any"):
            return True, Type(sym)

        return False, None

    if isinstance(se, list) and len(se) > 0:
        if isinstance(se[0], sexpdata.Symbol):
            sym = se[0].value()
            if sym == "Tuple":
                return True, Type.Tuple(*(parse_type(s, allow_Any) for s in se[1:]))
            if sym == "Vec" and len(se) == 2:
                return True, Type.Tensor(1, parse_type(se[1], allow_Any))
            if sym == "Tensor" and len(se) == 3:
                return (
                    True,
                    Type.Tensor(parse_int(se[1]), parse_type(se[2], allow_Any)),
                )
            if sym == "Lam" and len(se) == 3:
                return (
                    True,
                    Type.Lam(
                        parse_type(se[1], allow_Any), parse_type(se[2], allow_Any)
                    ),
                )
            if sym == "LM" and len(se) == 3:
                return (
                    True,
                    Type.LM(parse_type(se[1], allow_Any), parse_type(se[2], allow_Any)),
                )

    return False, None


def parse_type(se, allow_Any=False):
    ok, ty = parse_type_maybe(se, allow_Any)
    if ok:
        return ty
    else:
        raise ParseError("Did not know how to parse type {}".format(se))


# "1.3" -> int
def parse_int(se):
    if isinstance(se, int):
        return se

    assert re.match(r"^\d+$", se)
    return int(se)


# "x" -> string
def parse_name(se):
    check(isinstance(se, sexpdata.Symbol), "Wanted identifier, got: ", se)
    return se.value()


# "x" or "[fwd x]" or "[fwd [x (Tuple Float String)]]" -> string (mangled function name)
def parse_structured_name(se):
    if isinstance(se, sexpdata.Symbol):
        return StructuredName(se.value())

    check(
        isinstance(se, sexpdata.Bracket),
        "Wanted identifier or [ident Type] or [ident <StructuredName>], got: ",
        se,
    )
    ses = se.value()
    assert len(ses) == 2
    se0 = parse_name(ses[0])
    ok, ty = parse_type_maybe(ses[1], allow_Any=False)
    if ok:
        return StructuredName((se0, ty))

    # Not a type, assume it's a StructuredName
    sn = parse_structured_name(ses[1])

    return StructuredName((se0, sn))


# "\"x\"" -> string
def parse_string(se):
    check(isinstance(se, str), "Expected string, got: ", se)
    return se


# "x : Float" -> Var(x, Type.Float)
def parse_arg(arg, allow_Type_Any=False):
    check(len(arg) >= 3, "Expect (arg : type), not: ", arg)
    check(arg[1] == _colon, "No colon: ", arg)

    return Var(parse_name(arg[0]), parse_type(arg[2:], allow_Any=allow_Type_Any))


# "((x : Float) (y : Integer))" -> [Var("x", Type.Float), Var("y", Type.Integer)]
def parse_args(se, allow_Type_Any=False):
    return [
        parse_arg(arg, allow_Type_Any=allow_Type_Any)
        for arg in ensure_list_of_lists(se)
    ]


def parse_expr(se, allow_Type_Any=False):
    # Otherwise, "x" -> a variable use
    if isinstance(se, sexpdata.Symbol):
        return Var(se.value(), None)

    # "1.2", "1", "'string'"
    if not isinstance(se, list):
        return Const(se)

    # Remaining forms are lists

    # Empty lists should not occur -- an empty tuple is (tuple)
    check(len(se) > 0, "Empty list")

    head = se[0]
    parse_subexp = partial(parse_expr, allow_Type_Any=allow_Type_Any)
    # If(cond, t, f)
    if head == _if:
        return If(*parse_seq(se[1:], parse_subexp, parse_subexp, parse_subexp))

    # Assert(cond, body)
    if head == _assert:
        return Assert(*parse_seq(se[1:], parse_subexp, parse_subexp))

    # Let(var, rhs, body)
    if head == _let:
        check(
            len(se) == 3,
            f"Let should have 2 terms (let (<binding>) body), not {len(se)-1} in",
            se,
        )
        binding = se[1]
        check(len(binding) == 2, "Let bindings should be pairs", binding, "in", se)
        lhs = binding[0]
        if isinstance(lhs, list):
            vars = [Var(parse_name(v)) for v in lhs]
        else:
            vars = Var(parse_name(lhs))
        rhs = parse_subexp(binding[1])
        body = parse_subexp(se[2])
        ans = Let(vars, rhs, body)
        return ans

    # Lam(var, type, body)
    if head == _lam:
        var = parse_arg(se[1], allow_Type_Any)
        body = parse_subexp(se[2])
        return Lam(var, body)

    # The remainder are calls
    return Call(parse_structured_name(head), [parse_subexp(se) for se in se[1:]])


# Parse a top-level definition (def, edef, rule)
def parse_tld(se):
    check(isinstance(se, list), "Non-list at top level", se)
    check(len(se) > 0, "Empty list at top level")
    head = se[0]
    if head == _def:
        return Def(
            *parse_seq(
                se[1:], parse_structured_name, parse_type, parse_args, parse_expr
            )
        )

    if head == _edef:
        return EDef(*parse_seq(se[1:], parse_structured_name, parse_type, parse_type))

    if head == _gdef:
        return GDef(*parse_seq(se[1:], parse_name, parse_structured_name))

    if head == _rule:
        parse_expr_allow_Any = partial(parse_expr, allow_Type_Any=True)
        return Rule(
            *parse_seq(
                se[1:],
                parse_string,
                partial(parse_args, allow_Type_Any=True),
                parse_expr_allow_Any,
                parse_expr_allow_Any,
            )
        )

    check(False, "unrecognised top-level definition:", se)


################################################################
import argparse
import sys
import re


def s_exps_from_string(string_or_stream, source_file_name=None):
    if source_file_name:
        global parser_source_file
        parser_source_file = source_file_name

    return sexpdata.Parser(
        string_or_stream, nil=None, true="true", false="false", line_comment=";"
    ).parse()


def parse_expr_string(string_or_stream):
    s_exps = s_exps_from_string(string_or_stream)
    assert len(s_exps) == 1
    return parse_expr(s_exps[0])


def strip_block_comments(string):
    # Strip block comments
    regex = r"""\#\|               # hash bar
                    (
                        [^\|\#]     # (not bar or hash)  Do not be tempted to suffix with "+" - bad perf
                    |               # or...
                        (\|(?!\#))  # (bar not followed by hash)
                    |               # or...
                        (\#(?!\|))  # (hash not followed by bar)
                    )*             # many times 
                    \|\#           # bar hash
                """
    regex = re.compile(regex, flags=re.DOTALL | re.VERBOSE)
    while True:
        string, n = re.subn(regex, "", string)
        if n == 0:
            # print(f"Zapped {n} block comment(s)")
            return string


def parse_ks_string(string_or_stream, source_file_name):
    global parser_source_file
    parser_source_file = source_file_name

    string = strip_block_comments(string_or_stream)

    for s_exp in s_exps_from_string(string):
        yield parse_tld(s_exp)


def parse_ks_file(string_or_stream):
    return parse_ks_string(string_or_stream, "<unknown>")


def parse_ks_filename(filename):
    with open(filename) as f:
        ks_str = f.read()
        return parse_ks_string(ks_str, filename)


def main():
    parser = argparse.ArgumentParser(prog="parse_ks.py", description=__doc__)
    parser.add_argument(
        "input_ks_file", nargs="?", type=str, default="test/ksc/syntax-primer.ks"
    )
    args = parser.parse_args()

    for x in parse_ks_filename(args.input_ks_file):
        print(pystr(x, 0))


if __name__ == "__main__":
    sys.exit(main())
