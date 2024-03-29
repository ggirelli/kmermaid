"""
@author: Gabriele Girelli
@contact: gigi.ga90@gmail.com
@description: methods for batch joining
"""

import gzip
import os
import tempfile
from abc import abstractmethod
from typing import Dict, Set

import h5py  # type: ignore
import numpy as np  # type: ignore
from tqdm import tqdm  # type: ignore


class AbundanceVectorBase:
    """AbundanceVector basic structure.

    Just an empty interface for basic AbundanceVector classes.

    Variables:
            _ks {set} -- sequence lengths
    """

    _ks: Set[int] = set()

    def check_length(self, k: int) -> None:
        """Check that sequence length is compatible.

        :param k: sequence length
        :type k: int
        :raises AssertionError: if length is not compatible
        """
        self._ks.add(k)
        if len(self._ks) != 1:
            raise AssertionError(f"inconsistent sequence lengths: {self._ks}")

    @abstractmethod
    def add_count(
        self, ref: str, strand: str, pos: int, count: int, k: int, replace: bool = False
    ) -> None:
        """Add occurrence count to the vector.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param pos: position on ref:strand
        :type pos: int
        :param count: occurrence count
        :type count: int
        :param k: sequence length
        :type k: int
        :param replace: allow for replacement of non-zero counts, defaults to False
        :type replace: bool
        :raises NotImplementedError: abstract method
        """
        raise NotImplementedError

    @abstractmethod
    def add_ref(self, ref: str, strand: str, size: int) -> None:
        """Add/resize reference:strand vector.

        Adds a new reference:strand vector of given size  if absent, or resizes
        the current one is size is greater than the current one.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param size: new size
        :type size: int
        :raises NotImplementedError: abstract method
        """
        raise NotImplementedError

    @abstractmethod
    def write_to(self, dirpath: str) -> None:
        """Write AbundanceVectors to a folder.

        The extension is removed from dirpath before proceeding.

        :param dirpath: path to output directory
        :type dirpath: str
        :raises NotImplementedError: abstract method
        """
        raise NotImplementedError


class AbundanceVector(AbundanceVectorBase):
    """AbundanceVector system.

    For each records, for each strand, generates a 1-dimensional array with
    abundance counts.

    Variables:
            __data {dict} -- stores abundance vectors
    """

    __data: Dict[str, Dict[str, np.ndarray]] = {}  # {ref:{strand:np.ndarray}}

    def add_count(
        self, ref: str, strand: str, pos: int, count: int, k: int, replace: bool = False
    ) -> None:
        """Add occurrence count to the vector.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param pos: position on ref:strand
        :type pos: int
        :param count: occurrence count
        :type count: int
        :param k: sequence length
        :type k: int
        :param replace: allow for replacement of non-zero counts, defaults to False
        :type replace: bool
        :raises AssertionError: if replace is disallowed and count is not 0
        """
        super().add_count(ref, strand, pos, count, k, replace)
        self.check_length(k)
        self.add_ref(ref, strand, pos + 1)
        if not replace and self.__data[ref][strand][pos] != 0:
            raise AssertionError(
                "can't update non-zero count w/o replace: {ref},{strand},{pos},{count}"
            )
        self.__data[ref][strand][pos] = count

    def add_ref(self, ref: str, strand: str, size: int) -> None:
        """Add/resize reference:strand vector.

        Adds a new reference:strand vector of given size  if absent, or resizes
        the current one is size is greater than the current one.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param size: new size
        :type size: int
        """
        if ref not in self.__data.keys():
            self.__data[ref] = {}
        if strand not in self.__data[ref].keys():
            self.__data[ref][strand] = np.zeros(size)
        elif size > self.__data[ref][strand].shape[0]:
            self.__data[ref][strand].resize(size)

    def write_to(self, dirpath: str) -> None:
        """Write AbundanceVectors to a folder.

        The extension is removed from dirpath before proceeding.

        :param dirpath: output directory path
        :type dirpath: str
        :raises AssertionError: if input path is a file
        """
        dirpath = os.path.splitext(dirpath)[0]
        if os.path.isfile(dirpath):
            raise AssertionError
        print('Writing output in "%s"' % dirpath)
        os.makedirs(dirpath, exist_ok=True)
        for ref in self.__data:
            for strand in self.__data[ref].keys():
                fname = "%s___%s.gz" % (ref, strand)
                with gzip.open(os.path.join(dirpath, fname), "wb") as OH:
                    OH.write(b"# k=%d\n" % list(self._ks)[0])
                    for count in tqdm(self.__data[ref][strand], desc=fname):
                        OH.write(b"%d\n" % count)


