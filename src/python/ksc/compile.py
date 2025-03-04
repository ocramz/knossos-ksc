from dataclasses import dataclass
from typing import List

import atexit
import os
import subprocess
import sysconfig
import sys

from tempfile import NamedTemporaryFile
from tempfile import gettempdir

from torch.utils import cpp_extension

from ksc import cgen, utils
from ksc.cgen import VecSpec, VecSpec_None, VecSpec_Elementwise, VecSpec_VMap
from ksc.parse_ks import parse_ks_filename

preserve_temporary_files = False


@dataclass(frozen=True)
class CFlags:
    cl_flags: List[str]
    gcc_flags: List[str]

    def __add__(self, other):
        return CFlags(
            cl_flags=self.cl_flags + other.cl_flags,
            gcc_flags=self.gcc_flags + other.gcc_flags,
        )

    @staticmethod
    def All(cflags):
        return CFlags(cl_flags=cflags, gcc_flags=cflags)

    @staticmethod
    def Empty():
        return CFlags.All([])

    @staticmethod
    def GCCOnly(gcc_flags):
        return CFlags(cl_flags=[], gcc_flags=gcc_flags)


cl_flags_opt = ["/std:c++17", "/O2"]
cl_flags_debug = ["/std:c++17", "/Zi"]
gcc_flags_debug = ["-std=c++17", "-g", "-DKS_BOUNDS_CHECK"]
gcc_flags_opt = ["-std=c++17", "-g", "-O3"]

cflags_opt = CFlags(cl_flags=cl_flags_opt, gcc_flags=gcc_flags_opt)
cflags_debug = CFlags(cl_flags=cl_flags_debug, gcc_flags=gcc_flags_debug)
default_cflags = cflags_opt


def subprocess_run(cmd, env=None):
    return (
        subprocess.run(cmd, stdout=subprocess.PIPE, env=env).stdout.decode().strip("\n")
    )


def generate_cpp_from_ks(ks_str, ks_entry_points, preludes, prelude_headers):
    ksc_path, ksc_runtime_dir = utils.get_ksc_paths()

    with NamedTemporaryFile(mode="w", suffix=".ks", delete=False) as fks:
        fks.write(ks_str)
    with NamedTemporaryFile(mode="w", suffix=".kso", delete=False) as fkso:
        pass
    with NamedTemporaryFile(mode="w", suffix=".cpp", delete=False) as fcpp:
        pass

    print("generate_cpp_from_ks:", ksc_path, fks.name)
    ksc_command = [
        ksc_path,
        "--generate-cpp",
        *(
            opt
            for prelude in preludes
            for opt in ("--ks-source-file", f"{ksc_runtime_dir}/{prelude}")
        ),
        "--ks-source-file",
        fks.name,
        "--ks-output-file",
        fkso.name,
        *(opt for header in prelude_headers for opt in ("--cpp-include", header)),
        "--cpp-output-file",
        fcpp.name,
        "--remove-unused",
        *(
            opt
            for entry_point in ks_entry_points
            for opt in ("--used", str(entry_point))
        ),
    ]

    try:
        e = subprocess.run(ksc_command, capture_output=True, check=True,)
        print(e.stdout.decode("ascii"))
        print(e.stderr.decode("ascii"))
        decls = list(parse_ks_filename(fkso.name))
    except subprocess.CalledProcessError as e:
        ksc_command_str = " ".join(ksc_command)
        print(f"Command failed:\n{ksc_command_str}")
        print(f"KSC files {fks.name} {fkso.name} {fcpp.name}")
        print(f"ks_str=\n{ks_str}")
        print("KSC output:\n")
        print(e.output.decode("ascii"))
        ksc_stderr = e.stderr.decode("ascii")
        ksc_stderr_filtered = "> " + "\n> ".join(ksc_stderr.split("\n")[:-1])
        print(ksc_stderr_filtered + "\n")
        raise Exception(
            f"Command failed:\n"
            f"{ksc_command_str}\n"
            f"KSC output:\n"
            f"{ksc_stderr_filtered}\n"
            f"See additional information in stdout"
        ) from e

    # Read from CPP back to string
    with open(fcpp.name) as f:
        generated_cpp = f.read()

    # only delete these file if no error
    if not preserve_temporary_files:

        @atexit.register
        def _():
            print(
                "ksc.compile.generate_cpp_from_ks: Deleting",
                fks.name,
                fcpp.name,
                fkso.name,
            )
            os.unlink(fks.name)
            os.unlink(fcpp.name)
            os.unlink(fkso.name)

    return generated_cpp, decls


