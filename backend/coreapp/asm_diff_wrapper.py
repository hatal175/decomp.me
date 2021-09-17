from coreapp import compiler_wrapper
from coreapp.models import Assembly, Compilation
from coreapp.sandbox import Sandbox
from coreapp.compiler_wrapper import PATH
from typing import Any, Dict, Optional
import json
import logging
import subprocess

from asm_differ.diff import AARCH64_SETTINGS, MIPS_SETTINGS, PPC_SETTINGS, ArchSettings, Config, Display, JsonFormatter, restrict_to_function

logger = logging.getLogger(__name__)

MAX_FUNC_SIZE_LINES = 5000

class AsmDifferWrapper:
    @staticmethod
    def create_config(arch_str: str, arch: ArchSettings) -> Config:
        return Config(
            arch=arch,
            # Build/objdump options
            diff_obj=True,
            make=False,
            source=False,
            source_old_binutils=False,
            inlines=False,
            max_function_size_lines=MAX_FUNC_SIZE_LINES,
            max_function_size_bytes=MAX_FUNC_SIZE_LINES * 4,
            # Display options
            formatter=JsonFormatter(arch_str=arch_str),
            threeway=None,
            base_shift=0,
            skip_lines=0,
            compress=None,
            show_branches=True,
            show_line_numbers=True,
            stop_jrra=False,
            ignore_large_imms=False,
            ignore_addr_diffs=False,
            algorithm="levenshtein",
        )

    @staticmethod
    def run_objdump(target_data: bytes, config: Config) -> Optional[str]:
        flags = ["-drzl"]

        with Sandbox() as sandbox:
            target_path = sandbox.path / "out.s"
            target_path.write_bytes(target_data)

            try:
                objdump_proc = sandbox.run_subprocess(
                    ["mips-linux-gnu-objdump"] + config.arch.arch_flags + flags + [sandbox.rewrite_path(target_path)],
                    shell=True,
                    env={
                        "PATH": PATH,
                    },
                )
            except subprocess.CalledProcessError as e:
                logger.error(e)
                return None

        out = objdump_proc.stdout
        return out

    @staticmethod
    def diff(target_assembly: Assembly, compilation: Compilation) -> Dict[str, Any]:
        compiler_arch = compiler_wrapper.CompilerWrapper.arch_from_compiler(compilation.compiler)

        # TODO: Use `diff.get_arch()` after refactoring it to throw an exception
        if compiler_arch == "mips":
            arch = MIPS_SETTINGS
        elif compiler_arch == "aarch64":
            arch = AARCH64_SETTINGS
        elif compiler_arch == "ppc":
            arch = PPC_SETTINGS
        else:
            logger.error(f"Unsupported arch: {compiler_arch}. Continuing assuming mips")
            compiler_arch = "mips"
            arch = MIPS_SETTINGS
            
        config = AsmDifferWrapper.create_config(compiler_arch, arch)

        # Base
        if len(target_assembly.elf_object) == 0:
            logger.info("Base asm empty - attempting to regenerate")
            compiler_wrapper.CompilerWrapper.assemble_asm(compiler_arch, target_assembly.source_asm, target_assembly)
            if len(target_assembly.elf_object) == 0:
                logger.error("Regeneration of base-asm failed")
                return {"error": "Error: Base asm empty"}

        basedump = AsmDifferWrapper.run_objdump(target_assembly.elf_object, config)
        if not basedump:
            return {"error": "Error running asm-differ on basedump"}

        # New
        if len(compilation.elf_object) == 0:
            logger.info("New asm empty - attempting to regenerate")
            compiler_wrapper.CompilerWrapper.compile_code(
                compilation.compiler,
                compilation.cc_opts or "",
                compilation.source_code,
                compilation.context,
                compilation
            )
            if len(compilation.elf_object) == 0:
                logger.error("Regeneration of new-asm failed")
                return {"error": "Error: New asm empty"}

        mydump = AsmDifferWrapper.run_objdump(compilation.elf_object, config)
        if not mydump:
            return {"error": "Error running asm-differ on mydump"}

        # Remove first few junk lines from objdump output
        basedump = "\n".join(basedump.split("\n")[6:])
        mydump = "\n".join(mydump.split("\n")[6:])

        display = Display(basedump, mydump, config)

        # TODO: It would be nice to get a python object from `run_diff()` to avoid the
        # JSON roundtrip. See https://github.com/simonlindholm/asm-differ/issues/56
        result = json.loads(display.run_diff()[0])
        result["error"] = None

        return result
