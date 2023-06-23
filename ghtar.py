#!/usr/bin/python3

"""
Build up a file that is extractable via the 'make.gs' script.

Example input:

[
    {
        "type": "folder",
        "name": "/tmp"
    },
    {
        "type": "folder",
        "name": "~/scripts"
    },
    {
        "type": "file",
        "local": "./my-local-file.txt"
        "path": "~/scripts/try.scr"
    },
    {
        "type": "build",
        "source": "~/scripts/try.src",
        "target": "~/try"
    }
]
"""

from typing import Sequence, List, Dict, Mapping, Set, Tuple, Callable, Optional, Any
import os
import sys
import glob
import argparse
import base64
import json
import re
from collections import Counter

FILE_VERSION__UNCOMPRESSED = 1
FILE_VERSION__COMPRESSED = 2
TEMP_DIR = "~/.tmp"
VERBOSE = [False]


def debug(msg: str, **args: Any) -> None:
    """Debug message."""
    if VERBOSE[0]:
        sys.stderr.write("[DEBUG] " + (msg.format(**args)) + "\n")


def log_error(msg: str, **args: Any) -> None:
    """Error message."""
    sys.stderr.write("Error: " + (msg.format(**args)) + "\n")


# -----------------------------------------------
# Low level data converters
def mk_uint8(value: int) -> bytes:
    """Turn an int value into a uint8 value in a byte stream."""
    assert 0 <= value <= 255
    return value.to_bytes(1, "big")


def mk_uint16(value: int) -> bytes:
    """Turn an int value into a uint16 value in a byte stream."""
    assert 0 <= value <= 65535
    return value.to_bytes(2, "big")


def mk_bool(value: bool) -> bytes:
    """Turn a boolean into a 1 or 0"""
    return mk_uint8(1 if value else 0)


def mk_ref(index: int) -> bytes:
    """Turn a reference index into a uint16 in a byte stream."""
    return mk_uint16(index)


def mk_chunk(chunk_id: int, chunk_data: bytes) -> bytes:
    """Create a chunk block."""
    # A chunk is the chunk ID + chunk's data size (uint16) + data.
    assert 0 <= chunk_id <= 255
    ret = bytes([chunk_id]) + mk_uint16(len(chunk_data)) + chunk_data

    # r = f"[chunk {chunk_id}]"
    # for b in ret:
    #     r += f" {b:02x}"
    # debug(r)

    return ret


# -----------------------------------------------
# Low level block creators

BLOCK_HEADER = 0
BLOCK_ASCII = 1
BLOCK_UTF16 = 2
BLOCK_REL_HOME = 3
BLOCK_ASCII_REPLACED_HOME = 4
BLOCK_UTF16_REPLACED_HOME = 5
BLOCK_FOLDER = 20
BLOCK_FILE = 21
BLOCK_CHMOD = 24
BLOCK_CHOWN = 25
BLOCK_CHGROUP = 26
BLOCK_NEW_USER = 40
BLOCK_NEW_GROUP = 41
BLOCK_BUILD = 80
BLOCK_TEST = 81
BLOCK_LAUNCH = 82
BLOCK_COPY = 83
BLOCK_MOVE = 84
BLOCK_DELETE = 85

REPLACED_WITH_HOME = "<[HOME]>"


def mk_block_header(version: int) -> bytes:
    """Create a header block."""
    # version, rest of the header size.
    return mk_chunk(BLOCK_HEADER, mk_uint16(version) + mk_uint16(0))


def mk_block_string(index: int, text: str, needs_home_replacement: bool) -> bytes:
    """Create a block with a referencable, indexed string."""
    debug("Adding string {i}: '{txt}'", i=index, txt=repr(text[:20]))
    try:
        encoded = text.encode("ascii")
        return mk_chunk(
            BLOCK_ASCII_REPLACED_HOME if needs_home_replacement else BLOCK_ASCII,
            mk_ref(index) + mk_uint16(len(text)) + encoded,
        )
    except UnicodeEncodeError:
        # Strip off the leading \xff \xfe from the utf-16 string
        encoded = text.encode("utf-16")[2:]
        # Don't allow > 16-bit characters...
        if len(encoded) != len(text) * 2:
            raise RuntimeError(f"Only 2-byte UTF characters are allowed ({text})")
        data = b""
        for i in range(0, len(encoded), 2):
            data += mk_uint16((encoded[i] << 8) + encoded[i + 1])
        return mk_chunk(
            BLOCK_UTF16_REPLACED_HOME if needs_home_replacement else BLOCK_UTF16,
            mk_ref(index) + mk_uint16(len(text)) + data,
        )


def mk_block_rel_home(index: int, text: str) -> bytes:
    """Create a block that goes into the string pool, but whose value is a path
    that is relative to the user's home directory."""
    # File paths are always ascii-encoded.
    debug("Adding rel home string {i}: '{txt}'", i=index, txt=repr(text[:20]))
    return mk_chunk(
        BLOCK_REL_HOME, mk_ref(index) + mk_uint16(len(text)) + text.encode("ascii")
    )


def mk_block_folder(parent_index: int, name_index: int) -> bytes:
    """Create a folder block."""
    return mk_chunk(BLOCK_FOLDER, mk_ref(parent_index) + mk_ref(name_index))


def mk_block_file(
    dirname_index: int, filename_index: int, contents_index: int
) -> bytes:
    """Create a file block."""
    return mk_chunk(
        BLOCK_FILE,
        mk_ref(dirname_index) + mk_ref(filename_index) + mk_ref(contents_index),
    )


def mk_block_chmod(file_name_index: int, perms_index: int, recursive: bool) -> bytes:
    """Create a chmod block."""
    return mk_chunk(
        BLOCK_CHMOD,
        mk_ref(file_name_index) + mk_ref(perms_index) + mk_bool(recursive),
    )


def mk_block_chown(file_name_index: int, username_index: int, recursive: bool) -> bytes:
    """Create a chown block"""
    return mk_chunk(
        BLOCK_CHOWN,
        mk_ref(file_name_index) + mk_ref(username_index) + mk_bool(recursive),
    )


def mk_block_chgroup(file_name_index: int, group_index: int, recursive: bool) -> bytes:
    """Create a chgroup block"""
    return mk_chunk(
        BLOCK_CHOWN,
        mk_ref(file_name_index) + mk_ref(group_index) + mk_bool(recursive),
    )


