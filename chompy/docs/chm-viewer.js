// CHM Viewer with VFS Asset Loading
let pyodide = null;
let currentFile = null;
const blobUrlCache = new Map();

// Initialize Pyodide
async function initPyodide() {
    if (pyodide) return pyodide;
    
    updateLoadingStatus("Initializing Pyodide...");
    pyodide = await loadPyodide();
    
    updateLoadingStatus("Setting up environment...");
    
    updateLoadingStatus("Loading CHM parsing code...");
    await setupCHMParser();
    
    return pyodide;
}

// Python modules embedded as strings
const PYTHON_MODULES = {
    "pychmlib/chm.py": "# Copyright 2009 Wayne See\n#\n# Licensed under the Apache License, Version 2.0 (the \"License\");\n# you may not use this file except in compliance with the License.\n# You may obtain a copy of the License at\n#\n#     http://www.apache.org/licenses/LICENSE-2.0\n#\n# Unless required by applicable law or agreed to in writing, software\n# distributed under the License is distributed on an \"AS IS\" BASIS,\n# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n# See the License for the specific language governing permissions and\n# limitations under the License.\n\n\nfrom struct import unpack, pack\n\nfrom . import lzx\n\n_CHARSET_TABLE = {\n    0x0804: \"gbk\",\n    0x0404: \"big5\",\n    0xC04: \"big5\",\n    0x0401: \"iso-8859-6\",\n    0x0405: \"ISO-8859-2\",\n    0x0408: \"ISO-8859-7\",\n    0x040D: \"ISO-8859-8\",\n    0x0411: \"euc-jp\",\n    0x0412: \"euc-kr\",\n    0x041F: \"ISO-8859-9\",\n}\n\n_ITSF_MAX_LENGTH = 0x60\n_ITSP_MAX_LENGTH = 0x54\n_RESET_TABLE = \"::DataSpace/Storage/MSCompressed/Transform/{7FC28940-9D31-11D0-9B27-00A0C91E9C7C}/InstanceData/ResetTable\"\n_CONTENT = \"::DataSpace/Storage/MSCompressed/Content\"\n_LZXC_CONTROLDATA = \"::DataSpace/Storage/MSCompressed/ControlData\"\n\n\nclass _CHMFile:\n    \"a class to manage access to CHM files\"\n\n    def __init__(self, filename):\n        self.filename = filename\n        self.file = open(filename, \"rb\")\n        self._parse_chm()\n\n    def _parse_chm(self):\n        try:\n            self.itsf = self._get_ITSF()\n            self.encoding = self._get_encoding()\n            self.itsp = self._get_ITSP()\n            self._dir_offset = self.itsf.dir_offset + self.itsp.length\n            self.pmgi = self._get_PMGI()\n            entry = self.resolve_object(_RESET_TABLE)\n            self.lrt = self._get_LRT(entry)\n            entry = self.resolve_object(_CONTENT)\n            self._lzx_block_length = entry.length\n            self._lzx_block_offset = entry.offset + self.itsf.data_offset\n            entry = self.resolve_object(_LZXC_CONTROLDATA)\n            self.clcd = self._get_CLCD(entry)\n        except:\n            # in case of errors, close file as it will not be used again\n            self.file.close()\n            raise\n\n    def enumerate_files(self, condition=None):\n        pmgl = self._get_PMGL(self.itsp.first_pmgl_block)\n        while pmgl:\n            for ui in pmgl.entries():\n                if condition and condition(ui):\n                    yield ui\n                elif not condition:\n                    yield ui\n            pmgl = self._get_PMGL(pmgl.next_block)\n\n    def content_files(self):\n        def content_only(ui):\n            name = ui.name\n            if (\n                name.startswith(\"/\")\n                and len(name) > 1\n                and not (name.startswith(\"/#\") or name.startswith(\"/$\"))\n            ):\n                return True\n\n        return self.enumerate_files(content_only)\n\n    def get_hhc(self):\n        def hhc_only(ui):\n            name = ui.name\n            if name.endswith(\".hhc\"):\n                return True\n\n        for content in self.enumerate_files(hhc_only):\n            return content\n        return None\n\n    def all_files(self):\n        return self.enumerate_files()\n\n    def retrieve_object(self, unit_info):\n        return unit_info.get_content()\n\n    def resolve_object(self, filename):\n        filename = filename.lower()\n        start = self.itsp.first_pmgl_block\n        stop = self.itsp.last_pmgl_block\n        if self.pmgi:\n            entries = self.pmgi.entries\n            for name, block in entries:\n                if filename <= name:\n                    start = block - 1\n                    break\n            else:\n                start = len(entries) - 1\n        while True:\n            pmgl = self._get_PMGL(start)\n            for ui in pmgl.entries():\n                if filename == ui.name:\n                    return ui\n            else:\n                if start == stop:\n                    return None\n                else:\n                    start = pmgl.next_block\n\n    def _get_PMGL(self, start):\n        if start == -1:\n            return None\n        return self._pmgl(\n            self._get_segment(\n                self._dir_offset + start * self.itsp.dir_block_length,\n                self.itsp.dir_block_length,\n            )\n        )\n\n    def _get_encoding(self):\n        lang_id = self.itsf.lang_id\n        return _CHARSET_TABLE.get(lang_id, \"iso-8859-1\")\n\n    def _get_PMGI(self):\n        if self.itsp.index_depth == 2:\n            return self._pmgi(\n                self._get_segment(\n                    self._dir_offset\n                    + self.itsp.index_root * self.itsp.dir_block_length,\n                    self.itsp.dir_block_length,\n                )\n            )\n        else:\n            return None\n\n    def _get_LRT(self, entry):\n        return self._lrt(\n            self._get_segment(self.itsf.data_offset + entry.offset, entry.length)\n        )\n\n    def _get_CLCD(self, entry):\n        return self._clcd(\n            self._get_segment(self.itsf.data_offset + entry.offset, entry.length)\n        )\n\n    def _get_ITSF(self):\n        return self._itsf(self._get_segment(0, _ITSF_MAX_LENGTH))\n\n    def _get_ITSP(self):\n        offset = self.itsf.dir_offset\n        return self._itsp(self._get_segment(offset, _ITSP_MAX_LENGTH))\n\n    def _get_segment(self, start, length):\n        self.file.seek(start)\n        return self.file.read(length)\n\n    def _itsf(self, segment):\n        section = _Section()\n        fmt = \"<i i 4x 4x l 16x 16x 16x l 4x l 4x\"\n        (\n            section.version,\n            section.length,\n            section.lang_id,\n            section.dir_offset,\n            section.dir_length,\n        ) = unpack(fmt, segment[4:88])\n        if section.version == 3:\n            (section.data_offset,) = unpack(\"<l 4x\", segment[88:96])\n        else:\n            section.data_offset = section.dir_offset + section.dir_length\n        return section\n\n    def _itsp(self, segment):\n        section = _Section()\n        fmt = \"<i i 4x l 4x i i i i\"\n        (\n            section.version,\n            section.length,\n            section.dir_block_length,\n            section.index_depth,\n            section.index_root,\n            section.first_pmgl_block,\n            section.last_pmgl_block,\n        ) = unpack(fmt, segment[4:40])\n        return section\n\n    def _pmgl(self, segment):\n        section = _Section()\n        fmt = \"<l 4x 4x i\"\n        free_space, section.next_block = unpack(fmt, segment[4:20])\n        br = len(segment) - 20 - free_space\n        by = segment[20 : 20 + br]\n\n        def entries():\n            pointer = 0\n            bytes = by\n            bytes_remaining = br\n            while bytes_remaining > 0:\n                iter_read = 0\n                ui = UnitInfo(self)\n                name_length, bytes_read = self._get_encint(bytes, pointer)\n                pointer += bytes_read\n                iter_read += bytes_read\n                ui.name = str(bytes[pointer : pointer + name_length], \"utf-8\").lower()\n                pointer += name_length\n                iter_read += name_length\n                ui.compressed, bytes_read = self._get_encint(bytes, pointer)\n                pointer += bytes_read\n                iter_read += bytes_read\n                ui.offset, bytes_read = self._get_encint(bytes, pointer)\n                pointer += bytes_read\n                iter_read += bytes_read\n                ui.length, bytes_read = self._get_encint(bytes, pointer)\n                pointer += bytes_read\n                iter_read += bytes_read\n                bytes_remaining -= iter_read\n                yield ui\n\n        section.entries = entries\n        return section\n\n    def _pmgi(self, segment):\n        section = _Section()\n        fmt = \"<l\"\n        free_space = unpack(fmt, segment[4:8])[0]\n        bytes_remaining = len(segment) - 8 - free_space\n        bytes = segment[8 : 8 + bytes_remaining]\n        pointer = 0\n        entries = []\n        while bytes_remaining > 0:\n            iter_read = 0\n            name_length, bytes_read = self._get_encint(bytes, pointer)\n            pointer += bytes_read\n            iter_read += bytes_read\n            name = str(bytes[pointer : pointer + name_length], \"utf-8\").lower()\n            pointer += name_length\n            iter_read += name_length\n            block, bytes_read = self._get_encint(bytes, pointer)\n            pointer += bytes_read\n            iter_read += bytes_read\n            bytes_remaining -= iter_read\n            entries.append((name, block))\n        section.entries = entries\n        return section\n\n    def _lrt(self, segment):\n        section = _Section()\n        blocks = (len(segment) - 40) // 8\n        fmt = \"<32x l 4x \" + (\"l 4x \" * int(blocks))\n        result = unpack(fmt, segment)\n        section.block_length = result[0]\n        section.block_addresses = result[1:]\n        return section\n\n    def _clcd(self, segment):\n        section = _Section()\n        fmt = \"<4x 4x l l l 4x 4x\"\n        section.version, section.reset_interval, section.window_size = unpack(\n            fmt, segment\n        )\n        if section.version == 2:\n            section.window_size = section.window_size * 0x8000\n        return section\n\n    def _get_encint(self, bytes, start):\n        pointer = start\n        # Handle both Python 2 and 3 - in Python 3, bytes[i] already returns int\n        if isinstance(bytes[pointer], int):\n            byte = bytes[pointer]\n        else:\n            byte = ord(bytes[pointer])\n        pointer += 1\n        bi = 0\n        while byte > 127:\n            bi = (bi << 7) + (byte & 0x7F)\n            if isinstance(bytes[pointer], int):\n                byte = bytes[pointer]\n            else:\n                byte = ord(bytes[pointer])\n            pointer += 1\n        bi = (bi << 7) + (byte & 0x7F)\n        return bi, pointer - start\n\n    def close(self):\n        self.file.close()\n\n    __del__ = close\n\n\nclass _Section:\n    pass\n\n\nclass UnitInfo:\n\n    def __init__(self, chm, name=None, compressed=False, length=0, offset=0):\n        self.chm = chm\n        self.name = name\n        self.compressed = compressed\n        self.length = length\n        self.offset = offset\n\n    def get_content(self):\n        if self.compressed == False:\n            data = self.chm._get_segment(\n                self.chm.itsf.data_offset + self.offset, self.length\n            )\n            # For HTML/text content, try to decode as string, otherwise return bytes\n            if self.name.endswith(\n                (\".htm\", \".html\", \".hhc\", \".hhk\", \".css\", \".js\", \".txt\")\n            ):\n                try:\n                    if isinstance(data, bytes):\n                        return data.decode(self.chm.encoding, errors=\"ignore\")\n                    else:\n                        return data\n                except (UnicodeDecodeError, AttributeError):\n                    return data\n            return data\n        else:\n            bytes_per_block = self.chm.lrt.block_length\n            start_block = self.offset // bytes_per_block\n            end_block = (self.offset + self.length) // bytes_per_block\n            start_offset = self.offset % bytes_per_block\n            end_offset = (self.offset + self.length) % bytes_per_block\n            ini_block = start_block - start_block % self.chm.clcd.reset_interval\n            data = [None for i in range(end_block - start_block + 1)]\n            start = ini_block\n            block = self._get_lzx_block(start)\n            while start <= end_block:\n                if start == start_block and start == end_block:\n                    data[0] = block.content[start_offset:end_offset]\n                    break\n                if start == start_block:\n                    data[0] = block.content[start_offset:]\n                if start > start_block and start < end_block:\n                    data[start - start_block] = block.content\n                if start == end_block:\n                    data[start - start_block] = block.content[0:end_offset]\n                    break\n                start += 1\n                if start % self.chm.clcd.reset_interval == 0:\n                    block = self._get_lzx_block(start)\n                else:\n                    block = self._get_lzx_block(start, block)\n            byte_list = self._flatten(data)\n            return pack(\"B\" * len(byte_list), *byte_list)\n\n    def _get_lzx_segment(self, block):\n        addresses = self.chm.lrt.block_addresses\n        if block < len(addresses) - 1:\n            length = addresses[block + 1] - addresses[block]\n        else:\n            length = self.chm._lzx_block_length - addresses[block]\n        return self.chm._get_segment(\n            self.chm._lzx_block_offset + addresses[block], length\n        )\n\n    def _get_lzx_block(self, block_no, prev_block=None):\n        return lzx.create_lzx_block(\n            block_no,\n            self.chm.clcd.window_size,\n            self._get_lzx_segment(block_no),\n            self.chm.lrt.block_length,\n            prev_block,\n        )\n\n    def _flatten(self, data):\n        res = []\n        for item in data:\n            res.extend(item)\n        return res\n\n    def __repr__(self):\n        return self.name\n\n\nchm = _CHMFile\n",
    "pychmlib/lzx.py": "# Copyright 2009 Wayne See\n#\n# Licensed under the Apache License, Version 2.0 (the \"License\");\n# you may not use this file except in compliance with the License.\n# You may obtain a copy of the License at\n#\n#     http://www.apache.org/licenses/LICENSE-2.0\n#\n# Unless required by applicable law or agreed to in writing, software\n# distributed under the License is distributed on an \"AS IS\" BASIS,\n# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n# See the License for the specific language governing permissions and\n# limitations under the License.\n\nimport struct\n\n_NUM_CHARS = 256\n\n_LZX_PRETREE_MAXSYMBOLS = 20\n_LZX_PRETREE_NUM_ELEMENTS_BITS = 4\n_LZX_PRETREE_TABLEBITS = 6\n\n_LZX_MAINTREE_TABLEBITS = 12\n_LZX_MAINTREE_MAXSYMBOLS = _NUM_CHARS + 50 * 8\n\n_NUM_SECONDARY_LENGTHS = 249\n_LZX_LENGTH_TABLEBITS = 12\n_LZX_LENGTH_MAXSYMBOLS = _NUM_SECONDARY_LENGTHS + 1\n\n_LZX_NUM_PRIMARY_LENGTHS = 7\n\n_MIN_MATCH = 2\n\n_EXTRA_BITS = [\n    0,\n    0,\n    0,\n    0,\n    1,\n    1,\n    2,\n    2,\n    3,\n    3,\n    4,\n    4,\n    5,\n    5,\n    6,\n    6,\n    7,\n    7,\n    8,\n    8,\n    9,\n    9,\n    10,\n    10,\n    11,\n    11,\n    12,\n    12,\n    13,\n    13,\n    14,\n    14,\n    15,\n    15,\n    16,\n    16,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n    17,\n]\n\n_POSITION_BASE = [\n    0,\n    1,\n    2,\n    3,\n    4,\n    6,\n    8,\n    12,\n    16,\n    24,\n    32,\n    48,\n    64,\n    96,\n    128,\n    192,\n    256,\n    384,\n    512,\n    768,\n    1024,\n    1536,\n    2048,\n    3072,\n    4096,\n    6144,\n    8192,\n    12288,\n    16384,\n    24576,\n    32768,\n    49152,\n    65536,\n    98304,\n    131072,\n    196608,\n    262144,\n    393216,\n    524288,\n    655360,\n    786432,\n    917504,\n    1048576,\n    1179648,\n    1310720,\n    1441792,\n    1572864,\n    1703936,\n    1835008,\n    1966080,\n    2097152,\n]\n\n\nclass _LzxBlock:\n\n    def __init__(self):\n        self.content_length = 0\n        self.lzx_state = _LzxState()\n\n\nclass _LzxState:\n\n    def __init__(self):\n        self.block_length = 0\n        self.block_remaining = 0\n        self.type = None\n        self.intel_file_size = 0\n        self.header_read = False\n        self.intel_started = False\n        self.R0 = 1\n        self.R1 = 1\n        self.R2 = 1\n\n\nclass _BitBuffer:\n\n    def __init__(self, bytes):\n        self.left = 0\n        self.value = 0\n        self.bytes = bytes\n        self.length = len(bytes)\n        self.traversed = 0\n\n    def read_bits(self, get_bits, remove_bits=None):\n        if remove_bits is None:\n            remove_bits = get_bits\n        while self.left < 16:\n            self.value = (self.value << 16) + self.pop() + (self.pop() << 8)\n            self.left += 16\n        temp = self.value >> (self.left - get_bits)\n        self.left -= remove_bits\n        t = self.value >> self.left\n        self.value -= t << self.left\n        return temp\n\n    def pop(self):\n        if self.traversed < self.length:\n            # In Python 3, bytes[i] already returns an int\n            if isinstance(self.bytes[self.traversed], int):\n                val = self.bytes[self.traversed]\n            else:\n                # Python 2 compatibility\n                val, = struct.unpack(\"B\", self.bytes[self.traversed:self.traversed+1])\n            self.traversed += 1\n            return val\n        else:\n            return 0\n\n    def check_bit(self, i):\n        n = 1 << (self.left - i)\n        if (self.value & n) == 0:\n            return 0\n        return 1\n\n\ndef create_lzx_block(block_no, window, bytes, block_length, prev_block=None):\n    block = _create_empty_block(window)\n    block.block_no = block_no\n    if prev_block is None:\n        prev_block = _create_empty_block(window)\n    lzx_state = prev_block.lzx_state\n    block.lzx_state = lzx_state\n    if lzx_state.block_length > lzx_state.block_remaining:\n        prev_content = prev_block.content\n    else:\n        prev_content = []\n    buf = _BitBuffer(bytes)\n    block.content = [0 for i in range(block_length)]\n    if not lzx_state.header_read:\n        lzx_state.header_read = True\n        if buf.read_bits(1) == 1:\n            lzx_state.intel_file_size = (buf.read_bits(16) << 16) + buf.read_bits(16)\n    while block.content_length < block_length:\n        if lzx_state.block_remaining == 0:\n            lzx_state.type = buf.read_bits(3)\n            assert lzx_state.type == 1  # can't handle anything but verbatim\n            lzx_state.block_length = (buf.read_bits(16) << 8) + buf.read_bits(8)\n            lzx_state.block_remaining = lzx_state.block_length\n            lzx_state._main_tree_table = _create_main_tree_table(lzx_state, buf)\n            lzx_state._length_tree_table = _create_length_tree_table(lzx_state, buf)\n            if lzx_state._main_tree_length_table[0xE8] != 0:\n                lzx_state.intel_started = True\n        if block.content_length + lzx_state.block_remaining > block_length:\n            lzx_state.block_remaining = (\n                block.content_length + lzx_state.block_remaining - block_length\n            )\n            length = block_length\n        else:\n            length = block.content_length + lzx_state.block_remaining\n            lzx_state.block_remaining = 0\n        _decompress_verbatim_block(\n            block.content,\n            lzx_state,\n            block.content_length,\n            buf,\n            length,\n            block_length,\n            prev_content,\n        )\n        block.content_length = length\n    return block\n\n\ndef _get_main_tree_index(buf, main_bits, tree_table, main_max_symbol):\n    f = buf.read_bits(main_bits, 0)\n    z = tree_table[f]\n    if z >= main_max_symbol:\n        x = main_bits\n        while True:\n            x += 1\n            z <<= 1\n            z += buf.check_bit(x)\n            z = tree_table[z]\n            if z < main_max_symbol:\n                break\n    return z\n\n\ndef _decompress_verbatim_block(\n    content, lzx_state, content_length, buf, length, block_length, prev_content\n):\n    main_tree = lzx_state._main_tree_table\n    main_tree_length = lzx_state._main_tree_length_table\n    length_tree = lzx_state._length_tree_table\n    length_tree_length = lzx_state._length_tree_length_table\n    R0 = lzx_state.R0\n    R1 = lzx_state.R1\n    R2 = lzx_state.R2\n    i = content_length\n    while i < length:\n        s = _get_main_tree_index(\n            buf, _LZX_MAINTREE_TABLEBITS, main_tree, lzx_state._main_tree_elements\n        )\n        buf.read_bits(main_tree_length[s])\n        if s < _NUM_CHARS:\n            content[i] = s\n        else:\n            s -= _NUM_CHARS\n            match_length = s & _LZX_NUM_PRIMARY_LENGTHS\n            if match_length == _LZX_NUM_PRIMARY_LENGTHS:\n                match_footer = _get_main_tree_index(\n                    buf, _LZX_LENGTH_TABLEBITS, length_tree, _NUM_SECONDARY_LENGTHS\n                )\n                buf.read_bits(length_tree_length[match_footer])\n                match_length += match_footer\n            match_length += _MIN_MATCH\n            match_offset = s >> 3\n            if match_offset > 2:\n                if match_offset != 3:\n                    extra = _EXTRA_BITS[match_offset]\n                    l = buf.read_bits(extra)\n                    match_offset = _POSITION_BASE[match_offset] - 2 + l\n                else:\n                    match_offset = 1\n                R2 = R1\n                R1 = R0\n                R0 = match_offset\n            elif match_offset == 0:\n                match_offset = R0\n            elif match_offset == 1:\n                match_offset = R1\n                R1 = R0\n                R0 = match_offset\n            else:\n                match_offset = R2\n                R2 = R0\n                R0 = match_offset\n            run_dest = i\n            run_src = run_dest - match_offset\n            i += match_length - 1\n            if i > length:\n                break\n            if run_src < 0:\n                if match_length + run_src <= 0:\n                    run_src += len(prev_content)\n                    while match_length > 0:\n                        match_length -= 1\n                        content[run_dest] = prev_content[run_src]\n                        run_dest += 1\n                        run_src += 1\n                else:\n                    prev_content_length = len(prev_content)\n                    run_src += prev_content_length\n                    while run_src < prev_content_length:\n                        content[run_dest] = prev_content[run_src]\n                        run_dest += 1\n                        run_src += 1\n                    match_length = match_length + run_src - prev_content_length\n                    run_src = 0\n                    while match_length > 0:\n                        match_length -= 1\n                        content[run_dest] = content[run_src]\n                        run_dest += 1\n                        run_src += 1\n            else:\n                while (run_src < 0) and (match_length > 0):\n                    content[run_dest] = content[run_src + block_length]\n                    run_dest += 1\n                    run_src += 1\n                    match_length -= 1\n                while match_length > 0:\n                    match_length -= 1\n                    content[run_dest] = content[run_src]\n                    run_dest += 1\n                    run_src += 1\n        i += 1\n    if length == block_length:\n        lzx_state.R0 = R0\n        lzx_state.R1 = R1\n        lzx_state.R2 = R2\n\n\ndef _create_length_tree_table(lzx_state, buf):\n    pre_length_table = _create_pre_length_table(buf)\n    pre_tree_table = _create_pre_tree_table(\n        pre_length_table,\n        (1 << _LZX_PRETREE_TABLEBITS) + (_LZX_PRETREE_MAXSYMBOLS << 1),\n        _LZX_PRETREE_TABLEBITS,\n        _LZX_PRETREE_MAXSYMBOLS,\n    )\n    _init_tree_length_table(\n        lzx_state._length_tree_length_table,\n        buf,\n        0,\n        _NUM_SECONDARY_LENGTHS,\n        pre_tree_table,\n        pre_length_table,\n    )\n    return _create_pre_tree_table(\n        lzx_state._length_tree_length_table,\n        (1 << _LZX_LENGTH_TABLEBITS) + (_LZX_LENGTH_MAXSYMBOLS << 1),\n        _LZX_LENGTH_TABLEBITS,\n        _NUM_SECONDARY_LENGTHS,\n    )\n\n\ndef _create_main_tree_table(lzx_state, buf):\n    pre_length_table = _create_pre_length_table(buf)\n    pre_tree_table = _create_pre_tree_table(\n        pre_length_table,\n        (1 << _LZX_PRETREE_TABLEBITS) + (_LZX_PRETREE_MAXSYMBOLS << 1),\n        _LZX_PRETREE_TABLEBITS,\n        _LZX_PRETREE_MAXSYMBOLS,\n    )\n    _init_tree_length_table(\n        lzx_state._main_tree_length_table,\n        buf,\n        0,\n        _NUM_CHARS,\n        pre_tree_table,\n        pre_length_table,\n    )\n    pre_length_table = _create_pre_length_table(buf)\n    pre_tree_table = _create_pre_tree_table(\n        pre_length_table,\n        (1 << _LZX_PRETREE_TABLEBITS) + (_LZX_PRETREE_MAXSYMBOLS << 1),\n        _LZX_PRETREE_TABLEBITS,\n        _LZX_PRETREE_MAXSYMBOLS,\n    )\n    _init_tree_length_table(\n        lzx_state._main_tree_length_table,\n        buf,\n        _NUM_CHARS,\n        lzx_state._main_tree_elements,\n        pre_tree_table,\n        pre_length_table,\n    )\n    return _create_pre_tree_table(\n        lzx_state._main_tree_length_table,\n        (1 << _LZX_MAINTREE_TABLEBITS) + (_LZX_MAINTREE_MAXSYMBOLS << 1),\n        _LZX_MAINTREE_TABLEBITS,\n        lzx_state._main_tree_elements,\n    )\n\n\ndef _init_tree_length_table(\n    table, buf, counter, table_length, pre_tree_table, pre_length_table\n):\n    while counter < table_length:\n        z = _get_main_tree_index(\n            buf, _LZX_PRETREE_TABLEBITS, pre_tree_table, _LZX_PRETREE_MAXSYMBOLS\n        )\n        buf.read_bits(pre_length_table[z])\n        if z < 17:\n            z = table[counter] - z\n            if z < 0:\n                z += 17\n            table[counter] = z\n            counter += 1\n        elif z == 17:\n            y = buf.read_bits(4)\n            y += 4\n            for j in range(y):\n                table[counter] = 0\n                counter += 1\n        elif z == 18:\n            y = buf.read_bits(5)\n            y += 20\n            for j in range(y):\n                table[counter] = 0\n                counter += 1\n        elif z == 19:\n            y = buf.read_bits(1)\n            y += 4\n            z = _get_main_tree_index(\n                buf, _LZX_PRETREE_TABLEBITS, pre_tree_table, _LZX_PRETREE_MAXSYMBOLS\n            )\n            buf.read_bits(pre_length_table[z])\n            z = table[counter] - z\n            if z < 0:\n                z += 17\n            for j in range(y):\n                table[counter] = z\n                counter += 1\n\n\ndef _create_pre_tree_table(length_table, table_length, bits, max_symbol):\n    bit_num = 1\n    pos = 0\n    table_mask = 1 << bits\n    bit_mask = table_mask >> 1\n    next_symbol = bit_mask\n    tmp = [0 for x in range(table_length)]\n    while bit_num <= bits:\n        for x in range(max_symbol):\n            if length_table[x] == bit_num:\n                leaf = pos\n                pos += bit_mask\n                assert pos <= table_mask, \"invalid state\"\n                fill = bit_mask\n                while fill > 0:\n                    fill -= 1\n                    tmp[leaf] = x\n                    leaf += 1\n        bit_mask >>= 1\n        bit_num += 1\n    if pos != table_mask:\n        for x in range(pos, table_mask):\n            tmp[x] = 0\n        pos <<= 16\n        table_mask <<= 16\n        bit_mask = 1 << 15\n        while bit_num <= 16:\n            for i in range(max_symbol):\n                if length_table[i] == bit_num:\n                    leaf = pos >> 16\n                    for j in range(bit_num - bits):\n                        if tmp[leaf] == 0:\n                            tmp[(next_symbol << 1)] = 0\n                            tmp[(next_symbol << 1) + 1] = 0\n                            tmp[leaf] = next_symbol\n                            next_symbol += 1\n                        leaf = tmp[leaf] << 1\n                        if ((pos >> (15 - j)) & 1) != 0:\n                            leaf += 1\n                    tmp[leaf] = i\n                    pos += bit_mask\n                    assert pos <= table_mask, \"invalid state\"\n            bit_mask >>= 1\n            bit_num += 1\n    if pos == table_mask:\n        return tmp\n    return tmp\n\n\ndef _create_pre_length_table(buf):\n    return [\n        buf.read_bits(_LZX_PRETREE_NUM_ELEMENTS_BITS)\n        for i in range(_LZX_PRETREE_MAXSYMBOLS)\n    ]\n\n\ndef _create_empty_block(win):\n    window = 0\n    while win > 1:\n        win >>= 1\n        window += 1\n    if window < 15 or window > 21:\n        window = 16\n    if window == 21:\n        num_pos_slots = 50\n    elif window == 20:\n        num_pos_slots = 42\n    else:\n        num_pos_slots = window << 1\n    block = _LzxBlock()\n    lzx_state = block.lzx_state\n    lzx_state._main_tree_elements = _NUM_CHARS + num_pos_slots * 8\n    lzx_state._main_tree_length_table = [\n        0 for i in range(lzx_state._main_tree_elements)\n    ]\n    lzx_state._length_tree_length_table = [0 for i in range(_NUM_SECONDARY_LENGTHS)]\n    block.content_length = 0\n    return block\n",
    "hhc.py": "# Copyright 2009 Wayne See\n#\n# Licensed under the Apache License, Version 2.0 (the \"License\");\n# you may not use this file except in compliance with the License.\n# You may obtain a copy of the License at\n#\n#     http://www.apache.org/licenses/LICENSE-2.0\n#\n# Unless required by applicable law or agreed to in writing, software\n# distributed under the License is distributed on an \"AS IS\" BASIS,\n# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n# See the License for the specific language governing permissions and\n# limitations under the License.\n\nfrom html.parser import HTMLParser\n\nimport re\n\n_ESCAPE_PARAM_VALUE = re.compile(r'\\s<param name=\".*\" value=\"(.*\"+.*)\">\\s')\n\n\nclass HHCParser(HTMLParser):\n\n    def __init__(self):\n        HTMLParser.__init__(self)\n        self._contexts = []\n\n    def handle_starttag(self, tag, attrs):\n        if tag == \"object\":\n            self._object = HHCObject()\n            self._object.__dict__.update(dict(attrs))\n        elif tag == \"param\":\n            if hasattr(self, '_object'):\n                param = dict(attrs)\n                self._object.__dict__[param[\"name\"].lower()] = param[\"value\"]\n        elif tag == \"ul\":\n            # For UL tags, we need to set the last sitemap object as an inner node\n            # Look for the most recent sitemap object that could be a parent\n            if self._contexts:\n                # Use the current context\n                pass  # Already handled\n            elif hasattr(self, '_last_sitemap_object'):\n                # Make the last sitemap object a container\n                self._last_sitemap_object._set_as_inner_node()\n                self._contexts.append(self._last_sitemap_object)\n\n    def handle_endtag(self, tag):\n        if tag == \"object\":\n            if hasattr(self, '_object'):\n                # Ignore site properties objects, only process sitemap objects\n                if getattr(self._object, 'type', None) == 'text/sitemap':\n                    # Remember this as the last sitemap object\n                    self._last_sitemap_object = self._object\n                    \n                    if not self._contexts:\n                        # Create a root context if this is the first sitemap object\n                        if not hasattr(self, 'root_context'):\n                            root = HHCObject()\n                            root.is_root = True\n                            root._set_as_inner_node()\n                            root.name = \"Table of Contents\"\n                            self.root_context = root\n                        self.root_context.add_child(self._object)\n                    else:\n                        # add the object to the top of the stack's HHCObject\n                        if hasattr(self._contexts[-1], 'children'):\n                            self._contexts[-1].add_child(self._object)\n        elif tag == \"ul\":\n            if self._contexts:\n                self._contexts.pop()\n\n\nclass HHCObject:\n\n    def __init__(self):\n        self.type = None\n        self.is_inner_node = False  # means this node has leaves\n        self.is_root = False\n        self.parent = None\n        self.name = None\n        self.local = None\n\n    def _set_as_inner_node(self):\n        self.is_inner_node = True\n        self.children = []\n\n    def add_child(self, obj):\n        self.children.append(obj)\n        obj.parent = self\n\n\ndef _sanitize(html):\n    return re.sub(_ESCAPE_PARAM_VALUE, _replace_param, html)\n\n\ndef _replace_param(match_obj):\n    param = match_obj.group(0)\n    value = match_obj.group(1)\n    return param.replace(value, value.replace('\"', \"&quot;\"))\n\n\ndef parse(html):\n    # Handle both bytes and string input\n    if isinstance(html, bytes):\n        html = html.decode(\"utf-8\", errors=\"ignore\")\n    html = _sanitize(html)\n    parser = HHCParser()\n    parser.feed(html)\n    parser.close()\n    # Ensure root context has children attribute\n    if hasattr(parser, 'root_context') and parser.root_context:\n        if not hasattr(parser.root_context, 'children'):\n            parser.root_context._set_as_inner_node()\n        return parser.root_context\n    else:\n        # Create a dummy root if no content was parsed\n        root = HHCObject()\n        root.is_root = True\n        root._set_as_inner_node()\n        root.name = \"Root\"\n        return root\n\n\nif __name__ == \"__main__\":\n    import sys\n    from pychmlib.chm import chm\n\n    filenames = sys.argv[1:]\n    if filenames:\n        chm_file = chm(filenames.pop())\n        hhc_file_contents = chm_file.get_hhc().get_content()\n        contents = parse(hhc_file_contents)\n\n        def recur_print(content, spaces=0):\n            if spaces > 0:\n                tab = \" \" * spaces\n                print(tab + content.name)\n                if content.local:\n                    print(tab + \"(\" + content.local + \")\")\n            if content.is_inner_node:\n                for i in content.children:\n                    recur_print(i, spaces + 2)\n\n        recur_print(contents)\n        chm_file.close()\n    else:\n        print(\"Please provide a CHM file as parameter\")\n"
};

