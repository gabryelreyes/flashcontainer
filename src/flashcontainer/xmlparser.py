
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

import lxml.etree as ET
import flashcontainer.datamodel as DM
from flashcontainer.byteconv import ByteConvert

import logging
import pathlib
import os

schema_file = os.path.join(pathlib.Path(__file__).parent.resolve(), "pargen_1.0.xsd")
NS = '{http://www.schulznorbert.de/1.0/pargen}'


class XmlParser:
    def __init__(self):
        pass

    @classmethod
    def from_file(cls, file: str) -> DM.Model:
        return cls.parse(file)

    @staticmethod
    def parse(file: str) -> DM.Model:
        """ Parse given XML file into datamodel. """
        model = None
        try:
            logging.info(f"Loading parameter definitons from {file}.")
            schema = ET.XMLSchema(ET.parse(schema_file))
            xml_doc = ET.parse(file)
            schema.assertValid(xml_doc)
            model = XmlParser._build_model(xml_doc.getroot(), file)

        except ET.DocumentInvalid as err:
            logging.critical(f"xml validation failed:\n{str(err.error_log)}")
            return None

        except Exception as e:
            logging.exception(str(e))
            return None

        return model

    @staticmethod
    def _get_optional(element: ET.Element, attr: str, default: str) -> str:
        """Get optional attribute value."""

        val = element.get(attr)
        if val is None:
            val = default

        return val

    @staticmethod
    def _parse_bool(val_str: str) -> bool:
        """ Parse input as boolean """

        result = False
        if val_str is not None:
            val_str = val_str.lower()
            if ("true" == val_str) or ("1" == val_str):
                result = True

        return result

    @staticmethod
    def _parse_int(val_str: str) -> int:
        """ Parse int as decimal or hex."""

        try:
            return int(val_str, base=10)
        except ValueError:
            return int(val_str, base=16)

    @staticmethod
    def get_alignment(element: ET.Element) -> int:
        """Parse alignment argument."""

        val_str = element.get("align")
        return 1 if (val_str is None) else XmlParser._parse_int(val_str)

    @staticmethod
    def get_endianess(element: ET.Element) -> DM.Endianness:
        """Parse alignment argument."""

        val_str = element.get("endianness")
        if val_str is not None:
            return DM.Endianness.LE if val_str == "LE" else DM.Endianness.BE

        else:
            return DM.Endianness.LE

    @staticmethod
    def get_fill(element: ET.Element) -> int:
        """Parse fill argument."""

        val_str = element.get("fill")
        return 0x00 if (val_str is None) else XmlParser._parse_int(val_str)

    @staticmethod
    def _parse_crc_config(element: ET.Element, start: int, end: int) -> DM.CrcConfig:
        """Parse a crc element.

        Args:
            element (ET.Element): The XML element to read
            start (int): Start address for crc computation
            end (int): End address for crc computation

        Returns:
            A CrcConfig from the datamodel
        """
        defaults = DM.CrcConfig()  # get defaults
        poly = defaults.poly
        width = defaults.width
        init = defaults.init
        revin = defaults.revin
        revout = defaults.revout
        xor = defaults.xor

        val = element.get('polynomial')
        if val is not None:
            poly = XmlParser._parse_int(val)

        width = DM.TYPE_DATA[DM.ParamType[element.get("type")]].size * 8

        val = element.get('init')
        if val is not None:
            init = XmlParser._parse_int(val)

        val = element.get('rev_in')
        if val is not None:
            revin = XmlParser._parse_bool(val)

        val = element.get('rev_out')
        if val is not None:
            revin = XmlParser._parse_bool(val)

        val = element.get('final_xor')
        if val is not None:
            xor = XmlParser._parse_bool(val)

        return DM.CrcConfig(poly, width, init, revin, revout, xor, start, end)

    @staticmethod
    def _build_parameters(block: DM.Block, element) -> None:
        data_element = element.find(f"{NS}data")
        running_addr = block.addr + 16  # 16 = sizeof header

        for parameter_element in data_element:

            offset = XmlParser.calc_addr(
                block.addr,
                running_addr,
                parameter_element.get("offset"),
                XmlParser.get_alignment(parameter_element))

            if (offset > running_addr):   # we need to insert a gap
                gap = DM.Parameter.as_gap(running_addr, offset-running_addr, block.fill)
                logging.info(f"    Gap {gap}")
                block.add_parameter(gap)

            name = parameter_element.get("name")
            ptype = DM.ParamType[parameter_element.get("type")]
            crc_cfg = None
            val_text = None

            if f"{NS}crc" == parameter_element.tag:
                start = XmlParser.calc_addr(
                    block.addr,
                    offset,
                    XmlParser._get_optional(parameter_element, "from", "0"),
                    1)
                end = XmlParser.calc_addr(
                    block.addr,
                    offset,
                    XmlParser._get_optional(parameter_element, "to", "."),
                    1)
                crc_cfg = XmlParser._parse_crc_config(parameter_element, start, end)
                val_text = '0x0'  # crc bits get calculated at end of block
                logging.info("    got CRC data: " + str(crc_cfg))
            else:
                value_element = parameter_element.find(f"{NS}value")
                val_text = value_element.text

            bytes = ByteConvert.json_to_bytes(ptype, block.endianess, val_text)

            parameter = DM.Parameter(offset, name, ptype, bytes, crc_cfg)

            comment = parameter_element.find(f"{NS}comment")
            if comment is not None:
                parameter.set_comment(comment.text)

            block.add_parameter(parameter)
            logging.info(f"    Adding {parameter}")
            running_addr = offset + len(bytes)

        end_addr = block.addr + (block.header.length)
        if (end_addr > running_addr):  # we need to insert a gap at the end
            gap = DM.Parameter.as_gap(running_addr, end_addr-running_addr, block.fill)
            logging.info(f"    Gap {gap}")
            block.add_parameter(gap)

    @staticmethod
    def _build_model(root: ET.Element, filename: str) -> DM.Model:
        model = DM.Model(filename)

        # iterate over container list
        for element in root:
            address = XmlParser._parse_int(element.get("at"))
            name = element.get("name")

            container = DM.Container(name, address)
            logging.info(f"Loading container definition for {name}")
            XmlParser._build_blocks(container, element)

            model.add_container(container)

        return model

    @staticmethod
    def calc_addr(base_addr: int, running_addr: int, offset_str: str, alignment: int) -> int:
        if ("." == offset_str):
            result_addr = running_addr

        else:
            result_addr = base_addr + XmlParser._parse_int(offset_str)

        if 1 < alignment:
            mod = result_addr % alignment
            if (0 != mod):
                result_addr += alignment - mod

        return result_addr

    @staticmethod
    def _build_blocks(container: DM.Container, element: ET.Element) -> None:
        """ Load block list for given container """

        running_addr = container.addr
        blocks_element = element.find(f"{NS}blocks")

        for element in blocks_element:
            align = XmlParser.get_alignment(element)
            block_addr = XmlParser.calc_addr(container.addr, running_addr, element.get("offset"), align)
            name = element.get("name")
            endianess = XmlParser.get_endianess(element)
            fill = XmlParser.get_fill(element)
            block = DM.Block(block_addr, name, endianess, fill)

            comment = element.find(f"{NS}comment")
            if comment is not None:
                block.set_comment(comment.text)

            logging.info(f"  Loading block definition {block}")

            # mandatory block header
            header_element = element.find(f"{NS}header")

            id = XmlParser._parse_int(header_element.get("id"))
            major = XmlParser._parse_int(header_element.get("major"))
            minor = XmlParser._parse_int(header_element.get("minor"))
            version = XmlParser._parse_int(header_element.get("version"))
            length = XmlParser._parse_int(header_element.get("length"))
            block.set_header(DM.BlockHeader(id, DM.Version(major, minor, version), length))

            XmlParser._build_parameters(block, element)

            block.update_crc()
            container.add_block(block)

            running_addr += length