def mk_block_user(username_index: int, password_index: int) -> bytes:
    """Create a new user block."""
    return mk_chunk(BLOCK_NEW_USER, mk_ref(username_index) + mk_ref(password_index))


def mk_block_group(username_index: int, group_index: int) -> bytes:
    """Assign a user to a group, block."""
    return mk_chunk(BLOCK_NEW_GROUP, mk_ref(username_index) + mk_ref(group_index))


def mk_block_build(
    source_index: int, target_dir_index: int, target_file_name_index: int
) -> bytes:
    """Create a build block."""
    debug(
        "build block: src={src}, target dir={td}, target name={tn}",
        src=source_index,
        td=target_dir_index,
        tn=target_file_name_index,
    )
    return mk_chunk(
        BLOCK_BUILD,
        mk_ref(source_index)
        + mk_ref(target_dir_index)
        + mk_ref(target_file_name_index),
    )


def mk_block_test(test_index: int, name_index: int, contents_index: int) -> bytes:
    """Create a test block."""
    return mk_chunk(
        BLOCK_TEST,
        mk_uint16(test_index) + mk_ref(name_index) + mk_ref(contents_index),
    )


def mk_block_launch(argument_index: Sequence[int]) -> bytes:
    """Create a launch program block."""
    if len(argument_index) < 1:
        raise RuntimeError(
            f"Launch program must have at least 1 argument, found {len(argument_index)}"
        )
    data = mk_uint8(len(argument_index))
    for arg in argument_index:
        data += mk_ref(arg)
    return mk_chunk(BLOCK_LAUNCH, data)


def mk_block_copy(source_index: int, target_path_idx: int, target_name: int) -> bytes:
    """Create a copy a file block."""
    return mk_chunk(
        BLOCK_COPY,
        mk_ref(source_index) + mk_ref(target_path_idx) + mk_ref(target_name),
    )


def mk_block_move(source_index: int, target_path_idx: int, target_name: int) -> bytes:
    """Create a move a file block."""
    return mk_chunk(
        BLOCK_MOVE,
        mk_ref(source_index) + mk_ref(target_path_idx) + mk_ref(target_name),
    )


def mk_block_delete(file_index: int) -> bytes:
    """Create a delete a file block."""
    return mk_chunk(BLOCK_DELETE, mk_ref(file_index))


# -----------------------------------------------
# File store manager.
# Handles the construction of the source files and synthetic files
# neccesary to support compiling.


class MappedFile:
    """A file mapped into the local computer space."""

    __slots__ = ("path", "contents", "is_home_replaced", "requested_path")

    def __init__(
        self, *, path: str, contents: str, is_home_replaced: bool, requested_path: str
    ) -> None:
        self.path = path
        self.contents = contents
        self.is_home_replaced = is_home_replaced
        self.requested_path = requested_path


