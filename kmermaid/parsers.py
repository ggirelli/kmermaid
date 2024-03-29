"""
@author: Gabriele Girelli
@contact: gigi.ga90@gmail.com
@description: methods for sequence manipulation
"""

import gzip
import io
from typing import Iterator, List, Optional, Tuple


class SmartFastaParser:
    """Fasta parser with minimally open buffer.

    Extends the SimpleFastaParser function to avoid 'too many open files' issue.
    The input buffer is opened only when needed, and the byte-based position in
    the Fasta file is kept in memory. This continuous opening/closing adds a bit
    of an overhead but is useful when many Fasta files must be parsed at the
    same time.

    Variables:
            __compressed {bool} -- whether the Fasta is compressed.
            __pos {number} -- byte-based location in the Fasta file.
    """

    __compressed = False
    __pos = 0

    def __init__(self, FH):
        super(SmartFastaParser, self).__init__()
        if type(FH) is str:
            if FH.endswith(".gz"):
                self.__compressed = True
                self.__FH = gzip.open(FH, "rt")
            else:
                self.__FH = open(FH, "r+")
        elif type(FH) is io.TextIOWrapper:
            self.__FH = FH
            if self.__FH.name.endswith(".gz"):
                self.__compressed = True
        else:
            raise AssertionError("type error.")

    def __reopen(self):
        """Re-open the buffer and seek the last recorded position."""
        if self.__FH.closed:
            if self.__compressed:
                self.__FH = gzip.open(self.__FH.name, "rt")
            else:
                self.__FH = open(self.__FH.name, "r+")
        self.__FH.seek(self.__pos)

    def __skip_blank_and_comments(self) -> Tuple[str, bool]:
        """Skip any text before the first record (e.g. blank lines, comments)

        :return: next content line, and False if EOF or empty line was reached
        :rtype: Tuple[str, bool]
        """
        while True:
            line = self.__FH.readline()
            self.__pos = self.__FH.tell()
            if line == "":
                return ("", False)  # Premature end of file, or just empty?
            if line[0] == ">":
                break
        return (line, True)

    def __parse_sequence(self) -> List[str]:
        """Read all sequence for current record.

        :return: sequence lines
        :rtype: List[str]
        """
        lines = []
        line = self.__FH.readline()
        while True:
            if not line:
                break
            if line[0] == ">":
                break
            self.__pos = self.__FH.tell()
            lines.append(line.rstrip())
            line = self.__FH.readline()
        return lines

    def parse(self) -> Iterator[Tuple[str, str]]:
        """Iterate over Fasta records as string tuples.

        For each record a tuple of two strings is returned, the FASTA title
        line (without the leading '>' character), and the sequence (with any
        whitespace removed). The title line is not divided up into an
        identifier (the first word) and comment or description.

        Additionally, keep the Fasta handler open only when strictly necessary.

        :raises ValueError: when fasta does not pass format check
        :yield: (header, sequence)
        :rtype: Tuple[str, str]
        :raises AssertionError: if file is not parsable
        :raises ValueError: if a header line does not start with '>'
        :raises AssertionError: if the EOF is wrongly parsed
        """
        self.__reopen()
        line: Optional[str] = None
        line, parsable = self.__skip_blank_and_comments()
        if not parsable:
            raise AssertionError("premature end of file or empty file")

        while True:
            self.__reopen()
            line = self.__FH.readline() if line is None else line

            if not line:
                return

            if line[0] != ">":
                raise ValueError(
                    "Records in Fasta files should start with '>' character"
                )
            title = line[1:].rstrip()
            seq_lines = self.__parse_sequence()

            self.__FH.close()
            yield title, "".join(seq_lines).replace(" ", "").replace("\r", "")

            line = None

        raise AssertionError("Should not reach this line")

    @staticmethod
    def parse_file(path: str) -> Iterator[Tuple[str, str]]:
        """Parse a FASTA file in a smarter way.

        :param path: path to FASTA file
        :type path: str
        :return: FASTA record iterator
        :rtype: Iterator[Tuple[str, str]]
        """
        return SmartFastaParser(path).parse()