// Setup CHM parsing code in Pyodide
async function setupCHMParser() {
    updateLoadingStatus("Setting up Python modules...");
    
    // Create directories and write files in Pyodide's filesystem
    await pyodide.runPython(`
# Create pychmlib directory
import os
os.makedirs('pychmlib', exist_ok=True)

# Write __init__.py
with open('pychmlib/__init__.py', 'w') as f:
    f.write('')
`);
    
    // Write each module file
    for (const [filename, content] of Object.entries(PYTHON_MODULES)) {
        pyodide.FS.writeFile(filename, content);
    }
    
    // Import and setup the CHM functionality with VFS support
    await pyodide.runPython(`
import sys
sys.path.insert(0, '.')

from pychmlib.chm import _CHMFile
from hhc import parse as parse_hhc
import io
import os

class CHMFileWrapper:
    def __init__(self, file_data):
        self.data = bytes(file_data)
        self.pos = 0
        self.length = len(self.data)
    
    def read(self, size=-1):
        if size == -1:
            result = self.data[self.pos:]
            self.pos = self.length
        else:
            result = self.data[self.pos:self.pos + size]
            self.pos += len(result)
        return result
    
    def seek(self, pos):
        self.pos = pos
    
    def close(self):
        pass

class CHMFile(_CHMFile):
    def __init__(self, file_data):
        self.filename = '<memory>'
        self.file = CHMFileWrapper(file_data)
        try:
            self._parse_chm()
        except Exception as e:
            self.file.close()
            raise Exception(f"CHM parsing failed: {e}") from e
    
    def get_hhc_content(self):
        hhc_file = self.get_hhc()
        if hhc_file:
            content = self.retrieve_object(hhc_file)
            if isinstance(content, bytes):
                return content.decode(self.encoding, errors='ignore')
            return content
        return None
    
    def get_file_content(self, filename):
        unit_info = self.resolve_object(filename)
        if unit_info:
            content = self.retrieve_object(unit_info)
            if isinstance(content, bytes) and filename.endswith(('.htm', '.html', '.hhc', '.hhk', '.css', '.js', '.txt')):
                try:
                    return content.decode(self.encoding, errors='ignore')
                except (UnicodeDecodeError, AttributeError):
                    return content
            return content
        return None
    
    def list_files(self):
        return [ui.name for ui in self.all_files()]
    
    def extract_all_to_vfs(self, base_path='/chm'):
        os.makedirs(base_path, exist_ok=True)
        extracted_files = {}
        
        for unit_info in self.all_files():
            if not unit_info.name or unit_info.name in ['/', '']:
                continue
            
            # Skip directories (they end with / or have length 0)    
            if unit_info.name.endswith('/') or unit_info.length == 0:
                print(f"Skipping directory or empty entry: {unit_info.name}")
                continue
                
            # Skip system files that start with special characters
            if unit_info.name.startswith('/$') or unit_info.name.startswith('/#'):
                print(f"Skipping system file: {unit_info.name}")
                continue
            
            try:
                content = self.retrieve_object(unit_info)
                if content is None:
                    print(f"No content for: {unit_info.name}")
                    continue
                    
                file_path = unit_info.name
                if file_path.startswith('/'):
                    file_path = file_path[1:]
                
                full_path = os.path.join(base_path, file_path)
                
                # Create directories if needed
                dir_path = os.path.dirname(full_path)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                
                # Write file content
                if isinstance(content, str):
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                else:
                    with open(full_path, 'wb') as f:
                        f.write(content)
                
                extracted_files[unit_info.name] = full_path
                print(f"Extracted: {unit_info.name} -> {full_path}")
                
            except Exception as e:
                print(f"Error extracting {unit_info.name}: {e}")
                # Continue with other files even if this one fails
                continue
        
        print(f"Successfully extracted {len(extracted_files)} files to VFS")
        return extracted_files

# Global variables
chm_file = None
vfs_file_mapping = {}

def load_chm_file(file_data):
    global chm_file, vfs_file_mapping
    print(f"load_chm_file called with data type: {type(file_data)}")
    print(f"Data length: {len(file_data) if hasattr(file_data, '__len__') else 'unknown'}")
    if hasattr(file_data, '__getitem__'):
        header = bytes(file_data[:4])
        print(f"Header bytes: {header}")
    chm_file = CHMFile(file_data)
    print("CHMFile created successfully")
    
    print("Extracting CHM files to VFS...")
    vfs_file_mapping = chm_file.extract_all_to_vfs()
    print(f"Extracted {len(vfs_file_mapping)} files to VFS")
    
    return True

def get_chm_toc():
    global chm_file
    print(f"get_chm_toc called, chm_file: {chm_file}")
    if not chm_file:
        print("No chm_file available")
        return None
    
    print("Getting HHC content...")
    hhc_content = chm_file.get_hhc_content()
    print(f"HHC content type: {type(hhc_content)}")
    print(f"HHC content length: {len(hhc_content) if hhc_content else 0}")
    if not hhc_content:
        print("No HHC content found")
        return None
    
    print("Parsing HHC content...")
    result = parse_hhc(hhc_content)
    print(f"Parsed HHC result: {result}")
    return result

def get_chm_file_content(filename):
    global chm_file
    if not chm_file:
        return None
    return chm_file.get_file_content(filename)

def list_chm_files():
    global chm_file
    if not chm_file:
        return []
    return chm_file.list_files()

def get_vfs_path(chm_path):
    global vfs_file_mapping
    if chm_path in vfs_file_mapping:
        return vfs_file_mapping[chm_path]
    
    if '/' + chm_path in vfs_file_mapping:
        return vfs_file_mapping['/' + chm_path]
    
    for original_path, vfs_path in vfs_file_mapping.items():
        if original_path.lower() == chm_path.lower():
            return vfs_path
        if original_path.lower() == ('/' + chm_path).lower():
            return vfs_path
    
    return None

def create_blob_data_for_file(vfs_path):
    try:
        with open(vfs_path, 'rb') as f:
            data = f.read()
        return data
    except Exception as e:
        print(f"Error reading VFS file {vfs_path}: {e}")
        return None
`);
}

