# BSD 3-Clause License
#
# Copyright (c) 2022, Haju Schulz (haju.schulz@online.de)
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import flashcontainer.datamodel as DM
from flashcontainer.byteconv import ByteConvert

from typing import Dict
from pathlib import Path
import json5


class PyHexDumpWriter(DM.Walker):
    """Create configuration file for pyHexDump (see https://github.com/BlueAndi/pyHexDump) """

    _TYPE_MAPPING = {
        DM.ParamType.uint32: ("u32le", "u32be"),
        DM.ParamType.uint8: ("u8", "u8"),
        DM.ParamType.uint16: ("u16le", "u16be"),
        DM.ParamType.uint64: ("u64le", "u64be"),
        DM.ParamType.int8: ("u8", "u8"),
        DM.ParamType.int16: ("u16le", "u16be"),
        DM.ParamType.int32: ("u32le", "u32be"),
        DM.ParamType.int64: ("u32le", "u32be"),    # 64 bit unsupported
        DM.ParamType.float32: ("u32le", "u32be"),  # float unsupported
        DM.ParamType.float64: ("u32le", "u32be"),  # float unsupported
        DM.ParamType.utf8: ("u8", "u8")
    }

    def __init__(self, model: DM.Model, options: Dict[str, any]):
        super().__init__(model, options)
        self.dmpfile = None
        self.elements = []

    def pre_run(self) -> None:
        filename = Path.joinpath(
            self.options.get("DESTDIR"),
            self.options.get("BASENAME") + ".pyhexdump")

        print(f"Generating pyHexDump config file {filename}.")

        self.dmpfile = filename.open(mode='w')

    def begin_parameter(self, param: DM.Parameter) -> None:
        """Add element to data array """

        element = {
            "name": f"{self.ctx_block.name}_{param.name}",
            "addr": f"{hex(param.offset)}",
            "dataType": self._TYPE_MAPPING[param.type][0 if self.ctx_block.endianess == DM.Endianness.LE else 1],
            "count": len(param.value) // ByteConvert.get_type_size(param.type)
        }

        self.elements.append(element)

    def post_run(self):
        """Close output file"""
        record = {
            "_comment_":
                [
                    f"Configuration file for pyHexDump, see https://github.com/BlueAndi/pyHexDump",
                    f"GENERATED by {self.options.get('PNAME')} {self.options.get('VERSION')} "
                    f"{self.options.get('DATETIME')}",
                    f"cmd: {self.options.get('CMDLINE')}",
                    f"Buildkey: {self.options.get('GUID')}"
                ],
            "elements": self.elements
            }

        json_str = json5.dumps(record, quote_keys=True, indent=4, trailing_commas=False)
        self.dmpfile.write(json_str)
        self.dmpfile.close()