class FileManager:
    """Manages plain files and source files included in blocks.

    This is specially crafted to construct synthetic files so that
    compiling can happen correctly.  The in-game "build" tool has
    restrictions on allowed file names, and this file manager helps
    to put them into the correct location.  It also helps to manage
    the "import_code" lines to reference the correct location.

    The text_contents maps from the game file system
    to the file's contents.  The text_files and source_files maps from the game file
    system to the local file location.

    Sources are specially handled.  It assumes that the "import_code" line
    references the file relative to that source file's location.
    """

    __slots__ = (
        "text_contents",
        "text_files",
        "source_files",
        "_cleaned_source_map",
    )

    IMPORT_RE = re.compile(r'^\s*import_code\s*\(\s*"([^"]+)"\s*\)\s*$')
    GOOD_SRC_FILE_CHARS = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./"
    )

    def __init__(self) -> None:
        self.text_contents: Dict[str, str] = {}
        self.text_files: Dict[str, str] = {}
        self.source_files: Dict[str, str] = {}

        # Map of original name -> clean name
        self._cleaned_source_map: Dict[str, str] = {}

    def add_text_contents(self, game_file: str, contents: str) -> bool:
        """Marks the game file as containing the given contents."""
        if (
            game_file in self.text_contents
            or game_file in self.text_files
            or game_file in self.source_files
        ):
            log_error("Duplicate game file listed: {game_file}", game_file=game_file)
            return False
        self.text_contents[game_file] = contents
        return True

    def add_local_text_file(self, game_file: str, local_file: str) -> bool:
        """Loads the local file as a text file, for adding into the game file's location."""
        if (
            game_file in self.text_contents
            or game_file in self.text_files
            or game_file in self.source_files
        ):
            log_error("Duplicate game file listed: {game_file}", game_file=game_file)
            return False
        if not os.path.isfile(local_file):
            log_error("Could not find file '{local_file}'", local_file=local_file)
            return False
        self.text_files[game_file] = local_file
        return True

    def add_local_source_file(self, game_file: str, local_file: str) -> bool:
        """Loads the local file as a text file, for adding into the game file's location."""
        if (
            game_file in self.text_contents
            or game_file in self.text_files
            or game_file in self.source_files
        ):
            log_error("Duplicate game file listed: {game_file}", game_file=game_file)
            return False
        if not os.path.isfile(local_file):
            log_error("Could not find file '{local_file}'", local_file=local_file)
            return False
        self.source_files[game_file] = local_file
        self._cleaned_source_map[game_file] = FileManager._clean_source_name(game_file)
        return True

    def get_clensed_source_file(self, game_file: str) -> str:
        """Get the build-able source file game name.  If the file has never
        been added as a source file, then it will return the passed-in name."""
        return self._cleaned_source_map.get(game_file, game_file)

    def process_file_map(self) -> Optional[Sequence[MappedFile]]:
        """Process the files to construct the game file -> contents map.
        Returns None on error.  The contents are (contents, has-home-replacement)"""
        is_ok = True

        debug(
            "Handling raw text files {raw_text}, and source files {source_files}.  "
            "Cleaned file names: {cleaned_map}",
            raw_text=tuple(self.text_contents.keys()),
            source_files=tuple(self.source_files.keys()),
            cleaned_map=self._cleaned_source_map,
        )

        # First off, the plain text files are added as-is.
        ret: List[MappedFile] = [
            MappedFile(path=k, requested_path=k, contents=v, is_home_replaced=False)
            for k, v in self.text_contents.items()
        ]
        for game_file, local_file in self.text_files.items():
            contents = FileManager._load_file(local_file)
            if contents is None:
                is_ok = False
                contents = ""
            debug("Added game file {game_file}", game_file=game_file)
            ret.append(
                MappedFile(
                    path=game_file,
                    requested_path=game_file,
                    contents=contents,
                    is_home_replaced=False,
                )
            )

        # Next is the source files.
        # As files are parsed, more source files can be added.
        remaining_to_parse: List[Tuple[str, str, str]] = [
            (k, self._cleaned_source_map[k], v) for k, v in self.source_files.items()
        ]
        have_parsed: Set[str] = set()

        while remaining_to_parse:
            orig_game_file, game_file, local_file = remaining_to_parse.pop()
            debug(
                "Handling source file {local_file} -> {game_file}",
                game_file=game_file,
                local_file=local_file,
            )
            if game_file in have_parsed:
                continue
            have_parsed.add(game_file)
            contents = FileManager._load_file(local_file)
            if contents is None:
                is_ok = False
                contents = ""
            else:
                contents = self._clean_source(
                    local_file=local_file,
                    contents=contents,
                    discovered_sources=remaining_to_parse,
                )
            debug("Added game file {game_file}", game_file=game_file)
            ret.append(
                MappedFile(
                    path=game_file,
                    requested_path=orig_game_file,
                    contents=contents,
                    is_home_replaced=True,
                )
            )

        if is_ok:
            return ret
        return None

    def _clean_source(
        self,
        *,
        local_file: str,
        contents: str,
        discovered_sources: List[Tuple[str, str, str]],
    ) -> str:
        """Special content parsing to discover included files, as well as minimizing
        the source code."""
        ret = ""
        for line in contents.splitlines():
            # Strip each line, to help minimize it.
            line = FileManager._strip_trailing_comment(line.strip())
            # Do not skip blank lines.  It's really useful to keep line numbers the same.

            # Change imports.
            mtc = FileManager.IMPORT_RE.match(line)
            if mtc:
                # Matched up an import_code path.
                include_ref = mtc.group(1)
                # The included file is relative to the local file's location.

                import_file = self._add_import_file(
                    local_file=local_file,
                    include_ref=include_ref,
                    discovered_sources=discovered_sources,
                )
                if import_file.startswith("~/"):
                    # home_dir is built to not have a trailing '/'.
                    import_file = REPLACED_WITH_HOME + import_file[1:]
                line = f'import_code("{import_file}")'
            ret += "\n" + line
        return ret

    def _add_import_file(
        self,
        *,
        local_file: str,
        include_ref: str,
        discovered_sources: List[Tuple[str, str, str]],
    ) -> str:
        """The include file is relative to the local file."""
        # Try to match the included reference file to a file that's already been
        # added via a source file or text file.  If the included file isn't
        # a clean name, then it's put in the discovered sources.
        base_dir = os.path.abspath(os.path.dirname(local_file))
        included_local = os.path.join(base_dir, include_ref)
        for g_f, l_f in self.text_files.items():
            if os.path.abspath(l_f) == included_local:
                clean_name = FileManager._clean_source_name(g_f)
                if clean_name != g_f:
                    # Need to make a new version of the file.
                    # This implicitly turns the text file into a source file, though.
                    # orig_game_file, game_file, local_file
                    discovered_sources.append((g_f, clean_name, l_f))
                    return clean_name
                else:
                    # Reuse the game file.
                    # It wasn't added as a source file, so it won't be
                    # processed as a source file.  This might not be the desired behavior.
                    # It means clean and dirty game file locations will have different
                    # behavior, which is a sign of a bad API.
                    return g_f

        for g_f, l_f in self.source_files.items():
            if os.path.abspath(l_f) == included_local:
                # Reuse the game file.  It is already registered
                # in the cleaned name registry
                return self._cleaned_source_map[g_f]

        # Implicitly add the file.  Because it's implicitly added, it will be put
        # into the temp dir by default.
        g_f = FileManager._clean_source_name(f"{TEMP_DIR}/src/{include_ref}")
        self._cleaned_source_map[g_f] = g_f
        # orig_game_file, game_file, local_file
        discovered_sources.append((g_f, g_f, included_local))
        return g_f

    @staticmethod
    def _strip_trailing_comment(line: str) -> str:
        """Strip a trailing comment (//).  This needs to be careful for the
        situation where '//' is inside a string.  Because strings use "" to escape
        a quote, that means parsing for inside or outside a string is much easier."""
        # Easy case.  See if we even need to do anything.
        if "//" not in line:
            return line
        state = 0
        for pos in range(0, len(line)):
            val = line[pos]
            if state == 0:
                # in plain text
                if val == '"':
                    state = 1
                elif val == "/":
                    state = 2
                # else keep looking
            elif state == 1:
                # Inside a string.
                if val == '"':
                    state = 0
                # else keep looking
            elif state == 2:
                # Found a first '/'.
                if val == "/":
                    # Found the second "/" outside a string.  Comment started
                    # the character before this one.
                    return line[: pos - 1]
        # The "//" was inside a string.
        return line

    @staticmethod
    def _clean_source_name(game_file: str) -> str:
        """Clean the file name that is used as a source file.  If the name
        is unclean, it will be put into the TEMP_DIR using a unique file mapping."""
        if not game_file:
            return ""

        cleaned = ""
        remaining = game_file
        removed = ""
        if remaining[0] == "~":
            # This is the only place the ~ is okay.
            cleaned = "~" + cleaned[1:]
            remaining = remaining[1:]

        for c in remaining:
            if c not in FileManager.GOOD_SRC_FILE_CHARS:
                removed += "X"
                cleaned += "X"
            else:
                cleaned += c

        if removed:
            # There were bad characters.
            # Need to change the location.
            if cleaned.startswith(f"{TEMP_DIR}/"):
                cleaned = cleaned[len(f"{TEMP_DIR}/") :]
            if cleaned.startswith("src/"):
                cleaned = cleaned[len("src/") :]

            if cleaned.startswith("~/"):
                cleaned = cleaned[len("~/") :]
            if not cleaned:
                cleaned = "X"
            if cleaned[0] != "/":
                cleaned = "/" + cleaned
            return f"{TEMP_DIR}/src/dirty{removed}{cleaned}"
        return game_file

    @staticmethod
    def _load_file(local_file: str) -> Optional[str]:
        """Load the local file's contents."""
        try:
            with open(local_file, "r", encoding="utf-8") as fis:
                return fis.read()
        except OSError as err:
            log_error(
                "Failed reading '{local_file}': {err}",
                local_file=local_file,
                err=str(err),
            )
            return None


