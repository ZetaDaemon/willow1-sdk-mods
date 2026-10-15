from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto

from unrealsdk import logging


class ParserState(Enum):
    READY = auto()
    WAITING_FOR_JSON = auto()
    READING_JSON = auto()
    RECOVERING = auto()


@dataclass
class CommandParser:
    parts: list[str] = field(init=False, default_factory=list)
    brackets: list[str] = field(init=False, default_factory=list)
    in_string: bool = field(init=False, default=False)
    escaped: bool = field(init=False, default=False)
    start_line: int = field(init=False, default=0)
    state: ParserState = field(init=False, default=ParserState.READY)

    def _reset(self):
        self.parts.clear()
        self.brackets.clear()
        self.in_string = False
        self.escaped = False
        self.start_line = 0
        self.state = ParserState.READY

    def _error(self, line_number: int, message: str):
        logging.error(f"Line {line_number}: {message}")

    def _scan(self, text: str) -> bool:
        pairs = {"]": "[", "}": "{"}

        for char in text:
            if self.in_string:
                if self.escaped:
                    self.escaped = False
                elif char == "\\":
                    self.escaped = True
                elif char == '"':
                    self.in_string = False
            elif char == '"':
                self.in_string = True
            elif char in "[{":
                self.brackets.append(char)
            elif char in "]}":
                if not self.brackets or self.brackets[-1] != pairs[char]:
                    return False
                self.brackets.pop()

        return True

    def parse_lines(
        self, lines: list[str], registered_commands: set[str], json_commands: set[str]
    ) -> Iterator[str]:
        self._reset()

        try:
            for line_number, raw_line in enumerate(lines, 1):
                line = raw_line.strip()

                if not line:
                    continue

                first_token = line.split(maxsplit=1)[0]

                # A registered command marks a recovery boundary.
                if self.state != ParserState.READY and first_token in registered_commands:
                    if self.state != ParserState.RECOVERING:
                        self._error(self.start_line, "Incomplete JSON before next command")
                    self._reset()

                # Skip malformed JSON until another command starts.
                if self.state == ParserState.RECOVERING:
                    continue

                if self.state == ParserState.READY:
                    # Comments are valid only between commands.
                    if line.startswith("#"):
                        continue

                    self.start_line = line_number

                    if first_token not in json_commands:
                        yield line
                        continue

                    self.parts.append(line)

                    # If JSON starts on the next line, the reader
                    # will recognise it in WAITING_FOR_JSON.
                    #
                    # Look for an object/array at the end of the
                    # command, rather than brackets anywhere in
                    # object paths.
                    json_start = self.find_json_start(line)

                    if json_start is None:
                        self.state = ParserState.WAITING_FOR_JSON
                        continue

                    self.state = ParserState.READING_JSON

                    if not self._scan(line[json_start:]):
                        self._error(line_number, "Mismatched JSON brackets")
                        self.state = ParserState.RECOVERING
                        continue

                    if not self.brackets and not self.in_string:
                        yield " ".join(self.parts)
                        self._reset()

                    continue

                if self.state == ParserState.WAITING_FOR_JSON:
                    if line.startswith("#"):
                        self._error(line_number, "Comments are not allowed inside JSON")
                        self.state = ParserState.RECOVERING
                        continue

                    self.parts.append(line)

                    if line[0] not in "[{":
                        # This might be a primitive JSON value.
                        # Pass it to the existing command parser.
                        yield " ".join(self.parts)
                        self._reset()
                        continue

                    self.state = ParserState.READING_JSON

                elif self.state == ParserState.READING_JSON:
                    if line.startswith("#"):
                        self._error(line_number, "Comments are not allowed inside JSON")
                        self.state = ParserState.RECOVERING
                        continue

                    self.parts.append(line)

                if not self._scan(line):
                    self._error(line_number, "Mismatched JSON brackets")
                    self.state = ParserState.RECOVERING
                    continue

                if not self.brackets and not self.in_string:
                    yield " ".join(self.parts)
                    self._reset()

            if self.state in (ParserState.WAITING_FOR_JSON, ParserState.READING_JSON):
                self._error(self.start_line, "Incomplete JSON at end of file")

        finally:
            self._reset()

    def find_json_start(self, line: str) -> int | None:
        """Find an inline JSON object/array after a whitespace boundary.

        Ignores brackets inside quoted strings.
        This deliberately does not treat brackets embedded in
        object/property paths as JSON.

        """
        in_string = False
        escaped = False

        for index, char in enumerate(line):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char in "[{" and (index == 0 or line[index - 1].isspace()):
                return index

        return None
