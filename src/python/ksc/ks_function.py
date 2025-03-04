from ksc.utils import translate_and_import
from ksc.compile import build_py_module_from_ks
from ksc.expr import make_structured_name
from ksc.shape import ShapeType, shape_type_from_object
from ksc.type import make_tuple_if_many


class KsFunction:
    def __init__(
        self, name, return_type, arg_name_types, ks_str, is_edef=False, is_builtin=False
    ):
        self._name = name
        self._return_type = return_type
        if len(arg_name_types) == 0:
            self._arg_names = ()
            self._arg_types = ()
        else:
            self._arg_names, self._arg_types = zip(*arg_name_types)
        self._is_edef = is_edef
        self._is_builtin = is_builtin
        self._ks_str = ks_str
        self._py_mod = None

    @property
    def name(self):
        return self._name

    @property
    def return_type(self):
        return self._return_type

    @property
    def is_edef(self):
        return self._is_edef

    @property
    def is_builtin(self):
        return self._is_builtin

    @property
    def ks_str(self):
        return self._ks_str

    def combined_ks_str(self):
        return self.ks_str

    @property
    def arg_names(self):
        return self._arg_names

    @property
    def arg_types(self):
        return self._arg_types

    def __call__(self, *args, backend="jax"):
        for i, (arg, arg_type) in enumerate(zip(args, self._arg_types)):
            actual_type = shape_type_from_object(arg).type
            assert (
                actual_type == arg_type
            ), f"In the {i+1}th argument of {self.name}, expected {arg_type} but got {actual_type}"
        ks_str = self.combined_ks_str()
        name_to_call = self.name
        print(ks_str)
        if backend == "cpp":
            if self._py_mod is None:
                self._py_mod = build_py_module_from_ks(
                    ks_str,
                    [
                        (
                            "entry",
                            make_structured_name(
                                (self.name, make_tuple_if_many(self._arg_types))
                            ),
                        )
                    ],
                )
        else:
            if self._py_mod is None:
                self._py_mod = translate_and_import(__file__, ks_str, backend)
        if hasattr(self._py_mod, "defs"):
            return self._py_mod.defs[name_to_call](*args)
        else:
            return self._py_mod.entry(*args)