# -----------------------------------------------
# Block storage


class Blocks:
    """Stores the blocks"""

    def __init__(self) -> None:
        # maps to (string index, is-home-replaced)
        self._strings: Dict[str, int] = {}
        self._home_replace_strings: Dict[str, int] = {}
        self._rel_paths: Dict[str, int] = {}
        self._string_idx = 0
        self._folders: List[Tuple[str, bytes]] = []
        self._files = FileManager()
        self._build_blocks: List[bytes] = []
        self._test_blocks: List[bytes] = []
        self._test_files: Dict[str, str] = {}
        self._user_blocks: List[bytes] = []
        self._group_blocks: List[bytes] = []
        self._other_blocks: List[bytes] = []

    def assemble(self) -> Optional[bytes]:
        """Assemble the body of the data."""
        # The assembled order must be done to make the extract script
        # as trivial in implementation as possible.  So ordering is done here.

        # Need to set up the files first.  That dictates folders and other things.
        # They can't be set up until all the files are added.
        file_blocks: List[bytes] = []
        file_to_contents = self._files.process_file_map()
        if file_to_contents is None:
            return None
        for mapped_file in file_to_contents:
            if mapped_file.requested_path in self._test_files:
                # It's a test file.
                self.add_test(
                    self._test_files[mapped_file.requested_path], mapped_file.contents
                )
            else:
                # It's a source file.
                file_blocks.append(
                    self._add_file(
                        mapped_file.path,
                        mapped_file.contents,
                        mapped_file.is_home_replaced,
                    )
                )

        # Now all the blocks are ready to go.

        # Header first
        ret = mk_block_header(FILE_VERSION__UNCOMPRESSED)

        # Then the strings
        for text, idx in self._strings.items():
            ret += mk_block_string(idx, text, False)
        for text, idx in self._home_replace_strings.items():
            ret += mk_block_string(idx, text, True)
        for text, idx in self._rel_paths.items():
            ret += mk_block_rel_home(idx, text)
        # Then the folders, ordered so that they can be simply
        # created.
        folders = sorted(self._folders, key=lambda a: a[0])
        for _, block in folders:
            ret += block

        # Then the files.  Order doesn't matter here.
        for block in file_blocks:
            ret += block
        # Then build the files.  Order doesn't matter here.
        for block in self._build_blocks:
            ret += block
        # Then users.  Order doesn't matter.
        for block in self._user_blocks:
            ret += block
        # Then groups assigned to users.  Order doesn't matter.
        for block in self._group_blocks:
            ret += block
        # Then the other stuff.  This requires everything else to already exist.
        for block in self._other_blocks:
            ret += block
        # Finally, test it.
        for block in self._test_blocks:
            ret += block
        return ret

    def _add_string(self, text: str) -> int:
        if text in self._strings:
            ret = self._strings[text]
        else:
            ret = self._string_idx
            self._string_idx += 1
            self._strings[text] = ret
        return ret

    def _add_home_replace_string(self, text: str) -> int:
        if text in self._home_replace_strings:
            ret = self._home_replace_strings[text]
        else:
            ret = self._string_idx
            self._string_idx += 1
            self._home_replace_strings[text] = ret
        return ret

    def _add_path(self, text: str) -> int:
        group = self._strings
        if text == "~":
            group = self._rel_paths
            text = ""
        elif text[0:2] == "~/":
            group = self._rel_paths
            text = text[2:]
        elif text != "/" and text:
            while text[-1] == "/":
                text = text[:-1]
        if text in group:
            idx = group[text]
        else:
            idx = self._string_idx
            self._string_idx += 1
            group[text] = idx
        return idx

    def add_folder(self, folder_name: str) -> None:
        """Create a folder block."""
        # debug(f"ADD FOLDER [{folder_name}]")
        if folder_name == "/" or folder_name == "~":
            # The root was reached during recursive adds.
            return

        parent, name = Blocks._split(folder_name)
        if name == "":
            # this reached the root during recursive required adds.
            # If parent isn't empty, then there was a relative
            # directory request, which is not recommended.
            # If the parent is empty, then it's gone up the
            # whole tree.
            # Ignore it.
            return

        # Check that the joint path hasn't already been added.
        normalized = parent + "/" + name
        for exist, _ in self._folders:
            if exist == normalized:
                # already added
                return

        # Ensure the parent is added, to make the bundle assembly
        # definition simpler.
        self.add_folder(parent)

        # If the parent is empty, then a folder is being added to the
        # root directory.
        parent_idx = self._add_path(parent)
        name_idx = self._add_string(name)
        self._folders.append((normalized, mk_block_folder(parent_idx, name_idx)))

    def add_local_text_file(self, game_file: str, local_file: str) -> None:
        """Add a local file as a plain text file."""
        self._files.add_local_text_file(game_file, local_file)

    def add_local_source_file(self, game_file: str, local_file: str) -> None:
        """Add a local file as a source file."""
        self._files.add_local_source_file(game_file, local_file)

    def add_contents_file(self, game_file: str, contents: str) -> None:
        """Add plain text contents as a file."""
        self._files.add_text_contents(game_file=game_file, contents=contents)

    def add_test_file(self, name: str, local_file: str) -> None:
        """Store the local file as a game file, but it will be
        only used for running a test.  Its contents will be added
        later during file parsing."""
        game_file = f"{TEMP_DIR}/tests/{name}.src"
        self.add_local_source_file(game_file, local_file)
        self._test_files[game_file] = name

    def _add_file(self, file_name: str, contents: str, replace_home: bool) -> bytes:
        """Create a file block."""
        parent, name = Blocks._split(file_name)
        assert name
        # Ensure the parent directory is created.
        # This makes bundle definition easier.
        self.add_folder(parent)

        dirname_idx = self._add_path(parent)
        fname_idx = self._add_string(name)
        if replace_home:
            contents_idx = self._add_home_replace_string(contents)
        else:
            contents_idx = self._add_string(contents)
        return mk_block_file(dirname_idx, fname_idx, contents_idx)

    def add_user(self, username: str, password: str) -> None:
        """Create a new user block."""
        username_idx = self._add_string(username)
        password_idx = self._add_string(password)
        self._user_blocks.append(mk_block_user(username_idx, password_idx))

    def add_group(self, username: str, group: str) -> None:
        """Create a new group, or assign a user to a group, block."""
        username_idx = self._add_string(username)
        group_idx = self._add_string(group)
        self._group_blocks.append(mk_block_group(username_idx, group_idx))

    def add_chmod(self, file_name: str, perms: str, recursive: bool) -> None:
        """Create a chmod block."""
        file_name_idx = self._add_path(Blocks._normalize(file_name))
        perms_idx = self._add_string(perms)
        self._other_blocks.append(mk_block_chmod(file_name_idx, perms_idx, recursive))

    def add_chown(self, file_name: str, username: str, recursive: bool) -> None:
        """Create a chown block"""
        file_name_idx = self._add_path(Blocks._normalize(file_name))
        username_idx = self._add_string(username)
        self._other_blocks.append(
            mk_block_chown(file_name_idx, username_idx, recursive)
        )

    def add_chgroup(self, file_name: str, group: str, recursive: bool) -> None:
        """Create a chgroup block"""
        file_name_idx = self._add_path(Blocks._normalize(file_name))
        group_idx = self._add_string(group)
        self._other_blocks.append(mk_block_chgroup(file_name_idx, group_idx, recursive))

    def add_build(self, source: str, target: str) -> None:
        """Create a build block."""
        # Note: the name MUST be the clensed name.
        #  That means it must be added first.
        source = self._files.get_clensed_source_file(source)
        source_idx = self._add_path(Blocks._normalize(source))
        target_p, target_n = Blocks._split(target)
        # Ensure the target parent directory exists
        self.add_folder(target_p)
        dirname_idx = self._add_path(target_p)
        fname_idx = self._add_string(target_n)
        self._build_blocks.append(mk_block_build(source_idx, dirname_idx, fname_idx))

    def add_test(self, name: str, contents: str) -> None:
        """Create a test block."""
        # Ensure the test directory exists first.
        debug("Adding test [{name}]", name=name)
        self.add_folder(TEMP_DIR + "/tests")
        test_idx = len(self._test_blocks)
        name_idx = self._add_string(name)
        # Test files always have a home replacement string strategy.
        contents_idx = self._add_home_replace_string(contents)
        self._test_blocks.append(mk_block_test(test_idx, name_idx, contents_idx))

    def add_launch(self, args: Sequence[str]) -> None:
        """Create a launch block."""
        # Added to the 'build' set of instructions.
        # Arguments are considered paths, but don't force them to be normalized.
        arg_idx: List[int] = [self._add_path(a) for a in args]
        self._build_blocks.append(mk_block_launch(arg_idx))

    def add_copy(self, source: str, target: str) -> None:
        """Create a copy file block."""
        # Added to the 'build' set of instructions.
        source_idx = self._add_path(Blocks._normalize(source))
        target_p, target_n = Blocks._split(target)
        # Ensure the target parent directory exists
        self.add_folder(target_p)
        dirname_idx = self._add_path(target_p)
        fname_idx = self._add_string(target_n)
        self._build_blocks.append(mk_block_copy(source_idx, dirname_idx, fname_idx))

    def add_move(self, source: str, target: str) -> None:
        """Create a move file block."""
        # Added to the 'build' set of instructions.
        source_idx = self._add_path(Blocks._normalize(source))
        target_p, target_n = Blocks._split(target)
        # Ensure the target parent directory exists
        self.add_folder(target_p)
        dirname_idx = self._add_path(target_p)
        fname_idx = self._add_string(target_n)
        self._build_blocks.append(mk_block_move(source_idx, dirname_idx, fname_idx))

    def add_delete(self, path: str) -> None:
        """Create delete a file or folder block."""
        # Added to the 'build' set of instructions.
        path_idx = self._add_path(Blocks._normalize(path))
        self._build_blocks.append(mk_block_delete(path_idx))

    @staticmethod
    def _split(name: str) -> Tuple[str, str]:
        name = Blocks._normalize(name)
        if "/" not in name:
            return name, ""
        pos = name.rindex("/")
        parent = name[:pos]
        fname = name[pos + 1 :]
        return parent, fname

    @staticmethod
    def _normalize(name: str) -> str:
        name = name.replace("\\", "/")
        while "//" in name:
            name = name.replace("//", "/")
        return name


