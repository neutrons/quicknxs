r"""
Classes to handle string representations of sets of run numbers and absolute paths to data files
"""


# standard imports
import itertools
import operator
import os
import re


class RunNumbers(object):
    r"""
    A helper class to handle string representations of one or more run numbers. It translates from a
    string representation to a list of run numbers, and viceversa
    """
    merge_symbol = "+"
    range_symbol = ":"

    def __init__(self, numbers):
        # type: (Union[List[int], List[str], int, str]) -> None
        r"""
        @param numbers: a list of numbers or a string containing one or more numbers. For instance, '1:3+5' translates
          to [1, 2, 3, 5]
        """
        self._numbers = None  # type: Optional[int]
        if isinstance(numbers, int):
            self._numbers = [numbers]  # just one run number
        elif isinstance(numbers, list):
            self._numbers = sorted([int(n) for n in numbers])
        elif isinstance(numbers, str):
            if self.merge_symbol in numbers or self.range_symbol in numbers:
                self._numbers = sorted(self._uncompress(numbers))
            else:
                self._numbers = [int(numbers)]  # just one run number
        else:
            raise ValueError("Constructor requires a list or a string of run numbers as input")

    def _uncompress(self, numbers):
        # type: (str) ->  List[int]
        r"""
        @brief Split a string representation of a set of run numbers into a list
        @details Example: '1:3+6' becomes [1, 2, 3, 6]
        """
        run_numbers = list()
        for run_range in numbers.split(self.merge_symbol):  # e.g. 1:3+6' becomes ['1:3', '6']
            if self.range_symbol in run_range:  # e.g '2:7'
                first, last = [int(n) for n in run_range.split(self.range_symbol)]
                run_numbers.extend(list(range(first, last + 1)))
            else:  # a single run number, e.g. '4'
                run_numbers.append(int(run_range))
        return run_numbers

    @property
    def numbers(self):
        # type: () -> List[int]
        r"""
        @brief List of run numbers as a list of integers
        """
        return self._numbers

    @property
    def long(self):
        # type: () -> str
        r"""
        @brief Long string representation of the run numbers
        @details Example: [1, 2, 3, 6] becomes '1+2+3+6'
        """
        return self.merge_symbol.join([str(n) for n in self._numbers])

    @property
    def short(self):
        # type: () -> str
        r"""
        @brief Short string representation of the run numbers
        @details Example: [1, 2, 3, 6] becomes '1:3+6'
        """
        ranges = list()
        for _, g in itertools.groupby(
            enumerate(self._numbers), lambda i_run_number: i_run_number[0] - i_run_number[1]
        ):
            runs = list(map(operator.itemgetter(1), g))  # e.g. [3,4,5]
            run_range = str(runs[0]) if len(runs) == 1 else "{}{}{}".format(runs[0], self.range_symbol, runs[-1])
            ranges.append(run_range)
        return self.merge_symbol.join(ranges)

    @property
    def statement(self):
        # type: () -> str
        r"""
        @brief Human readable string representation.
         @details Examples: '12', '12 and 13', '12, 13, and 14'
        """
        runs_str = [str(n) for n in self._numbers]
        if len(runs_str) == 1:
            return runs_str[0]
        runs = ", ".join(runs_str[:-1])
        if len(runs_str) > 2:
            runs += ","
        runs += " and " + runs_str[-1]
        return runs


class FilePath(object):
    r"""Helper class to deal with string representation of one or more absolute file paths.

    Example:
    file_path = '/SNS/REF_M/IPTS-25531/nexus/REF_M_38202.nxs.h5+/SNS/REF_M/IPTS-25531/nexus/REF_M_38201.nxs.h5'

    NOTE: Paths are sorted
    """
    merge_symbol = "+"

    @classmethod
    def join(cls, dirname: str, basename: str, sort: bool = True) -> str:
        r"""Create the file path for a single file or a set of files using one directory

        Example: u'/SNS/REF_M/IPTS-25531/nexus/REF_M_38198.nxs.h5+/SNS/REF_M/IPTS-25531/nexus/REF_M_38199.nxs.h5'

        @param dirname: absolute path to a directory
        @param basename: name of one or more files. If more than one file, they're concatenated with the merge
        symbol '+'. Example: u'REF_M_38198.nxs.h5+REF_M_38199.nxs.h5'
        @param sort: if True, sort the basenames according to increasing run number when more than one file.

        @returns string representing the absolute path to the files.
        """
        base_names = basename.split(cls.merge_symbol)
        file_paths = [os.path.join(dirname, name) for name in base_names]
        if sort:
            file_paths.sort()
        return str(cls.merge_symbol.join(file_paths))

    @classmethod
    def unique_dirname(cls, file_path):
        r"""For composite file paths, check that the dirname of the paths is the same for all files"""
        dirs = [os.path.dirname(path) for path in file_path.split(cls.merge_symbol)]
        if len(set(dirs)) > 1:
            return False
        return True

    def __init__(self, file_path, sort=True):
        # type: (Union[str, List[str]], Optional[bool]) -> None
        if isinstance(file_path, list):
            file_path = self.merge_symbol.join(file_path)
        if not self.unique_dirname(file_path):
            raise ValueError("files in {} reside in different directories".format(file_path))
        if self.merge_symbol in file_path:
            if sort:
                paths = sorted(file_path.split(self.merge_symbol))
                self._file_path = str(self.merge_symbol.join(paths))
            else:
                self._file_path = str(file_path)
        else:
            self._file_path = str(file_path)

    def __str__(self):
        return self._file_path

    @property
    def path(self):
        return self._file_path

    @property
    def single_paths(self):
        if self.is_composite:
            return self._file_path.split(self.merge_symbol)
        return [self._file_path]

    @property
    def is_composite(self):
        return self.merge_symbol in self._file_path

    @property
    def dirname(self):
        if self.merge_symbol in self._file_path:
            first_path = self._file_path.split(self.merge_symbol)[0]
            return os.path.dirname(first_path)
        return os.path.dirname(self._file_path)

    @property
    def basename(self):
        if self.merge_symbol in self._file_path:
            names = [os.path.basename(name) for name in self._file_path.split(self.merge_symbol)]
            return self.merge_symbol.join(names)
        return os.path.basename(self._file_path)

    @property
    def first_path(self):
        if self.is_composite:
            return self._file_path.split(self.merge_symbol)[0]
        return self._file_path

    def split(self):
        return self.dirname, self.basename

    def run_numbers(self, string_representation=None):
        # type: (Optional[str]) -> Union[List[int], str]
        r"""
        @brief return the run number(s) associated to this file path
        @details This function assumes the basename of each single file path has the pattern "REF_M_XXXX.*" where
        'XXXX' is the run number to extract, and * is some file extension
        @param string_representation: If None, return the run numbers as a list of integers. If 'long', return all
        the run numbers concatenated by the merge symbol ('+'). If 'short', return a compressed string representation.
        For instance, return run numbers 1, 2, 3, 5, 7, 8 as 1:3+5+7:8
        """
        numbers = list()
        for path in self.single_paths:
            match = re.search(r"REF_M_(\d+)", path)
            if match is None:
                raise ValueError("Could not extract run number in file path {}".format(path))
            numbers.append(int(match.groups()[0]))
        numbers.sort()  # this should be unnecessary, though, since self._file_path is already sorted
        if string_representation is None:
            return numbers
        elif string_representation in ("long", "short", "statement"):
            return getattr(RunNumbers(numbers), string_representation)
        else:
            raise ValueError('parameter string_representation must be one of [None, "long", "short"]')
