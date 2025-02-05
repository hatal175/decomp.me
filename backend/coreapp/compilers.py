from functools import cache
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, OrderedDict

from django.conf import settings
from coreapp.flags import (
    COMMON_CLANG_FLAGS,
    COMMON_GCC_FLAGS,
    COMMON_IDO_FLAGS,
    COMMON_MWCC_FLAGS,
    COMMON_GCC_PS1_FLAGS,
    FlagSet,
    Flags,
)

from coreapp import platforms

from coreapp.platforms import GBA, GC_WII, N64, NDS_ARM9, Platform, PS1, PS2, SWITCH

logger = logging.getLogger(__name__)

CONFIG_PY = "config.py"
COMPILER_BASE_PATH: Path = settings.COMPILER_BASE_PATH


@dataclass(frozen=True)
class Compiler:
    id: str
    cc: str
    platform: Platform
    flags: ClassVar[Flags]
    base_id: Optional[str] = None
    is_gcc: ClassVar[bool] = False
    is_ido: ClassVar[bool] = False
    is_mwcc: ClassVar[bool] = False
    needs_wine = False

    @property
    def path(self) -> Path:
        return COMPILER_BASE_PATH / (self.base_id or self.id)

    def available(self) -> bool:
        # consider compiler binaries present if the compiler's directory is found
        return self.path.exists()


@dataclass(frozen=True)
class Preset:
    name: str
    flags: str
    compiler: Compiler

    def to_json(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "flags": self.flags,
            "compiler": self.compiler.id,
        }


@dataclass(frozen=True)
class DummyCompiler(Compiler):
    flags: ClassVar[Flags] = []

    def available(self) -> bool:
        return settings.DUMMY_COMPILER


@dataclass(frozen=True)
class ClangCompiler(Compiler):
    flags: ClassVar[Flags] = COMMON_CLANG_FLAGS


@dataclass(frozen=True)
class GCCCompiler(Compiler):
    is_gcc: ClassVar[bool] = True
    flags: ClassVar[Flags] = COMMON_GCC_FLAGS


@dataclass(frozen=True)
class GCCPS1Compiler(GCCCompiler):
    flags: ClassVar[Flags] = COMMON_GCC_PS1_FLAGS


@dataclass(frozen=True)
class IDOCompiler(Compiler):
    is_ido: ClassVar[bool] = True
    flags: ClassVar[Flags] = COMMON_IDO_FLAGS


@dataclass(frozen=True)
class MWCCCompiler(Compiler):
    is_mwcc: ClassVar[bool] = True
    flags: ClassVar[Flags] = COMMON_MWCC_FLAGS


def from_id(compiler_id: str) -> Compiler:
    if compiler_id not in _compilers:
        raise ValueError(f"Unknown compiler: {compiler_id}")
    return _compilers[compiler_id]


def available_compilers() -> List[Compiler]:
    return sorted(
        _compilers.values(),
        key=lambda c: (c.platform.id, c.id),
    )


def available_platforms() -> List[Platform]:
    return sorted(
        set(compiler.platform for compiler in available_compilers()),
        key=lambda p: p.name,
    )


@cache
def available_presets(platform: Platform) -> List[Preset]:
    return [p for p in _presets if p.compiler.platform == platform]


DUMMY = DummyCompiler(id="dummy", platform=platforms.DUMMY, cc="")

# GBA
AGBCC = GCCCompiler(
    id="agbcc",
    platform=GBA,
    cc='cc -E -I "${COMPILER_DIR}"/include -iquote include -nostdinc -undef "$INPUT" | "${COMPILER_DIR}"/bin/agbcc $COMPILER_FLAGS -o - | arm-none-eabi-as -mcpu=arm7tdmi -o "$OUTPUT"',
)

OLD_AGBCC = GCCCompiler(
    id="old_agbcc",
    platform=GBA,
    cc='cc -E -I "${COMPILER_DIR}"/include -iquote include -nostdinc -undef "$INPUT" | "${COMPILER_DIR}"/bin/old_agbcc $COMPILER_FLAGS -o - | arm-none-eabi-as -mcpu=arm7tdmi -o "$OUTPUT"',
    base_id="agbcc",
)

AGBCCPP = GCCCompiler(
    id="agbccpp",
    platform=GBA,
    cc='cc -E -I "${COMPILER_DIR}"/include -iquote include -nostdinc -undef "$INPUT" | "${COMPILER_DIR}"/bin/agbcp -quiet $COMPILER_FLAGS -o - | arm-none-eabi-as -mcpu=arm7tdmi -o "$OUTPUT"',
)