# =====================================================================
# Parse the JSON data.


def parse_folder_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse an explicit 'folder' block."""
    name = data.get("path")
    if name is None or not isinstance(name, str):
        log_error("'folder' block requires the folder name in the 'path' key")
        return False
    blocks.add_folder(name)
    return True


def parse_file_block(blocks: Blocks, data: Mapping[str, Any], context_dir: str) -> bool:
    """Parse a simple 'file' block."""
    name = data.get("path")
    contents = data.get("contents")
    local_file = data.get("local")
    if (name is None or not isinstance(name, str)) or (
        (contents is None or not isinstance(contents, str))
        and (local_file is None or not isinstance(local_file, str))
    ):
        log_error("'file' block requires 'path', and one of 'content' or 'local'.")
        return False

    if contents:
        blocks.add_contents_file(name, contents)
    else:
        assert local_file is not None  # nosec  # for mypy
        blocks.add_local_text_file(name, os.path.join(context_dir, local_file))
    return True


def parse_source_block(
    blocks: Blocks, data: Mapping[str, Any], context_dir: str
) -> bool:
    """Parse source code block."""
    name = data.get("path")
    local_file = data.get("local")
    if (name is None or not isinstance(name, str)) or (
        local_file is None or not isinstance(local_file, str)
    ):
        log_error("'source' block requires 'path' and 'local'.")
        return False

    blocks.add_local_source_file(name, os.path.join(context_dir, local_file))
    return True


def parse_test_block(blocks: Blocks, data: Mapping[str, Any], context_dir: str) -> bool:
    """Parse compiling and running a test block."""
    name = data.get("name")
    contents = data.get("contents")
    local_file = data.get("local")
    if (name is None or not isinstance(name, str)) or (
        (contents is None or not isinstance(contents, str))
        and (local_file is None or not isinstance(local_file, (str, list, tuple)))
    ):
        log_error("'test' block requires 'name' and one of 'contents' or 'local'.")
        return False

    if contents:
        # No parsing of the contents.
        blocks.add_test(name, contents)
        return True

    # The local file must be parsed as a source file.
    if isinstance(local_file, str):
        local_file = [local_file]
    assert isinstance(local_file, (tuple, list))  # nosec  # for mypy
    count = 0
    for l_f in local_file:
        for filename in glob.iglob(os.path.join(context_dir, l_f)):
            if os.path.isfile(filename):
                test_name = f"{name}-{os.path.splitext(os.path.basename(filename))[0]}"
                debug(
                    "Adding {test} test for '{filename}' as '{test_name}'",
                    test=name,
                    filename=filename,
                    test_name=test_name,
                )
                blocks.add_test_file(test_name, filename)
                count += 1
    if count <= 0:
        log_error("Found no files matching {pattern}", pattern=local_file)
        return False
    return True


def parse_build_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """A simple 'build' block."""
    source = data.get("source")
    target = data.get("target")
    if (
        source is None
        or not isinstance(source, str)
        or target is None
        or not isinstance(target, str)
    ):
        log_error("'build' block requires 'source' and 'target'")
        return False
    blocks.add_build(source, target)
    return True


def parse_compile_block(
    blocks: Blocks, data: Mapping[str, Any], context_dir: str
) -> bool:
    """A combination source + build + test block."""
    local_file = data.get("local")
    test_files = data.get("local-tests")
    target = data.get("target")
    if (
        local_file is None
        or not isinstance(local_file, str)
        or target is None
        or not isinstance(target, str)
    ):
        log_error(
            "'compile' block requires 'local' and 'target', and optionally 'local-tests'"
        )
        return False
    source_name = f"{TEMP_DIR}/build.source/{os.path.basename(local_file)}"
    blocks.add_local_source_file(source_name, os.path.join(context_dir, local_file))
    # Tests run before the target builds.
    ret = True
    if test_files and isinstance(test_files, (str, list, tuple)):
        # Ignore problem?
        ret = parse_test_block(
            blocks,
            {
                "name": os.path.splitext(os.path.basename(local_file))[0],
                "local": test_files,
            },
            context_dir,
        )
    blocks.add_build(source_name, target)
    return ret


def parse_user_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a create a user block."""
    user = data.get("user")
    passwd = data.get("password")
    if (
        user is None
        or not isinstance(user, str)
        or passwd is None
        or not isinstance(passwd, str)
    ):
        log_error("'user' block requires 'user' and 'password'")
        return False

    blocks.add_user(user, passwd)
    return True