def build_py_module_from_cpp(cpp_str, profiling=False):
    """
    Build python module, independently of pytorch, non-ninja
    """
    _ksc_path, ksc_runtime_dir = utils.get_ksc_paths()
    pybind11_path = utils.get_ksc_dir() + "/extern/pybind11"

    with NamedTemporaryFile(mode="w", suffix=".cpp", delete=False) as fcpp:
        fcpp.write(cpp_str)

    extension_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if extension_suffix is None:
        extension_suffix = sysconfig.get_config_var("SO")

    with NamedTemporaryFile(mode="w", suffix=extension_suffix, delete=False) as fpymod:
        pass
    module_path = fpymod.name
    module_name = os.path.basename(module_path).split(".")[0]
    python_includes = subprocess_run(
        [sys.executable, "-m", "pybind11", "--includes"],
        env={"PYTHONPATH": pybind11_path},
    )
    cmd = (
        f"g++ -I{ksc_runtime_dir} -I{pybind11_path}/include "
        + python_includes
        + " -Wall -Wno-unused-variable -Wno-unused-but-set-variable"
        " -fmax-errors=1"
        " -std=c++17"
        " -fPIC"
        " -g -O3 -DIN_BUILD_FROM_CPP_NOT_USING_CFLAGS"
        + (" -pg" if profiling else "")
        + " -shared"
        + f" -DPYTHON_MODULE_NAME={module_name}"
        f" -o {module_path} " + fcpp.name
    )
    print(cmd)
    try:
        subprocess.run(cmd, shell=True, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"cpp_file={fcpp.name}")
        print(cmd)
        print(e.output.decode("utf-8"))
        print(e.stderr.decode("utf-8"))

        raise

    if not preserve_temporary_files:

        @atexit.register
        def _():
            print(
                "ksc.utils.build_py_module_from_cpp: Deleting", fcpp.name, fpymod.name,
            )
            os.unlink(fcpp.name)
            os.unlink(fpymod.name)

    return module_name, module_path


derivatives_to_generate_default = ["fwd", "rev"]


def generate_cpp_for_py_module_from_ks(
    ks_str,
    bindings_to_generate,
    python_module_name,
    vectorization: VecSpec = VecSpec_None(),
    use_aten=True,
    use_torch=False,
    gpu=False,
):
    """Returns two strings of C++ code:
       The first string contains definitions of all ksc-generated functions and entry points.
       The second string defines a pybind module which uses the entry points.
       These can either be compiled separately or concatenated into a single source file.
       """

    def mangled_with_type(structured_name):
        if not structured_name.has_type():
            raise ValueError(
                "Need a type on the structured name: " + str(structured_name)
            )
        return structured_name.mangled()

    bindings = [
        (python_name, "ks::entry_points::generated::" + python_name)
        for (python_name, _) in bindings_to_generate
    ]

    preludes = ["prelude.ks"] + (["prelude-aten.ks"] if use_aten else [])
    prelude_headers = ["prelude.h"] + (["prelude-aten.h"] if use_aten else [])
    cpp_ks_functions, decls = generate_cpp_from_ks(
        ks_str, [sn for _, sn in bindings_to_generate], preludes, prelude_headers
    )
    (
        cpp_entry_point_declarations,
        cpp_entry_point_definitions,
    ) = cgen.generate_cpp_entry_points(
        bindings_to_generate,
        decls,
        vectorization=vectorization,
        use_torch=use_torch,
        gpu=gpu,
    )
    cpp_pybind_module_declaration = generate_cpp_pybind_module_declaration(
        bindings, python_module_name
    )

    return (
        cpp_ks_functions + cpp_entry_point_definitions,
        cpp_entry_point_declarations + cpp_pybind_module_declaration,
    )


def generate_cpp_pybind_module_declaration(bindings_to_generate, python_module_name):
    def m_def(python_name, cpp_name):
        return f"""
        m.def("{python_name}", &{cpp_name});
        """

    return (
        """
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace ks {
namespace entry_points {

void reset_allocator();
size_t allocator_top();
size_t allocator_peak();

}
}

PYBIND11_MODULE("""
        + python_module_name
        + """, m) {
    m.def("reset_allocator", &ks::entry_points::reset_allocator);
    m.def("allocator_top", &ks::entry_points::allocator_top);
    m.def("allocator_peak", &ks::entry_points::allocator_peak);
"""
        + "\n".join(m_def(*t) for t in bindings_to_generate)
        + """
}
"""
    )


