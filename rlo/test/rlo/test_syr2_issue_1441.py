# fmt: off
import os

from rlo import expr_sets
from rlo import rewrites
from rlo import utils

def test_syr2_issue_1441():
    blas_test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../src/rlo/ksc/blas/blas_test.kso")
    e = dict(expr_sets.ExpressionSetFromFile(blas_test_path).named_exprenvs())["syr2"]
    seq  = [(67, "commute_add"), (137, "inline_call"), (140, "inline_call"), (144, "inline_call"), (213, "inline_call"), (37, "delete_let"), (175, "inline_call"), (0, "delete_let"), (142, "inline_call"), (0, "delete_let"), (39, "inline_let"), (38, "select_of_tuple"), (42, "inline_let"), (31, "delete_let"), (36, "select_of_tuple"), (40, "inline_let"), (44, "inline_let"), (46, "inline_let"), (37, "delete_let"), (51, "inline_let"), (34, "delete_let"), (51, "inline_let"), (31, "delete_let"), (52, "inline_let"), (51, "select_of_tuple"), (72, "inline_let"), (27, "delete_let"), (49, "select_of_tuple"), (53, "inline_let"), (62, "inline_let"), (53, "delete_let"), (52, "size_of_build"), (59, "inline_let"), (68, "inline_let"), (59, "delete_let"), (57, "index_of_build"), (66, "inline_let"), (57, "delete_let"), (56, "size_of_build"), (59, "inline_let"), (50, "delete_let"), (62, "inline_let"), (47, "delete_let"), (64, "inline_let"), (27, "delete_let"), (53, "inline_let"), (44, "delete_let"), (42, "index_of_build"), (51, "inline_let"), (42, "delete_let"), (40, "index_of_build"), (48, "inline_let"), (40, "delete_let"), (62, "inline_let"), (61, "select_of_tuple"), (65, "inline_let"), (54, "delete_let"), (59, "select_of_tuple"), (63, "inline_let"), (67, "inline_let"), (69, "inline_let"), (60, "delete_let"), (74, "inline_let"), (57, "delete_let"), (74, "inline_let"), (54, "delete_let"), (75, "inline_let"), (74, "select_of_tuple"), (95, "inline_let"), (50, "delete_let"), (72, "select_of_tuple"), (76, "inline_let"), (85, "inline_let"), (76, "delete_let"), (75, "size_of_build"), (82, "inline_let"), (91, "inline_let"), (82, "delete_let"), (80, "index_of_build"), (89, "inline_let"), (80, "delete_let"), (79, "size_of_build"), (82, "inline_let"), (73, "delete_let"), (85, "inline_let"), (70, "delete_let"), (87, "inline_let"), (50, "delete_let"), (76, "inline_let"), (67, "delete_let"), (65, "index_of_build"), (74, "inline_let"), (65, "delete_let"), (63, "index_of_build"), (71, "inline_let"), (63, "delete_let"), (74, "inline_let"), (73, "select_of_tuple"), (77, "inline_let"), (47, "delete_let"), (52, "select_of_tuple"), (75, "inline_let"), (84, "inline_let"), (75, "delete_let"), (74, "size_of_build"), (81, "inline_let"), (90, "inline_let"), (81, "delete_let"), (79, "index_of_build"), (90, "inline_let"), (79, "delete_let"), (78, "size_of_build"), (81, "inline_let"), (72, "delete_let"), (88, "inline_let"), (47, "delete_let"), (90, "inline_let"), (47, "delete_let"), (77, "inline_let"), (68, "delete_let"), (66, "index_of_build"), (77, "inline_let"), (66, "delete_let"), (64, "index_of_build"), (74, "inline_let"), (64, "delete_let"), (76, "inline_let"), (75, "select_of_tuple"), (104, "inline_let"), (24, "delete_let"), (54, "select_of_tuple"), (77, "inline_let"), (86, "inline_let"), (77, "delete_let"), (76, "size_of_build"), (83, "inline_let"), (92, "inline_let"), (83, "delete_let"), (81, "index_of_build"), (92, "inline_let"), (81, "delete_let"), (80, "size_of_build"), (83, "inline_let"), (74, "delete_let"), (90, "inline_let"), (24, "delete_let"), (71, "inline_let"), (62, "delete_let"), (60, "index_of_build"), (71, "inline_let")]
    for node_id, rule_name in seq:
        rw = utils.single_elem([r for r in rewrites.rule(rule_name).get_all_rewrites(e) if r.node_id == node_id])
        print("Matched", (node_id, rule_name))
        e = rw.apply(e)