def parse_group_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a create/add a user to a group block."""
    user = data.get("user")
    group = data.get("group")
    if (
        user is None
        or not isinstance(user, str)
        or group is None
        or not isinstance(group, str)
    ):
        log_error("'group' block requires 'user' and 'group'")
        return False

    blocks.add_group(user, group)
    return True


def parse_chmod_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a chmod block."""
    filename = data.get("path")
    recursive = data.get("recursive", False)
    permissions = data.get("permissions")
    if (
        filename is None
        or not isinstance(filename, str)
        or permissions is None
        or not isinstance(permissions, str)
        or not isinstance(recursive, bool)
    ):
        log_error(
            "'chmod' block requires 'path' and 'permissions', and optionally 'recursive'"
        )
        return False

    blocks.add_chmod(filename, permissions, recursive)
    return True


def parse_chown_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a chown block."""
    filename = data.get("path")
    recursive = data.get("recursive", False)
    owner = data.get("owner")
    user = data.get("user")
    if (
        filename is None
        or not isinstance(filename, str)
        or not isinstance(recursive, bool)
    ):
        log_error(
            "'chown' block requires 'path' and 'owner' or 'user', and optionally 'recursive'"
        )
        return False

    if owner is not None and isinstance(owner, str):
        if user:
            log_error("'chown' must have one of 'owner' or 'user', but not both")
            return False
        cpos = owner.find(":")
        if 0 <= cpos < len(owner) - 1:
            blocks.add_chown(filename, owner[:cpos], recursive)
            blocks.add_chgroup(filename, owner[cpos + 1 :], recursive)
        else:
            blocks.add_chown(filename, owner, recursive)
    elif user is not None and isinstance(user, str):
        blocks.add_chown(filename, user, recursive)
    else:
        log_error(
            "'chown' block requires 'file' and 'owner' or 'user', and optionally 'recursive'"
        )
        return False

    return True


def parse_chgroup_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a chgroup block."""
    filename = data.get("path")
    recursive = data.get("recursive", False)
    group = data.get("group")
    if (
        filename is None
        or not isinstance(filename, str)
        or group is None
        or not isinstance(group, str)
        or not isinstance(recursive, bool)
    ):
        log_error(
            "'chgroup' block requires 'path' and 'group', and optionally 'recursive'"
        )
        return False

    blocks.add_chgroup(filename, group, recursive)
    return True


def parse_launch_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a run an executable block."""
    filename = data.get("cmd")
    arguments = data.get("arguments")
    if arguments is None:
        arguments = ()
    if isinstance(arguments, str):
        arguments = [arguments]
    if (
        filename is None
        or not isinstance(filename, str)
        or arguments is None
        or not isinstance(arguments, (tuple, str))
    ):
        log_error("'exec' block requires 'cmd' and optional 'arguments' list")
        return False

    blocks.add_launch([filename, *arguments])
    return True


def parse_copy_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a copy file block."""
    from_file = data.get("from")
    to_file = data.get("to")
    if (
        from_file is None
        or not isinstance(from_file, str)
        or to_file is None
        or not isinstance(to_file, str)
    ):
        log_error("'copy' block requires 'from' and 'to'")
        return False

    blocks.add_copy(from_file, to_file)
    return True