class AbundanceVectorLocal(AbundanceVectorBase):
    """AbundanceVector system with local storage.

    Stores data in local binary file(s) instead of memory. Based on h5py.
    """

    __tmpH = None
    _tmp = None
    _dataList: Set[str] = set()

    def __init__(self):
        super(AbundanceVectorLocal, self).__init__()
        self.__tmpH = tempfile.TemporaryDirectory(prefix="kmmVector")
        self._tmp = self.__tmpH.name

    @property
    def tmp(self):
        return self._tmp

    def add_count(
        self, ref: str, strand: str, pos: int, count: int, k: int, replace: bool = False
    ) -> None:
        """Add occurrence count to the vector.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param pos: position on ref:strand
        :type pos: int
        :param count: occurrence count
        :type count: int
        :param k: sequence length
        :type k: int
        :param replace: allow for replacement of non-zero counts, defaults to False
        :type replace: bool
        :raises AssertionError: if abundances are non-zero without replace
        """
        super().add_count(ref, strand, pos, count, k, replace)
        self.check_length(k)
        self.add_ref(ref, strand, pos)
        with h5py.File(self.refpath(ref, strand)) as DH:
            if not replace:
                assert_msg = "cannot update a non-zero count without replace."
                assert_msg += " (%s, %s, %d, %d)" % (ref, strand, pos, count)
                if DH["abundances"][pos] != 0:
                    raise AssertionError(assert_msg)
            DH["abundances"][pos] = count

    def add_ref(self, ref: str, strand: str, size: int) -> None:
        """Add/resize reference:strand vector.

        Adds a new reference:strand vector of given size  if absent, or resizes
        the current one is size is greater than the current one.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param size: new size
        :type size: int
        """
        if not self.has_ref(ref, strand):
            self.mk_ref_file(ref, strand, size)
        else:
            with h5py.File(self.refpath(ref, strand)) as DH:
                if size + 1 > DH["abundances"].shape[0]:
                    DH["abundances"].resize((size + 1,))

    @staticmethod
    def refname(ref: str, strand: str) -> str:
        """Get reference filename

        :param ref: reference name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :return: reference filename
        :rtype: str
        """
        return "%s___%s.hdf5" % (ref, strand)

    def refpath(self, ref: str, strand: str) -> str:
        """Get path to reference file.

        :param ref: reference name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :return: path to reference file
        :rtype: str
        """
        return os.path.join(self.tmp, self.refname(ref, strand))

    def has_ref(self, ref: str, strand: str) -> bool:
        """Check if reference exists.

        :param ref: reference name.
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :return: if reference exists
        :rtype: bool
        """
        refname = self.refname(ref, strand)
        refpath = self.refpath(ref, strand)
        return os.path.isfile(refpath) and refname in self._dataList

    def mk_ref_file(self, ref: str, strand: str, size: int) -> None:
        """Generates reference file.

        :param ref: reference record name
        :type ref: str
        :param strand: strandedness
        :type strand: str
        :param size: reference size
        :type size: int
        """
        if not self.has_ref(ref, strand):
            self._dataList.add(self.refname(ref, strand))
            with h5py.File(self.refpath(ref, strand)) as DH:
                data = DH.create_dataset(
                    "abundances", (size + 1,), dtype="i", maxshape=(None,), chunks=True
                )
                data[...] = np.zeros((size + 1,))

    def write_to(self, dirpath: str) -> None:
        """Write AbundanceVectors to a folder.

        The extension is removed from dirpath before proceeding.

        :param dirpath: output directory path
        :type dirpath: str
        :raises AssertionError: if input path is a file
        """
        dirpath = os.path.splitext(dirpath)[0]
        if os.path.isfile(dirpath):
            raise AssertionError
        print('Writing output in "%s"' % dirpath)
        os.makedirs(dirpath, exist_ok=True)

        for fname in self._dataList:
            fpath = os.path.join(self.tmp, fname)
            with h5py.File(fpath) as DH:
                oname = "%s.gz" % os.path.splitext(fname)[0]
                with gzip.open(os.path.join(dirpath, oname), "wb") as OH:
                    OH.write(b"# k=%d\n" % list(self._ks)[0])
                    for count in tqdm(DH["abundances"], desc=oname):
                        OH.write(b"%d\n" % count)
