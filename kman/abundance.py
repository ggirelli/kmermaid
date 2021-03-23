"""
@author: Gabriele Girelli
@contact: gigi.ga90@gmail.com
@description: methods for batch joining
"""

import gzip
import h5py  # type: ignore
import numpy as np  # type: ignore
import os
import tempfile
from tqdm import tqdm  # type: ignore
from typing import Dict, Set


class AbundanceVectorBase(object):
    """AbundanceVector basic structure.

    Just an empty interface for basic AbundanceVector classes.

    Variables:
            _ks {set} -- sequence lengths
    """

    _ks: Set[int] = set()

    def __init__(self):
        super().__init__()

    def check_length(self, k: int):
        """Check that sequence length is compatible.

        Arguments:
                k {int} -- sequence length
        """
        self._ks.add(k)
        assert_msg = "inconsistent sequence lengths: %s" % self._ks
        assert 1 == len(self._ks), assert_msg

    def add_count(self, ref, strand, pos, count, k, replace=False):
        """Add occurrence count to the vector.

        Arguments:
                ref {str} -- reference record name
                strand {str} -- strand type
                pos {int} -- position on ref:strand
                count {int} -- occurrence count
                k {int} -- sequence length

        Keyword Arguments:
                replace {bool} -- whether to allow for replacement of non-zero
                                                  counts (default: {False})
        """
        self.check_length(k)

    def add_ref(self, ref, strand, size):
        """Add/resize reference:strand vector.

        Adds a new reference:strand vector of given size  if absent, or resizes
        the current one is size is greater than the current one.

        Arguments:
                ref {str} -- reference record name
                strand {str} -- strand type
                size {int} -- new size
        """
        pass

    def write_to(self, dirpath):
        """Write AbundanceVectors to a folder.

        The extension is removed from dirpath before proceeding.

        Arguments:
                dirpath {str} -- path to output directory.
        """
        pass


class AbundanceVector(AbundanceVectorBase):
    """AbundanceVector system.

    For each records, for each strand, generates a 1-dimensional array with
    abundance counts.

    Variables:
            __data {dict} -- stores abundance vectores
    """

    """{ref:{strand:np.ndarray}}"""
    __data: Dict[str, Dict[str, np.ndarray]] = {}

    def __init__(self):
        super().__init__()

    def add_count(self, ref, strand, pos, count, k, replace=False):
        """Add occurrence count to the vector.

        Arguments:
                ref {str} -- reference record name
                strand {str} -- strand type
                pos {int} -- position on ref:strand
                count {int} -- occurrence count
                k {int} -- sequence length

        Keyword Arguments:
                replace {bool} -- whether to allow for replacement of non-zero
                                                  counts (default: {False})
        """
        super().add_count(ref, strand, pos, count, k, replace)
        self.add_ref(ref, strand, pos + 1)
        if not replace:
            assert_msg = "cannot update a non-zero count without replace."
            assert_msg += " (%s, %s, %d, %d)" % (ref, strand, pos, count)
            assert self.__data[ref][strand][pos] == 0, assert_msg
        self.__data[ref][strand][pos] = count

    def add_ref(self, ref, strand, size):
        """Add/resize reference:strand vector.

        Adds a new reference:strand vector of given size  if absent, or resizes
        the current one is size is greater than the current one.

        Arguments:
                ref {str} -- reference record name
                strand {str} -- strand type
                size {int} -- new size
        """
        if ref not in self.__data.keys():
            self.__data[ref] = {}
        if strand not in self.__data[ref].keys():
            self.__data[ref][strand] = np.zeros(size)
        elif size > self.__data[ref][strand].shape[0]:
            self.__data[ref][strand].resize(size)

    def write_to(self, dirpath):
        """Write AbundanceVectors to a folder.

        The extension is removed from dirpath before proceeding.

        Arguments:
                dirpath {str} -- path to output directory.
        """
        dirpath = os.path.splitext(dirpath)[0]
        assert not os.path.isfile(dirpath)
        print('Writing output in "%s"' % dirpath)
        os.makedirs(dirpath, exist_ok=True)
        for ref in self.__data.keys():
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
        self.__tmpH = tempfile.TemporaryDirectory(prefix="kmanVector")
        self._tmp = self.__tmpH.name

    @property
    def tmp(self):
        return self._tmp

    def add_count(self, ref, strand, pos, count, k, replace=False):
        """Add occurrence count to the vector.

        Arguments:
                ref {str} -- reference record name
                strand {str} -- strand type
                pos {int} -- position on ref:strand
                count {int} -- occurrence count
                k {int} -- sequence length

        Keyword Arguments:
                replace {bool} -- whether to allow for replacement of non-zero
                                                  counts (default: {False})
        """
        super().add_count(ref, strand, pos, count, k, replace)
        self.add_ref(ref, strand, pos)
        with h5py.File(self.refpath(ref, strand)) as DH:
            if not replace:
                assert_msg = "cannot update a non-zero count without replace."
                assert_msg += " (%s, %s, %d, %d)" % (ref, strand, pos, count)
                assert DH["abundances"][pos] == 0, assert_msg
            DH["abundances"][pos] = count

    def add_ref(self, ref, strand, size):
        """Add/resize reference:strand vector.

        Adds a new reference:strand vector of given size  if absent, or resizes
        the current one is size is greater than the current one.

        Arguments:
                ref {str} -- reference record name
                strand {str} -- strand type
                size {int} -- new size
        """
        if not self.has_ref(ref, strand):
            self.mk_ref_file(ref, strand, size)
        else:
            with h5py.File(self.refpath(ref, strand)) as DH:
                if size + 1 > DH["abundances"].shape[0]:
                    DH["abundances"].resize((size + 1,))

    @staticmethod
    def refname(ref, strand) -> str:
        return "%s___%s.hdf5" % (ref, strand)

    def refpath(self, ref, strand):
        return os.path.join(self.tmp, self.refname(ref, strand))

    def has_ref(self, ref, strand):
        refname = self.refname(ref, strand)
        refpath = self.refpath(ref, strand)
        return os.path.isfile(refpath) and refname in self._dataList

    def mk_ref_file(self, ref, strand, size):
        if not self.has_ref(ref, strand):
            self._dataList.add(self.refname(ref, strand))
            with h5py.File(self.refpath(ref, strand)) as DH:
                data = DH.create_dataset(
                    "abundances", (size + 1,), dtype="i", maxshape=(None,), chunks=True
                )
                data[...] = np.zeros((size + 1,))

    def write_to(self, dirpath):
        """Write AbundanceVectors to a folder.

        The extension is removed from dirpath before proceeding.

        Arguments:
                dirpath {str} -- path to output directory.
        """
        dirpath = os.path.splitext(dirpath)[0]
        assert not os.path.isfile(dirpath)
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