def parse_move_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a move file block."""
    from_file = data.get("from")
    to_file = data.get("to")
    if (
        from_file is None
        or not isinstance(from_file, str)
        or to_file is None
        or not isinstance(to_file, str)
    ):
        log_error("'move' block requires 'from' and 'to'")
        return False

    blocks.add_move(from_file, to_file)
    return True


def parse_delete_block(
    blocks: Blocks, data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse a delete file block."""
    filename = data.get("path")
    if filename is None or not isinstance(filename, str):
        log_error("'delete' block requires 'path'")
        return False

    blocks.add_delete(filename)
    return True


def parse_about_block(
    _blocks: Blocks, _data: Mapping[str, Any], _context_dir: str
) -> bool:
    """Parse the metadata information for this bundle."""
    return True


BLOCK_TYPE_COMMANDS: Mapping[str, Callable[[Blocks, Mapping[str, Any], str], bool]] = {
    "folder": parse_folder_block,
    "file": parse_file_block,
    "source": parse_source_block,
    "test": parse_test_block,
    "build": parse_build_block,
    "compile": parse_compile_block,
    "user": parse_user_block,
    "group": parse_group_block,
    "chmod": parse_chmod_block,
    "chown": parse_chown_block,
    "chgroup": parse_chgroup_block,
    "exec": parse_launch_block,
    "run": parse_launch_block,
    "copy": parse_copy_block,
    "cp": parse_copy_block,
    "move": parse_move_block,
    "mv": parse_move_block,
    "rename": parse_move_block,
    "ren": parse_move_block,
    "delete": parse_delete_block,
    "del": parse_delete_block,
    "rm": parse_delete_block,
    "about": parse_about_block,
}


def parse_block_cmd(
    blocks: Blocks,
    value: Dict[str, Any],
    context_dir: str,
) -> bool:
    """Create a block command from a json entry.

    Folders are left for later.  They must be added at the start of the block list,
    and be ordered correctly.
    """
    cmd = str(value.get("type", ""))

    parser = BLOCK_TYPE_COMMANDS.get(cmd)
    if not parser:
        log_error("Unknown block type '{cmd}'", cmd=cmd)
        return False

    return parser(blocks, value, context_dir)


def parse_json(data: Any, context_dir: str) -> Optional[bytes]:
    """Parse the json data into the block store."""
    if not isinstance(data, (list, tuple)):
        log_error("Bundle data must be an array of blocks.")
        return None
    blocks = Blocks()

    # Must always exist
    blocks.add_folder(TEMP_DIR)

    for block in data:
        parse_block_cmd(blocks, block, context_dir)

    return blocks.assemble()

# =====================================================================
# Compression

def compress_dictionary_creation(body: bytes) -> Tuple[int, Dict[bytes, int]]:
    """Constructs a reverse lookup dictionary - the lookup string
    to the lookup index.
    
    The algorithm is restricted by the dictionary header to searching for
    at most 16 byte strings.  The dictionary size is limited to 12 bits
    (0-4095).  The very last dictionary entry is reserved as a end-of-stream
    marker.

    Returns (max string length, dictionary)
    """
    # First, construct a histogram of the possiblities.
    histo = Counter()
    body_len = len(body)
    for count in range(2, 16):
        for pos in range(0, body_len - count + 1):
            histo[bytes(body[pos:pos+count])] += 1
    
    # Find all the distinct, single values in the stream.
    # These are required to be in the dictionary, but will
    # be
    single_values = Counter()
    for val in body:
        single_values[bytes([val])] += 1
    # we'll use at most the top 12-bits minus the
    # individual byte count and the last value marker (1)
    # = 4096 - len(single_values) - 1 = 4095 - len(single_values) values
    common = histo.most_common(4095 - len(single_values)) + single_values.most_common()
    common.sort(key=lambda a: a[1])
    assert len(common) <= 4095

    ret: Dict[bytes, Tuple[bytes, int]] = {}
    index = 0
    max_len = 0
    for sub, _ in common:
        max_len = max(max_len, len(sub))
        ret[sub] = index
        index += 1
    
    return max_len, ret


def compress_encoded_body(body: bytes, max_item_len: int, reverse_lookup: Dict[bytes, int]) -> List[int]:
    """Encode the body into lookup table indexes."""
    pos = 0
    body_len = len(body)
    ret: List[int] = []
    while pos < body_len:
        # Find the longest string that is in the dictionary starting with pos.
        try:
            tail = min(pos + max_item_len + 1, body_len)
            while tail > pos:
                sub = body[pos:tail]
                index = reverse_lookup.get(sub)
                if index is not None:
                    ret.append(index)
                    pos = tail
                    raise StopIteration
                tail -= 1
        except StopIteration:
            pass
        else:
            raise RuntimeError(f"Did not stop; incorrect substring table construction (@{pos}/{max_item_len}, c = {body[pos:pos+1]}, {reverse_lookup})")
    return ret


def compress_compacted_body_lookup(encoded: List[int], reverse_lookup: Dict[bytes, int]) -> Tuple[List[int], Dict[bytes, int]]:
    """A final pass over the body and lookup to compact it down to just the entries used."""
    lookup: Dict[int, bytes] = {}
    for sub, orig_idx in reverse_lookup.items():
        lookup[orig_idx] = sub

    # Because a fixed length encoding value is used, we don't care about ordering the
    # dictionary in terms of frequency.  However, due to the dictionary storage, it's smaller
    # to store it with same-sized entries grouped together.  So sort entries by size.
    
    histo: Set[int] = set()
    for idx in encoded:
        histo.add(idx)
    used_indicies = list(histo)
    used_indicies.sort(key=lambda v: len(lookup[v]))

    old_to_new: Dict[int, int] = {}
    translated: Dict[bytes, int] = {}
    count = 0
    for orig_idx in used_indicies:
        old_to_new[orig_idx] = count
        translated[lookup[orig_idx]] = count
        count += 1
    
    recoded: List[int] = []
    for orig_idx in encoded:
        recoded.append(old_to_new[orig_idx])

    return recoded, translated