def build_py_module_from_ks(
    ks_str,
    bindings_to_generate,
    vectorization: VecSpec = VecSpec_None(),
    use_aten=False,
    use_torch=False,
):

    cpp_definitions, cpp_pybind = generate_cpp_for_py_module_from_ks(
        ks_str,
        bindings_to_generate,
        "PYTHON_MODULE_NAME",
        vectorization=vectorization,
        use_aten=use_aten,
        use_torch=use_torch,
    )

    cpp_str = cpp_definitions + cpp_pybind

    cpp_fname = (
        gettempdir() + "/ksc-pybind.cpp"
    )  # TODO temp name, but I want to solve a GC problem with temp names
    print(f"Saving to {cpp_fname}")
    with open(cpp_fname, "w") as fcpp:
        fcpp.write(cpp_str)

    module_name, module_path = build_py_module_from_cpp(cpp_str)
    return utils.import_module_from_path(module_name, module_path)


def build_module_using_pytorch_from_ks(
    ks_str,
    bindings_to_generate,
    torch_extension_name,
    vectorization: VecSpec = VecSpec_None(),
    use_aten=False,
    extra_cflags=[],
    gpu=False,
):
    """Uses PyTorch C++ extension mechanism to build and load a module

    * ks_str: str

      The text of a ks source file

    * bindings_to_generate : Iterable[Tuple[str, StructuredName]]

      The StructuredName is the ksc function to expose to Python.  The
      str is the Python name given to that function when exposed.
      Each StructuredName must have a type attached
    """
    cpp_definitions, cpp_pybind = generate_cpp_for_py_module_from_ks(
        ks_str,
        bindings_to_generate,
        "TORCH_EXTENSION_NAME",
        vectorization=vectorization,
        use_aten=use_aten,
        use_torch=True,
        gpu=gpu,
    )

    return build_module_using_pytorch_from_cpp_backend(
        [
            ("ksc-main.cu" if gpu else "ksc-main.cpp", cpp_definitions),
            ("ksc-pybind.cpp", cpp_pybind),
        ],
        torch_extension_name,
        extra_cflags,
    )


def build_module_using_pytorch_from_cpp(
    cpp_str, bindings_to_generate, torch_extension_name, extra_cflags=[]
):
    cpp_pybind = generate_cpp_pybind_module_declaration(
        bindings_to_generate, "TORCH_EXTENSION_NAME"
    )
    return build_module_using_pytorch_from_cpp_backend(
        [("ksc.cpp", cpp_str + cpp_pybind + '#include "knossos-entry-points.cpp"\n')],
        torch_extension_name,
        extra_cflags,
    )


def build_module_using_pytorch_from_cpp_backend(
    cpp_strs, torch_extension_name, extra_cflags
):
    __ksc_path, ksc_runtime_dir = utils.get_ksc_paths()

    # I don't like this assumption about Windows -> cl but it matches what PyTorch is currently doing:
    # https://github.com/pytorch/pytorch/blob/ad8d1b2aaaf2ba28c51b1cb38f86311749eff755/torch/utils/cpp_extension.py#L1374-L1378
    # We're making a guess here if people recognifigure their C++ compiler on Windows it's because they're using non-MSVC
    # otherwise we need to inspect the end of the path path for cl[.exe].

    cpp_compiler = os.environ.get("CXX")
    if cpp_compiler == None and sys.platform == "win32":
        extra_cflags = extra_cflags.cl_flags
    else:
        extra_cflags = extra_cflags.gcc_flags

    verbose = True

    # https://pytorch.org/docs/stable/cpp_extension.html
    build_directory = (
        utils.get_ksc_build_dir() + "/torch_extensions/" + torch_extension_name
    )
    os.makedirs(build_directory, exist_ok=True)

    def source_path(filename):
        return os.path.join(build_directory, filename)

    for filename, cpp_str in cpp_strs:
        utils.write_file_if_different(
            "#include <torch/extension.h>\n" + cpp_str, source_path(filename), verbose
        )

    module = cpp_extension.load(
        name=torch_extension_name,
        sources=[source_path(filename) for filename, _ in cpp_strs],
        extra_include_paths=[ksc_runtime_dir],
        extra_cflags=extra_cflags,
        extra_cuda_cflags=extra_cflags + ["-DKS_CUDA"],
        build_directory=build_directory,
        verbose=verbose,
    )

    return module