// File handling functions
function setupFileHandling() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const loadBtn = document.getElementById('loadBtn');
    
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            currentFile = e.target.files[0];
            loadBtn.disabled = false;
            updateUploadZone();
        }
    });
    
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.toLowerCase().endsWith('.chm')) {
                currentFile = file;
                fileInput.files = e.dataTransfer.files;
                loadBtn.disabled = false;
                updateUploadZone();
            } else {
                showError('Please select a CHM file');
            }
        }
    });
}

function updateUploadZone() {
    const uploadZone = document.getElementById('uploadZone');
    if (currentFile) {
        uploadZone.innerHTML = `
            <div class="upload-icon">✅</div>
            <div>
                <p><strong>${currentFile.name}</strong></p>
                <p style="color: #666; font-size: 0.9rem;">Size: ${formatFileSize(currentFile.size)}</p>
                <p style="color: #666; font-size: 0.9rem;">Click "Load CHM File" to continue</p>
            </div>
        `;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Create blob URL for CHM file content
async function createBlobUrlForCHMFile(chmPath) {
    if (blobUrlCache.has(chmPath)) {
        return blobUrlCache.get(chmPath);
    }
    
    try {
        pyodide.globals.set("blob_chm_path", chmPath);
        await pyodide.runPython(`
global blob_file_data, blob_success, blob_mime_type
import mimetypes

blob_chm_path_clean = blob_chm_path
if blob_chm_path_clean.startswith('/'):
    blob_chm_path_clean = blob_chm_path_clean[1:]

vfs_path = get_vfs_path(blob_chm_path)
if vfs_path:
    blob_file_data = create_blob_data_for_file(vfs_path)
    if blob_file_data:
        mime_type, _ = mimetypes.guess_type(blob_chm_path_clean)
        if not mime_type:
            if blob_chm_path_clean.lower().endswith(('.htm', '.html')):
                mime_type = 'text/html'
            elif blob_chm_path_clean.lower().endswith('.css'):
                mime_type = 'text/css'
            elif blob_chm_path_clean.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif blob_chm_path_clean.lower().endswith('.png'):
                mime_type = 'image/png'
            elif blob_chm_path_clean.lower().endswith('.gif'):
                mime_type = 'image/gif'
            else:
                mime_type = 'application/octet-stream'
        blob_mime_type = mime_type
        blob_success = True
    else:
        blob_success = False
else:
    blob_success = False
`);
        
        const success = pyodide.globals.get('blob_success');
        if (success) {
            const fileData = pyodide.globals.get('blob_file_data');
            const mimeType = pyodide.globals.get('blob_mime_type');
            
            const uint8Array = new Uint8Array(fileData.toJs());
            const blob = new Blob([uint8Array], { type: mimeType });
            const blobUrl = URL.createObjectURL(blob);
            
            blobUrlCache.set(chmPath, blobUrl);
            console.log(`Created blob URL for ${chmPath}: ${blobUrl}`);
            return blobUrl;
        }
    } catch (error) {
        console.error(`Error creating blob URL for ${chmPath}:`, error);
    }
    
    return null;
}

// Load and parse CHM file
async function loadFile() {
    if (!currentFile) {
        showError('Please select a CHM file first');
        return;
    }
    
    try {
        showLoading(true);
        
        if (!pyodide) {
            await initPyodide();
        }
        
        updateLoadingStatus("Reading CHM file...");
        
        const arrayBuffer = await currentFile.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        updateLoadingStatus("Parsing CHM structure and extracting to VFS...");
        
        pyodide.globals.set("file_data", uint8Array);
        
        await pyodide.runPython(`
global chm_load_success
try:
    result = load_chm_file(file_data.to_py())
    print(f"load_chm_file returned: {result}")
    chm_load_success = result
except Exception as e:
    import traceback
    print(f"Error loading CHM: {e}")
    print("Full traceback:")
    traceback.print_exc()
    chm_load_success = False
`);
        
        const success = pyodide.globals.get('chm_load_success');
        console.log("JavaScript success value:", success, "Type:", typeof success);
        
        if (!success) {
            throw new Error("Failed to parse CHM file");
        }
        
        updateLoadingStatus("Extracting table of contents...");
        
        await pyodide.runPython(`
global toc_json_data, toc_extraction_success
import json

try:
    print("Getting TOC...")
    toc = get_chm_toc()
    print(f"TOC result: {toc}")
    print(f"TOC type: {type(toc)}")
    if toc:
        print(f"TOC has children: {hasattr(toc, 'children')}")
        if hasattr(toc, 'children'):
            print(f"Number of children: {len(toc.children)}")
        
        def convert_toc(node):
            result = {
                'name': node.name,
                'local': getattr(node, 'local', None),
                'children': []
            }
            if hasattr(node, 'children'):
                for child in node.children:
                    if child.name and child.name.strip():
                        result['children'].append(convert_toc(child))
            return result
        converted = convert_toc(toc)
        print(f"Converted TOC: {converted}")
        toc_json_data = json.dumps(converted)
        print(f"JSON length: {len(toc_json_data)}")
        toc_extraction_success = True
    else:
        print("No TOC found")
        toc_extraction_success = False
except Exception as e:
    print(f"Error getting TOC: {e}")
    import traceback
    traceback.print_exc()
    toc_extraction_success = False
`);
        
        const tocSuccess = pyodide.globals.get('toc_extraction_success');
        console.log("TOC extraction success:", tocSuccess);
        
        let tocData = null;
        if (tocSuccess) {
            const tocJsonString = pyodide.globals.get('toc_json_data');
            tocData = JSON.parse(tocJsonString);
            console.log("Parsed TOC data:", tocData);
        }
        
        if (tocData) {
            displayCHMViewer(tocData);
        } else {
            throw new Error("Could not extract table of contents from CHM file");
        }
        
    } catch (error) {
        console.error('Error loading CHM file:', error);
        showError(`Error loading CHM file: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// Display CHM viewer
function displayCHMViewer(tocData) {
    document.getElementById('viewerContainer').style.display = 'block';
    
    const tocContainer = document.getElementById('tocContent');
    tocContainer.innerHTML = buildTOCHTML(tocData);
    
    setupTOCHandlers();
    
    document.getElementById('viewerContainer').scrollIntoView({ behavior: 'smooth' });
}

function buildTOCHTML(node) {
    let html = '<ul>';
    
    if (node.children && node.children.length > 0) {
        for (const child of node.children) {
            html += '<li>';
            
            if (child.local) {
                html += `<a href="#" class="toc-item" data-path="${child.local}">${child.name}</a>`;
            } else if (child.children && child.children.length > 0) {
                html += `<div class="folder" onclick="toggleFolder(this)">${child.name}</div>`;
                html += `<div class="folder-content">${buildTOCHTML(child)}</div>`;
            } else {
                html += `<div class="folder">${child.name}</div>`;
            }
            
            if (child.local && child.children && child.children.length > 0) {
                html += `<div class="folder-content">${buildTOCHTML(child)}</div>`;
            }
            
            html += '</li>';
        }
    }
    
    html += '</ul>';
    return html;
}

function setupTOCHandlers() {
    const tocItems = document.querySelectorAll('.toc-item');
    tocItems.forEach(item => {
        item.addEventListener('click', async (e) => {
            e.preventDefault();
            const path = item.dataset.path;
            if (path) {
                await loadContent(path);
                
                document.querySelectorAll('.toc-item').forEach(i => i.classList.remove('current'));
                item.classList.add('current');
            }
        });
    });
}

function toggleFolder(element) {
    element.classList.toggle('collapsed');
}

// Resolve relative paths
function resolveRelativePath(path) {
    const parts = path.split('/');
    const resolved = [];
    
    for (const part of parts) {
        if (part === '' || part === '.') {
            continue;
        } else if (part === '..') {
            if (resolved.length > 0) {
                resolved.pop();
            }
        } else {
            resolved.push(part);
        }
    }
    
    return resolved.join('/');
}

// Scope CSS to content area - Improved version
function scopeCSSToContentArea(cssContent) {
    console.log("Scoping CSS content, original length:", cssContent.length);
    
    // More robust CSS rule parsing
    const rules = [];
    let currentRule = '';
    let braceCount = 0;
    let inString = false;
    let stringChar = '';
    
    for (let i = 0; i < cssContent.length; i++) {
        const char = cssContent[i];
        const prevChar = i > 0 ? cssContent[i - 1] : '';
        
        if (!inString && (char === '"' || char === "'")) {
            inString = true;
            stringChar = char;
        } else if (inString && char === stringChar && prevChar !== '\\') {
            inString = false;
            stringChar = '';
        }
        
        if (!inString) {
            if (char === '{') {
                braceCount++;
            } else if (char === '}') {
                braceCount--;
                if (braceCount === 0) {
                    currentRule += char;
                    rules.push(currentRule.trim());
                    currentRule = '';
                    continue;
                }
            }
        }
        
        currentRule += char;
    }
    
    // Add any remaining rule
    if (currentRule.trim()) {
        rules.push(currentRule.trim());
    }
    
    console.log("Parsed", rules.length, "CSS rules");
    
    const scopedRules = [];
    
    for (let rule of rules) {
        rule = rule.trim();
        if (!rule) continue;
        
        // Handle @-rules (media queries, keyframes, etc.)
        if (rule.startsWith('@')) {
            if (rule.startsWith('@media')) {
                // For media queries, scope the inner rules
                const mediaMatch = rule.match(/@media[^{]+\{([\s\S]*)\}$/);
                if (mediaMatch) {
                    const mediaQuery = rule.substring(0, rule.indexOf('{') + 1);
                    const innerCSS = mediaMatch[1];
                    const scopedInner = scopeCSSToContentArea(innerCSS);
                    scopedRules.push(mediaQuery + scopedInner + '}');
                } else {
                    scopedRules.push(rule);
                }
            } else {
                // Other @-rules (keyframes, imports, etc.) - keep as-is
                scopedRules.push(rule);
            }
            continue;
        }
        
        const braceIndex = rule.indexOf('{');
        if (braceIndex === -1) continue;
        
        const selector = rule.substring(0, braceIndex).trim();
        const properties = rule.substring(braceIndex);
        
        // Scope each selector
        const scopedSelector = selector.split(',').map(sel => {
            sel = sel.trim();
            
            // Skip if already scoped
            if (sel.includes('.chm-content')) {
                return sel;
            }
            
            // Handle special selectors that should be scoped but not prefixed
            if (sel === 'html' || sel === 'body' || sel === '*') {
                return '.chm-content';
            }
            
            // Handle pseudo-selectors and combinators properly
            if (sel.includes(':') || sel.includes('>') || sel.includes('+') || sel.includes('~')) {
                // For complex selectors, scope the first part
                const parts = sel.split(/(\s*[>+~]\s*)/);
                if (parts.length > 1) {
                    parts[0] = '.chm-content ' + parts[0].trim();
                    return parts.join('');
                } else {
                    // For pseudo-selectors like div:hover
                    return '.chm-content ' + sel;
                }
            }
            
            // Add .chm-content prefix to scope the selector
            return '.chm-content ' + sel;
        }).join(', ');
        
        scopedRules.push(scopedSelector + properties);
    }
    
    const result = scopedRules.join('\n');
    console.log("Scoped CSS result length:", result.length);
    console.log("Sample scoped CSS (first 200 chars):", result.substring(0, 200));
    
    return result;
}

// Process HTML content with VFS assets - General approach
async function processHTMLContent(htmlContent, basePath) {
    console.log("processHTMLContent called with basePath:", basePath);
    let processedHTML = htmlContent;
    
    const baseDir = basePath.includes('/') ? basePath.substring(0, basePath.lastIndexOf('/')) : '';
    console.log("Base directory:", baseDir);
    
    // **GENERAL APPROACH**: Find all relative file paths and replace them with blob URLs
    // This catches any relative path that looks like a file, regardless of context
    // Matches: ../path/file.ext, ./path/file.ext, path/file.ext, file.ext
    // NOTE: Excludes CSS files as they need special processing for url() references
    const generalFileRegex = /(?:["'=\s>])([^"'\s<>]*[^\/\s<>"']\.(?:jpg|jpeg|png|gif|bmp|js|htm|html|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|tar|gz|mp3|mp4|avi|mov|wmv|flv|swf|ico|svg|woff|woff2|ttf|eot))(?=["'\s<>])/gi;
    const generalMatches = [...htmlContent.matchAll(generalFileRegex)];
    console.log("Found", generalMatches.length, "relative file paths via general approach");
    console.log("General matches:", generalMatches.map(m => `"${m[0]}" -> "${m[1]}"`));
    
    for (const match of generalMatches) {
        const fullMatch = match[0];
        const relativePath = match[1];
        
        console.log(`Processing match: Full="${fullMatch}" | Path="${relativePath}"`);
        
        // Skip if already processed (contains blob:) or is an absolute URL
        if (relativePath.includes('blob:') || relativePath.startsWith('http://') || 
            relativePath.startsWith('https://') || relativePath.startsWith('data:')) {
            console.log(`Skipping already processed or absolute URL: "${relativePath}"`);
            continue;
        }
        
        try {
            let resolvedPath = relativePath;
            if (!relativePath.startsWith('/')) {
                if (baseDir) {
                    resolvedPath = baseDir + '/' + relativePath;
                } else {
                    resolvedPath = relativePath;
                }
                resolvedPath = resolveRelativePath(resolvedPath);
            }
            
            console.log("Loading general file via VFS:", resolvedPath, "from original:", relativePath);
            
            const blobUrl = await createBlobUrlForCHMFile(resolvedPath);
            if (blobUrl) {
                // Replace the relative path with the blob URL, preserving the surrounding context
                const newMatch = fullMatch.replace(relativePath, blobUrl);
                console.log(`Replacing "${fullMatch}" with "${newMatch}"`);
                const oldHTML = processedHTML;
                processedHTML = processedHTML.replace(fullMatch, newMatch);
                if (oldHTML === processedHTML) {
                    console.log(`WARNING: No replacement occurred for "${fullMatch}"`);
                } else {
                    console.log("Successfully loaded general file via blob URL:", resolvedPath);
                }
            } else {
                console.log("Could not create blob URL for general file:", resolvedPath);
            }
        } catch (error) {
            console.error("Error processing general file " + relativePath + ":", error);
        }
    }
    
    // Process external CSS files for scoping and url() processing
    // CSS files are excluded from general regex above to allow proper url() processing
    const cssRegex = /<link([^>]*?)href=["']([^"']+\.css)["']([^>]*?)>/gi;
    const cssMatches = [...processedHTML.matchAll(cssRegex)];
    console.log("Found", cssMatches.length, "CSS links to process for url() references and scoping");
    
    for (const match of cssMatches) {
        const fullTag = match[0];
        const cssHref = match[2];
        
        console.log(`Processing CSS file: "${cssHref}" from tag: "${fullTag}"`);
        
        if (cssHref.startsWith('http://') || cssHref.startsWith('https://') || cssHref.startsWith('blob:')) {
            console.log(`Skipping external/blob CSS: "${cssHref}"`);
            continue;
        }
        
        try {
            let cssPath = cssHref;
            if (!cssHref.startsWith('/')) {
                if (baseDir) {
                    cssPath = baseDir + '/' + cssHref;
                } else {
                    cssPath = cssHref;
                }
                cssPath = resolveRelativePath(cssPath);
            }
            
            console.log("Loading CSS via VFS for scoping: " + cssPath);
            
            const blobUrl = await createBlobUrlForCHMFile(cssPath);
            if (blobUrl) {
                const response = await fetch(blobUrl);
                if (response.ok) {
                    const cssContent = await response.text();
                    console.log("Processing CSS file for url() references and scoping:", cssPath);
                    
                    // Process url() references in the CSS content (general approach may not catch these inside blobs)
                    let processedCssContent = cssContent;
                    const cssUrlRegex = /url\(["']?([^"')]+)["']?\)/gi;
                    const cssUrlMatches = [...cssContent.matchAll(cssUrlRegex)];
                    console.log("Found", cssUrlMatches.length, "url() references in CSS file:", cssPath);
                    
                    for (const urlMatch of cssUrlMatches) {
                        const fullCssUrl = urlMatch[0];
                        const cssImgUrl = urlMatch[1];
                        
                        console.log(`Processing CSS url(): "${fullCssUrl}" -> "${cssImgUrl}"`);
                        
                        if (cssImgUrl.startsWith('http://') || cssImgUrl.startsWith('https://') || 
                            cssImgUrl.startsWith('data:') || cssImgUrl.startsWith('blob:')) {
                            console.log(`Skipping external/blob CSS url(): "${cssImgUrl}"`);
                            continue;
                        }
                        
                        try {
                            // Resolve relative to the CSS file's directory
                            const cssDir = cssPath.includes('/') ? cssPath.substring(0, cssPath.lastIndexOf('/')) : '';
                            let cssImagePath = cssImgUrl;
                            if (!cssImgUrl.startsWith('/')) {
                                if (cssDir) {
                                    cssImagePath = cssDir + '/' + cssImgUrl;
                                } else {
                                    cssImagePath = cssImgUrl;
                                }
                                cssImagePath = resolveRelativePath(cssImagePath);
                            }
                            
                            console.log("Loading CSS image via VFS:", cssImagePath, "from CSS file:", cssPath);
                            
                            const cssImageBlobUrl = await createBlobUrlForCHMFile(cssImagePath);
                            if (cssImageBlobUrl) {
                                const newCssUrl = "url('" + cssImageBlobUrl + "')";
                                processedCssContent = processedCssContent.replace(fullCssUrl, newCssUrl);
                                console.log("Successfully loaded CSS image via blob URL:", cssImagePath);
                            } else {
                                console.log("Could not create blob URL for CSS image:", cssImagePath);
                            }
                        } catch (error) {
                            console.error("Error processing CSS image " + cssImgUrl + ":", error);
                        }
                    }
                    
                    // Scope the CSS content to avoid conflicts
                    const scopedCSS = scopeCSSToContentArea(processedCssContent);
                    const styleTag = "<style>" + scopedCSS + "</style>";
                    processedHTML = processedHTML.replace(fullTag, styleTag);
                    console.log("Successfully embedded scoped CSS with processed images: " + cssPath);
                }
            }
        } catch (error) {
            console.error("Error processing CSS " + cssHref + ":", error);
        }
    }
    
    // Add compatibility shims for legacy HTML Help functions at the end
    const hhctrlShims = `
<!-- HTML Help Compatibility Shims -->
<script>
// Create hhctrl object for legacy CHM compatibility
if (typeof hhctrl === 'undefined') {
    window.hhctrl = {
        // TextPopup function - shows popup text
        TextPopup: function(text, font, size, foreColor, backColor) {
            console.log('hhctrl.TextPopup called:', text);
            // Create a simple modal-style popup
            const popup = document.createElement('div');
            popup.style.cssText = \`
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: \${backColor || '#FFFFC0'};
                color: \${foreColor || '#000000'};
                border: 1px solid #000;
                padding: 10px;
                font-family: \${font || 'Arial'};
                font-size: \${size || '12'}px;
                z-index: 10000;
                max-width: 400px;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
                border-radius: 4px;
            \`;
            popup.innerHTML = text + '<br><br><button onclick="this.parentElement.remove()">Close</button>';
            document.body.appendChild(popup);
            return popup;
        },
        
        // HH_HELP_CONTEXT function
        HH_HELP_CONTEXT: function(contextId) {
            console.log('hhctrl.HH_HELP_CONTEXT called:', contextId);
            // In a real implementation, this would navigate to a specific help topic
            return false;
        },
        
        // Other common HTML Help functions
        HtmlHelp: function(hwndCaller, pszFile, uCommand, dwData) {
            console.log('hhctrl.HtmlHelp called:', arguments);
            return false;
        }
    };
}

// Legacy functions that might be called directly
if (typeof TextPopup === 'undefined') {
    window.TextPopup = window.hhctrl.TextPopup;
}

if (typeof HtmlHelp === 'undefined') {
    window.HtmlHelp = window.hhctrl.HtmlHelp;
}

// Handle legacy popup links and events
document.addEventListener('click', function(e) {
    const target = e.target;
    
    // Handle legacy popup attributes
    if (target.hasAttribute('onclick')) {
        const onclick = target.getAttribute('onclick');
        if (onclick.includes('TextPopup') || onclick.includes('hhctrl')) {
            console.log('Legacy popup click intercepted:', onclick);
            // Let the event proceed but ensure our shims are available
        }
    }
}, true);

console.log('HTML Help compatibility shims loaded');
</script>
`;

    processedHTML += hhctrlShims;
    
    return processedHTML;
}

// Load content for a specific path
async function loadContent(path) {
    try {
        updateLoadingStatus(`Loading ${path}...`);
        
        pyodide.globals.set("content_path", path);
        await pyodide.runPython(`
global content_data, content_success
try:
    print(f"Loading content for path: {content_path}")
    
    base_path = content_path.split('#')[0] if '#' in content_path else content_path
    anchor = content_path.split('#')[1] if '#' in content_path else None
    
    paths_to_try = [
        base_path,
        '/' + base_path,
        '/' + base_path.lower(),
        base_path.lower()
    ]
    
    all_files = list_chm_files()
    print(f"Total files in CHM: {len(all_files)}")
    
    content = None
    used_path = None
    
    for try_path in paths_to_try:
        print(f"Trying path: {try_path}")
        if try_path in all_files:
            print(f"Found exact match: {try_path}")
            content = get_chm_file_content(try_path)
            used_path = try_path
            if anchor:
                print(f"Note: Will need to scroll to anchor #{anchor}")
            break
    
    if not content:
        print("No exact match found. Searching for similar files...")
        similar = [f for f in all_files if base_path.lower() in f.lower()]
        print(f"Similar files: {similar[:5]}")
        if similar:
            try_path = similar[0]
            print(f"Trying similar file: {try_path}")
            content = get_chm_file_content(try_path)
            used_path = try_path
    
    print(f"Content type: {type(content)}")
    print(f"Content length: {len(content) if content else 0}")
    if content and isinstance(content, str):
        print(f"Content preview: {content[:100]}...")
        print(f"Used path: {used_path}")
    
    content_data = content if content else ""
    content_success = bool(content)
    print(f"Stored content_success: {content_success}")
    
except Exception as e:
    print(f"Error loading content: {e}")
    import traceback
    traceback.print_exc()
    content_data = ""
    content_success = False
`);

        const contentSuccess = pyodide.globals.get('content_success');
        const content = contentSuccess ? pyodide.globals.get('content_data') : null;
        
        const contentArea = document.getElementById('contentArea');
        
        console.log("JavaScript received content:", content);
        console.log("Content type:", typeof content);
        console.log("Content length:", content ? content.length : 0);
        
        if (content) {
            console.log("Processing content for path:", path);
            const isHTML = path.toLowerCase().includes('.htm');
            console.log("Is HTML file:", isHTML);
            if (isHTML) {
                console.log("Calling processHTMLContent...");
                const processedContent = await processHTMLContent(content, path);
                
                contentArea.innerHTML = `
                    <div style="border: 1px solid #ddd; border-radius: 4px; overflow: hidden;">
                        <div style="background: #f8f9fa; padding: 0.5rem; border-bottom: 1px solid #ddd; font-weight: 600;">
                            📄 ${path}
                        </div>
                        <div class="chm-content" style="padding: 1rem; max-height: 60vh; overflow-y: auto;">
                            ${processedContent}
                        </div>
                    </div>
                `;
            } else {
                contentArea.innerHTML = `
                    <div style="border: 1px solid #ddd; border-radius: 4px; overflow: hidden;">
                        <div style="background: #f8f9fa; padding: 0.5rem; border-bottom: 1px solid #ddd; font-weight: 600;">
                            📄 ${path}
                        </div>
                        <pre style="padding: 1rem; margin: 0; max-height: 60vh; overflow-y: auto; background: #f8f9fa;">${content}</pre>
                    </div>
                `;
            }
        } else {
            contentArea.innerHTML = `
                <div class="error">
                    <h3>Content Not Available</h3>
                    <p>Could not load content for "${path}". The file may be compressed or not found.</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error loading content:', error);
        const contentArea = document.getElementById('contentArea');
        contentArea.innerHTML = `
            <div class="error">
                <h3>Error Loading Content</h3>
                <p>Failed to load "${path}": ${error.message}</p>
            </div>
        `;
    }
}

// Utility functions
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

function updateLoadingStatus(message) {
    document.getElementById('loadingStatus').textContent = message;
}

function showError(message) {
    const errorContainer = document.getElementById('errorContainer');
    errorContainer.innerHTML = `
        <div class="error">
            <h3>Error</h3>
            <p>${message}</p>
        </div>
    `;
    setTimeout(() => {
        errorContainer.innerHTML = '';
    }, 5000);
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    setupFileHandling();
});