def mk_compress_header(reverse_lookup: Dict[bytes, int]) -> bytes:
    """Create the compression lookup header."""
    # The lookup is bytes -> index, but the header needs to write
    # index -> bytes.
    # Additionally, it writes (encoded byte count, number with the byte count)
    # The final sub-block is a 0 number of bytes with that count, and 0 count.
    lookup: Dict[int, bytes] = {}
    for key, index in reverse_lookup.items():
        assert index not in lookup
        lookup[index] = key

    # Create a list of shared size, in order of index.
    # Seed the lists with index 0.
    assert 0 in lookup
    sized_ordered: List[List[int]] = [[lookup[0]]]
    prev_len = len(lookup[0])
    for idx in range(1, len(lookup)):
        val = lookup[idx]
        if len(val) != prev_len:
            prev_len = len(val)
            sized_ordered.append([])
        elif len(sized_ordered[-1]) >= 15:
            # Need to create another group, because each group is
            # limited to 15 members.
            sized_ordered.append([])
        sized_ordered[-1].append(val)

    header = b''
    debug_idx = 0
    for group in sized_ordered:
        # Add the byte with the (item length - 1 | item count)
        item_len = len(group[0])
        assert 0 < item_len <= 16
        item_count = len(group)
        assert 0 < item_count < 16
        group_header = ((item_len - 1) << 4) | item_count
        header += mk_uint8(group_header)

        for item in group:
            # Directly add the whole item to the header.
            # debug(f"d[{debug_idx}] = {item}")
            # debug_idx += 1
            header += item

    # Put the terminator.
    header += mk_uint8(0)
    debug(f"Compression header size: {len(header)} bytes")
    return header


def mk_encoded_body(encoded: List[int], table_size: int) -> bytes:
    """Convert the body into index lookups in the lookup table."""
    ret = b''
    remainder = 0
    is_odd = False
    for idx in encoded:
        # Do the variable length encoding
        # debug(f"[] = {idx}")
        if is_odd:
            ret += bytes([remainder | ((idx >> 8) & 0xf)])
            ret += bytes([idx & 0xff])
        else:
            ret += bytes([(idx >> 4) & 0xff])
            remainder = ((idx << 4) & 0xf0)
        is_odd = not is_odd
    # Add the table size index to mark the end of the data.
    if is_odd:
        ret += bytes([remainder | ((table_size >> 8) & 0xf)])
        ret += bytes([table_size & 0xff])
    else:
        ret += bytes([(table_size >> 4) & 0xff])
        # Directly add the value to the buffer, not to the remainder.
        ret += bytes([(table_size << 4) & 0xf0])

    debug(f"Compressed body size: {len(ret)} bytes")
    return ret


def compress(body: bytes) -> bytes:
    """Final assembly of the blocks.
    
    This is a custom compression tool based on nybble (4-bit)
    blocks.  It contains a dictionary header split into blocks,
    each block starting with (item length - 1, item count) packed into
    one byte.  With item count == 0, that's the marker for the end
    of the dictionary.  After that, each element in the dictionary
    is an index, and they are encoded into uint12 lookup indexes (0-4095).

    The big bad part of this is the dictionary generation
    to reduce the total size of the data.  The dictionary header limits
    this to searching
    """

    # Create a reverse lookup without bytes, and the encoded body.
    max_len, reverse_lookup = compress_dictionary_creation(body)
    encoded = compress_encoded_body(body, max_len, reverse_lookup)
    encoded, reverse_lookup = compress_compacted_body_lookup(encoded, reverse_lookup)

    # Create the encoding block
    ret = mk_block_header(FILE_VERSION__COMPRESSED)
    ret += mk_compress_header(reverse_lookup)
    ret += mk_encoded_body(encoded, len(reverse_lookup))

    return ret
    

def convert(data: bytes, wide: bool) -> str:
    """Convert the data into the encoded form."""
    res = base64.a85encode(data).decode("ascii")
    ret = ""
    while res:
        ret += res[:70]
        if not wide:
            ret += "\n"
        res = res[70:]
    return ret


def main(args: Sequence[str]) -> int:
    """CLI Entrypoint."""
    parser = argparse.ArgumentParser(
        prog="ghtar",
        description="""GreyHack File Assembler.

        Combines files, folders, build, test, and run instructions into one file format.""",
        epilog="""
        This bundles JSON formatted files into a single file.  The bundle file is a JSON
        array, meaning that the file starts with '[' and ends with ']'.  Between that are
        instruction blocks.

        Each instruction block is a JSON map, which means that it starts with a '{' and ends
        with a '}', and they are divided by a ','.  Each instruction has a '"type"' key to
        declare the kind of instruction block, along with keys specific to that instruction
        block.  For example, the file:

        [
           {
             "type": "folder",
             "path": "~/src/programs"
           }
        ]

        will create the folder "/home/(username)/src/programs" on the game's computer,
        along with any missing folder between the '/'.  The system understands that paths
        starting with '~/' refers to the user home directory.

        Unpack using the `make.src` script.
        """,
    )
    parser.add_argument(
        "-l",
        "--multiline",
        action="store_true",
        dest="multiline",
        help="Output contains line breaks to make it easier on text editors.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        help="Increase verbosity.",
    )
    parser.add_argument(
        "-o",
        "--out",
        action="store",
        dest="out",
        help="Output file to contain the generated file.  Defaults to stdout.",
    )
    parser.add_argument(
        "-z",
        "--compress",
        action="store_true",
        dest="compress",
        help="Use LZW compression on the output.",
    )
    parser.add_argument(
        "filename",
        help="Source bundle file.",
    )
    parsed = parser.parse_args(args[1:])

    VERBOSE[0] = parsed.verbose
    source = parsed.filename
    if not os.path.isfile(source):
        log_error("Provided source file is not a file: {source}", source=source)
        return 1

    outfile = parsed.out
    if outfile is not None:
        if os.path.exists(outfile) and not os.path.isfile(outfile):
            log_error(
                "Invalid output file {outfile}; either it exists and "
                "isn't a file, or its parent directory doesn't exist",
                outfile=outfile,
            )
            return 1

    try:
        with open(source, "r", encoding="utf-8") as fis:
            data = json.load(fis)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as err:
        log_error(
            "Failed to read source ({source}): {err}",
            source=source,
            err=str(err),
        )
        return 1

    blocks = parse_json(data, os.path.dirname(source))
    if blocks is None:
        # already reported the error
        return 1
    if parsed.compress:
        debug(f"Source size: {len(blocks)}")
        # debug(f" = {blocks}")
        blocks = compress(blocks)
        debug(f"Compressed size: {len(blocks)}")
    out = convert(blocks, not parsed.multiline)
    if outfile is None:
        print(out)
    else:
        with open(outfile, "w", encoding="utf-8") as fos:
            fos.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