# Switch
CLANG_391 = ClangCompiler(
    id="clang-3.9.1",
    platform=SWITCH,
    cc='TOOLROOT="$COMPILER_DIR" "$COMPILER_DIR"/bin/clang++ -target aarch64-linux-elf --sysroot="$COMPILER_DIR"/botw-lib-musl-25ed8669943bee65a650700d340e451eda2a26ba -D_LIBCPP_HAS_MUSL_LIBC -fuse-ld=lld -mcpu=cortex-a57+fp+simd+crypto+crc -mno-implicit-float -fstandalone-debug -fPIC -Wl,-Bsymbolic-functions -shared -stdlib=libc++ -nostdlib $COMPILER_FLAGS -o "$OUTPUT" "$INPUT"',
)

CLANG_401 = ClangCompiler(
    id="clang-4.0.1",
    platform=SWITCH,
    cc='TOOLROOT="$COMPILER_DIR" "$COMPILER_DIR"/bin/clang++ -target aarch64-linux-elf --sysroot="$COMPILER_DIR"/botw-lib-musl-25ed8669943bee65a650700d340e451eda2a26ba -fuse-ld=lld -mcpu=cortex-a57+fp+simd+crypto+crc -mno-implicit-float -fstandalone-debug -fPIC -Wl,-Bsymbolic-functions -shared -stdlib=libc++ -nostdlib $COMPILER_FLAGS -o "$OUTPUT" "$INPUT"',
)

# PS1
GCC263_MIPSEL = GCCPS1Compiler(
    id="gcc2.6.3-mipsel",
    platform=PS1,
    cc='mips-linux-gnu-cpp -Wall -lang-c -gstabs "$INPUT" | "${COMPILER_DIR}"/cc1 -mips1 -mcpu=3000 $COMPILER_FLAGS | mips-linux-gnu-as -march=r3000 -mtune=r3000 -no-pad-sections -O1 -o "$OUTPUT"',
)

PSYQ_CC = 'cpp -P "$INPUT" | unix2dos | ${WINE} ${COMPILER_DIR}/CC1PSX.EXE -quiet ${COMPILER_FLAGS} -o "$OUTPUT".s && ${WINE} ${COMPILER_DIR}/ASPSX.EXE "$OUTPUT".s -o "$OUTPUT".obj && ${COMPILER_DIR}/psyq-obj-parser "$OUTPUT".obj -o "$OUTPUT"'
PSYQ40 = GCCPS1Compiler(
    id="psyq4.0",
    platform=PS1,
    cc=PSYQ_CC,
)

PSYQ41 = GCCPS1Compiler(
    id="psyq4.1",
    platform=PS1,
    cc=PSYQ_CC,
)

PSYQ43 = GCCPS1Compiler(
    id="psyq4.3",
    platform=PS1,
    cc=PSYQ_CC,
)

PSYQ46 = GCCPS1Compiler(
    id="psyq4.6",
    platform=PS1,
    cc=PSYQ_CC,
)

GCC_PSYQ_CC = 'cpp -P "$INPUT" | unix2dos | ${WINE} ${COMPILER_DIR}/CC1PSX.EXE -quiet ${COMPILER_FLAGS} | ${COMPILER_DIR}/mips-elf-as -EL -march=r3000 -mtune=r3000 -G0 -o "$OUTPUT"'

GCC272PSYQ = GCCPS1Compiler(
    id="gcc2.7.2-psyq",
    platform=PS1,
    cc=GCC_PSYQ_CC,
)

GCC281PSYQ = GCCPS1Compiler(
    id="gcc2.8.1-psyq",
    platform=PS1,
    cc=GCC_PSYQ_CC,
)

GCC2952PSYQ = GCCPS1Compiler(
    id="gcc2.95.2-psyq",
    platform=PS1,
    cc=GCC_PSYQ_CC,
)

# PS2
EE_GCC296 = GCCCompiler(
    id="ee-gcc2.96",
    platform=PS2,
    cc='"${COMPILER_DIR}"/bin/ee-gcc -c -B "${COMPILER_DIR}"/bin/ee- $COMPILER_FLAGS "$INPUT" -o "$OUTPUT"',
)

# N64
IDO53 = IDOCompiler(
    id="ido5.3",
    platform=N64,
    cc='TOOLROOT="$COMPILER_DIR" "$COMPILER_DIR/usr/bin/cc" -c -Xcpluscomm -G0 -non_shared -Wab,-r4300_mul -woff 649,838,712 -32 $COMPILER_FLAGS -o "$OUTPUT" "$INPUT"',
)

