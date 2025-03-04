import pytest
import re

from ksc.type import Type
from ksc.expr import (
    Def,
    EDef,
    GDef,
    Rule,
    Const,
    Var,
    Lam,
    Call,
    Let,
    If,
    Assert,
    StructuredName,
    make_structured_name,
)

from ksc.parse_ks import (
    parse_tld,
    parse_expr_string,
    ParseError,
    s_exps_from_string,
    strip_block_comments,
)


def tld(s):
    return parse_tld(s_exps_from_string(s)[0])


def test_parses():
    Var_a_Float = Var("a", Type.Float)
    Var_b_Float = Var("b", Type.Float)
    Var_a = Var("a", None)
    Var_b = Var("b", None)
    f = make_structured_name("f")

    assert tld("(def f Float () 1.1)") == Def(f, Type.Float, [], Const(1.1))

    assert tld("(def [rev [f (Tuple)]] Float () 1.1)") == Def(
        make_structured_name(("rev", ("f", Type.Tuple()))), Type.Float, [], Const(1.1)
    )

    assert tld("(edef f Float (Tuple (Float) (Vec Float)))") == EDef(
        f, Type.Float, Type.Tuple(Type.Float, Type.Tensor(1, Type.Float))
    )

    assert tld("(gdef rev [f (Tuple (Float) (Vec Float))])") == GDef(
        "rev",
        make_structured_name(("f", Type.Tuple(Type.Float, Type.Tensor(1, Type.Float)))),
    )

    assert tld('(rule "f" ((a : Float) (b : Float)) a b)') == Rule(
        "f", [Var_a_Float, Var_b_Float], Var_a, Var_b
    )

    assert tld("(def f Float ((a : Float)) a)") == Def(
        f, Type.Float, [Var_a_Float], Var_a
    )

    assert tld("(def f Float ((a : Float) (b : Float)) (add a b))") == Def(
        f, Type.Float, [Var_a_Float, Var_b_Float], Call("add", [Var_a, Var_b])
    )

    assert tld("(def f Bool () true)") == Def(f, Type.Bool, [], Const(True))

    assert parse_expr_string("(assert a b)") == Assert(Var_a, Var_b)
    assert parse_expr_string("(if a a b)") == If(Var_a, Var_a, Var_b)
    assert parse_expr_string("(let (a b) a)") == Let(Var_a, Var_b, Var_a)
    assert parse_expr_string("(lam (a : Float) a)") == Lam(Var_a_Float, Var_a)
    assert parse_expr_string("(let ((a b) (tuple 1 2)) a)") == Let(
        [Var_a, Var_b], Call("tuple", [Const(1), Const(2)]), Var_a
    )


def test_expr():
    Var_a_Float = Var("a", Type.Float)
    Var_a = Var("a", None)
    Var_b = Var("b", None)
    Var_a1 = Var("a", None)

    l = Lam(Var_a_Float, Var_a)
    l1 = Lam(Var_a_Float, Var_a1)
    assert l == l1
    assert l != Lam(Var_a_Float, Var_b)
    assert Lam(Var_a_Float, Var_b) != Assert(Var_a_Float, Var_b)


def test_errors():
    with pytest.raises(ParseError, match="Empty list at top level"):
        tld("()")
    with pytest.raises(ParseError, match="Empty list"):
        parse_expr_string("()")
    with pytest.raises(ParseError, match="Let bindings should be pairs"):
        parse_expr_string("(let (a) 2)")


def check(pattern, s):
    assert re.match(
        re.compile(pattern, flags=re.DOTALL | re.MULTILINE), strip_block_comments(s)
    )


def test_any_type_allowed_only_for_rules():
    with pytest.raises(ParseError, match="parse type.*Any"):
        tld("(def foo Float (x : Any) 3.0)")
    with pytest.raises(ParseError, match="parse type.*Any"):
        tld("(def foo Any (x : Float) x)")

    tld('(rule "foo" (x : Any) x x)')
    tld(
        """
(rule "map_to_build" ((body : Any) (v : Vec Any))
    (map (lam (e : Any) body) v)
    (build n (lam (i : Integer) (let (e (index i v)) body))))"""
    )


def test_comments():
    check(r"^A  1$", "A #| b |# 1")
    check(
        r"^\s+stay\s+$",
        """
            #| go | 
        ;      # go |#
        stay
            #|O1  | #|O2|C2|#|# 
            """,
    )
    check(
        r"^\s+a\s+b\s+c\s+d\s+$",
        """
    #| x | 
;      # y |#
a
    #|O1  | #|O2|C2|#|# b
c #|# |#d
    #|d  | #||#|#


    #|  | #||#|#
    """,
    )


if __name__ == "__main__":
    test_parses()