IDO71 = IDOCompiler(
    id="ido7.1",
    platform=N64,
    cc='TOOLROOT="$COMPILER_DIR" "$COMPILER_DIR/usr/bin/cc" -c -Xcpluscomm -G0 -non_shared -Wab,-r4300_mul -woff 649,838,712 -32 $COMPILER_FLAGS -o "$OUTPUT" "$INPUT"',
)

GCC272KMC = GCCCompiler(
    id="gcc2.7.2kmc",
    platform=N64,
    cc='COMPILER_PATH="${COMPILER_DIR}" "${COMPILER_DIR}"/gcc -c -G0 -mgp32 -mfp32 ${COMPILER_FLAGS} "${INPUT}" -o "${OUTPUT}"',
)

GCC281 = GCCCompiler(
    id="gcc2.8.1",
    platform=N64,
    cc='"${COMPILER_DIR}"/gcc -G0 -c -B "${COMPILER_DIR}"/ $COMPILER_FLAGS "$INPUT" -o "$OUTPUT"',
)

# GC_WII
MWCCEPPC_CC = '${WINE} "${COMPILER_DIR}/mwcceppc.exe" -c -proc gekko -nostdinc -stderr ${COMPILER_FLAGS} -o "${OUTPUT}" "${INPUT}"'

MWCC_233_144 = MWCCCompiler(
    id="mwcc_233_144",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_233_159 = MWCCCompiler(
    id="mwcc_233_159",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)
MWCC_233_163 = MWCCCompiler(
    id="mwcc_233_163",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_233_163E = MWCCCompiler(
    id="mwcc_233_163e",
    platform=GC_WII,
    cc='${WINE} "${COMPILER_DIR}/mwcceppc.125.exe" -c -proc gekko -nostdinc -stderr ${COMPILER_FLAGS} -o "${OUTPUT}.1" "${INPUT}" && ${WINE} "${COMPILER_DIR}/mwcceppc.exe" -c -proc gekko -nostdinc -stderr ${COMPILER_FLAGS} -o "${OUTPUT}.2" "${INPUT}" && python3 "${COMPILER_DIR}/frank.py" "${OUTPUT}.1" "${OUTPUT}.2" "${OUTPUT}"',
)

MWCC_242_81 = MWCCCompiler(
    id="mwcc_242_81",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_247_92 = MWCCCompiler(
    id="mwcc_247_92",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_247_105 = MWCCCompiler(
    id="mwcc_247_105",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_247_107 = MWCCCompiler(
    id="mwcc_247_107",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_247_108 = MWCCCompiler(
    id="mwcc_247_108",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_41_60831 = MWCCCompiler(
    id="mwcc_41_60831",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_41_60126 = MWCCCompiler(
    id="mwcc_41_60126",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_42_142 = MWCCCompiler(
    id="mwcc_42_142",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_43_151 = MWCCCompiler(
    id="mwcc_43_151",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_43_172 = MWCCCompiler(
    id="mwcc_43_172",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

MWCC_43_213 = MWCCCompiler(
    id="mwcc_43_213",
    platform=GC_WII,
    cc=MWCCEPPC_CC,
)

# NDS_ARM9
MWCCARM_CC = '${WINE} "${COMPILER_DIR}/mwccarm.exe" -c -proc arm946e -nostdinc -stderr ${COMPILER_FLAGS} -o "${OUTPUT}" "${INPUT}"'

MWCC_20_72 = MWCCCompiler(
    id="mwcc_20_72",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_20_79 = MWCCCompiler(
    id="mwcc_20_79",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_20_82 = MWCCCompiler(
    id="mwcc_20_82",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_20_84 = MWCCCompiler(
    id="mwcc_20_84",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_20_87 = MWCCCompiler(
    id="mwcc_20_87",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_114 = MWCCCompiler(
    id="mwcc_30_114",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_123 = MWCCCompiler(
    id="mwcc_30_123",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_126 = MWCCCompiler(
    id="mwcc_30_126",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_131 = MWCCCompiler(
    id="mwcc_30_131",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_133 = MWCCCompiler(
    id="mwcc_30_133",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_134 = MWCCCompiler(
    id="mwcc_30_134",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_136 = MWCCCompiler(
    id="mwcc_30_136",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_137 = MWCCCompiler(
    id="mwcc_30_137",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_138 = MWCCCompiler(
    id="mwcc_30_138",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_30_139 = MWCCCompiler(
    id="mwcc_30_139",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1018 = MWCCCompiler(
    id="mwcc_40_1018",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1024 = MWCCCompiler(
    id="mwcc_40_1024",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1026 = MWCCCompiler(
    id="mwcc_40_1026",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1027 = MWCCCompiler(
    id="mwcc_40_1027",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1028 = MWCCCompiler(
    id="mwcc_40_1028",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1034 = MWCCCompiler(
    id="mwcc_40_1034",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1036 = MWCCCompiler(
    id="mwcc_40_1036",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

MWCC_40_1051 = MWCCCompiler(
    id="mwcc_40_1051",
    platform=NDS_ARM9,
    cc=MWCCARM_CC,
)

_all_compilers: List[Compiler] = [
    DUMMY,
    # GBA
    AGBCC,
    OLD_AGBCC,
    AGBCCPP,
    # Switch
    CLANG_391,
    CLANG_401,
    # PS1
    GCC263_MIPSEL,
    PSYQ40,
    PSYQ41,
    PSYQ43,
    PSYQ46,
    GCC272PSYQ,
    GCC281PSYQ,
    GCC2952PSYQ,
    # PS2
    EE_GCC296,
    # N64
    IDO53,
    IDO71,
    GCC272KMC,
    GCC281,
    # GC_WII
    MWCC_233_144,
    MWCC_233_159,
    MWCC_233_163,
    MWCC_233_163E,
    MWCC_242_81,
    MWCC_247_92,
    MWCC_247_105,
    MWCC_247_107,
    MWCC_247_108,
    MWCC_41_60831,
    MWCC_41_60126,
    MWCC_42_142,
    MWCC_43_151,
    MWCC_43_172,
    MWCC_43_213,
    # NDS
    MWCC_20_72,
    MWCC_20_79,
    MWCC_20_82,
    MWCC_20_84,
    MWCC_20_87,
    MWCC_30_114,
    MWCC_30_123,
    MWCC_30_126,
    MWCC_30_131,
    MWCC_30_133,
    MWCC_30_134,
    MWCC_30_136,
    MWCC_30_137,
    MWCC_30_138,
    MWCC_30_139,
    MWCC_40_1018,
    MWCC_40_1024,
    MWCC_40_1026,
    MWCC_40_1027,
    MWCC_40_1028,
    MWCC_40_1034,
    MWCC_40_1036,
    MWCC_40_1051,
]

_all_presets = [
    # GBA
    Preset(
        "Rhythm Tengoku",
        "-mthumb-interwork -Wparentheses -O2 -fhex-asm",
        AGBCC,
    ),
    Preset(
        "The Minish Cap",
        "-O2 -Wimplicit -Wparentheses -Werror -Wno-multichar -g3",
        AGBCC,
    ),
    Preset(
        "Mother 3",
        "-fno-exceptions -fno-rtti -fhex-asm -mthumb-interwork -Wimplicit -Wparentheses -O2 -g3",
        AGBCCPP,
    ),
    # Switch
    Preset(
        "Super Mario Odyssey",
        "-x c++ -O3 -g2 -std=c++1z -fno-rtti -fno-exceptions -Wall -Wextra -Wdeprecated -Wno-unused-parameter -Wno-unused-private-field -fno-strict-aliasing -Wno-invalid-offsetof -D SWITCH -D NNSDK -D MATCHING_HACK_NX_CLANG",
        CLANG_391,
    ),
    Preset(
        "Breath of the Wild",
        "-x c++ -O3 -g2 -std=c++1z -fno-rtti -fno-exceptions -Wall -Wextra -Wdeprecated -Wno-unused-parameter -Wno-unused-private-field -fno-strict-aliasing -Wno-invalid-offsetof -D SWITCH -D NNSDK -D MATCHING_HACK_NX_CLANG",
        CLANG_401,
    ),
    # PS1
    Preset(
        "Castlevania: Symphony of the Night",
        "-O2 -G0 -funsigned-char",
        GCC263_MIPSEL,
    ),
    Preset(
        "Evo's Sapce Adventures",
        "-O2",
        PSYQ46,
    ),
    # N64
    Preset("Super Mario 64", "-O1 -g -mips2", IDO53),
    Preset("Mario Kart 64", "-O2 -mips2", IDO53),
    Preset("GoldenEye / Perfect Dark", "-Olimit 2000 -mips2 -O2", IDO53),
    Preset("Diddy Kong Racing", "-O2 -mips1", IDO53),
    Preset("Dinosaur Planet", "-O2 -g3 -mips2", IDO53),
    Preset("Dinosaur Planet (DLLs)", "-O2 -g3 -mips2 -KPIC", IDO53),
    Preset("Ocarina of Time", "-O2 -mips2", IDO71),
    Preset("Majora's Mask", "-O2 -g3 -mips2", IDO71),
    Preset("Mario Party 3", "-O1 -mips2", GCC272KMC),
    Preset("Paper Mario", "-O2 -fforce-addr", GCC281),
    # GC_WII
    Preset(
        "Super Monkey Ball",
        "-O4,p -nodefaults -fp hard -Cpp_exceptions off -enum int -inline auto",
        MWCC_233_159,
    ),
    Preset(
        "Super Mario Sunshine",
        "-lang=c++ -Cpp_exceptions off -fp hard -O4 -nodefaults -enum int -rostr",
        MWCC_233_163,
    ),
    Preset(
        "Pikmin",
        "-lang=c++ -nodefaults -Cpp_exceptions off -RTTI on -fp hard -O4,p",
        MWCC_233_163E,
    ),
    Preset(
        "Super Smash Bros. Melee",
        "-O4,p -nodefaults -fp hard -Cpp_exceptions off -enum int -fp_contract on -inline auto",
        MWCC_233_163E,
    ),
    Preset(
        "Battle for Bikini Bottom",
        "-lang=c++ -g -Cpp_exceptions off -RTTI off -fp hard -fp_contract on -O4,p -maxerrors 1 -str reuse,pool,readonly -char unsigned -enum int -use_lmw_stmw on -inline off",
        MWCC_247_92,
    ),
    Preset(
        "Pikmin 2",
        "-lang=c++ -nodefaults -Cpp_exceptions off -RTTI off -fp hard -fp_contract on -rostr -O4,p -use_lmw_stmw on -enum int -inline auto -sdata 8 -sdata2 8",
        MWCC_247_107,
    ),
    Preset(
        "The Thousand-Year Door",
        "-fp hard -fp_contract on -enum int -O4,p -sdata 48 -sdata2 6 -rostr -multibyte -use_lmw_stmw on -inline deferred -Cpp_exceptions off",
        MWCC_247_108,
    ),
    Preset(
        "Twilight Princess",
        "-lang=c++ -Cpp_exceptions off -nodefaults -O3 -fp hard -msgstyle gcc -str pool,readonly,reuse -RTTI off -maxerrors 1 -enum int",
        MWCC_247_108,
    ),
    Preset(
        "Super Paper Mario (DOL)",
        "-lang=c99 -enc SJIS -fp hard -O4 -use_lmw_stmw on -str pool -rostr -inline all -sdata 4 -sdata2 4",
        MWCC_41_60831,
    ),
    Preset(
        "Super Paper Mario (REL)",
        "-lang=c99 -enc SJIS -fp hard -O4 -use_lmw_stmw on -str pool -rostr -ipa file -sdata 0 -sdata2 0 -pool off -ordered-fp-compares",
        MWCC_41_60831,
    ),
    Preset(
        "Wii Sports",
        "-lang=c++ -enum int -inline auto -Cpp_exceptions off -RTTI off -fp hard -O4,p -nodefaults",
        MWCC_41_60831,
    ),
    Preset(
        "Super Mario Galaxy",
        "-Cpp_exceptions off -stdinc -nodefaults -fp hard -lang=c++ -inline auto,level=2 -ipa file -O4,s -rtti off -sdata 4 -sdata2 4 -enum int",
        MWCC_41_60126,
    ),
    # NDS
    Preset(
        "Pokémon Diamond / Pearl",
        "-O4,p -gccext,on -fp soft -lang c99 -Cpp_exceptions off -interworking -enum int",
        MWCC_30_123,
    ),
    Preset(
        "Pokémon HeartGold / SoulSilver",
        "-O4,p -enum int -lang c99 -Cpp_exceptions off -gccext,on -gccinc -interworking -gccdep -MD",
        MWCC_30_137,
    ),
    Preset(
        "Mario Party 4",
        "-O0,p -str pool -fp hard -Cpp_exceptions off",
        MWCC_242_81,
    ),
]


_compilers = OrderedDict({c.id: c for c in _all_compilers if c.available()})
_presets = [p for p in _all_presets if p.compiler.available()]

logger.info(f"Enabled {len(_compilers)} compiler(s): {', '.join(_compilers.keys())}")
logger.info(
    f"Available platform(s): {', '.join([platform.id for platform in available_platforms()])}"
)
