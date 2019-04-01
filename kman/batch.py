
'''
@author: Gabriele Girelli
@contact: gigi.ga90@gmail.com
@description: methods for batching
'''

from Bio.SeqIO.FastaIO import SimpleFastaParser
from enum import Enum
from ggc.args import check_threads
from kman.seq import KMer, Sequence
from joblib import Parallel, delayed
import oligo_melting as om
import os
import tempfile
import time
from tqdm import tqdm

class BatcherBase(object):
	"""docstring for Batcher"""

	DEFAULT_BATCH_SIZE = int(1e6)
	DEFAULT_BATCH_TYPE = KMer
	DEFAULT_NATYPE = om.NATYPES.DNA

	_tmp = None
	_batches = None
	__size = DEFAULT_BATCH_SIZE
	_type = DEFAULT_BATCH_TYPE
	__natype = DEFAULT_NATYPE

	def __init__(self, size = None):
		"""Initializes BatcherBase.
		
		Keyword Arguments:
			size {int} -- batching size (default: {None})
		"""
		super().__init__()
		if type(None) != type(size):
			assert size >= 1
			self.__size = int(size)
		if type(None) == type(self._batches):
			self._batches = [Batch(self)]

	@property
	def size(self):
		return self.__size
	@property
	def type(self):
		return self._type
	@property
	def natype(self):
		return self.__natype
	@property
	def collection(self):
		return self._batches
	@property
	def tmp(self):
		if type(None) == type(self._tmp):
			self._tmp = tempfile.TemporaryDirectory(prefix = "kmanBatch")
		return self._tmp

	def new_batch(self):
		"""Add a new empty batch to the current collection."""
		if self.collection[-1].is_full():
			self.collection[-1].write()
			self._batches.append(Batch(self))

	def add_record(self, record):
		"""Add a record to the currentcollection.
		
		The record is added to the last empty batch in the collection. If no
		empty batches are left, a new empty batch is added.
		
		Arguments:
			record
		"""
		self.new_batch() # Add new batch if needed
		self.collection[-1].add(record)

class BatcherThreading(BatcherBase):
	"""docstring for BatcherThreading"""

	class FEED_MODES(Enum):
		"""Feeding modes.
		
		Used with feed_collection() method.
		
		Extends:
			Enum
		
		Variables:
			REPLACE {number} -- replace current collection.
			FLOW {number} -- flow records into current collection.
			APPEND {number} -- append to current collection.
		"""
		REPLACE = 1
		FLOW = 2
		APPEND = 3

	__threads = 1

	def __init__(self, threads = 1, size = None):
		"""Initialize BatcherThreading.
		
		Keyword Arguments:
			threads {number} -- number of threads for parallelization
			                    (default: {1})
			size {int} -- batching size (default: {None})
		"""
		super().__init__(size)
		self.threads = threads

	@property
	def threads(self):
		return self.__threads
	@threads.setter
	def threads(self, t):
		self.__threads = check_threads(t)

	def feed_collection(self, new_collection, mode = FEED_MODES.FLOW):
		"""Feed new batch collection to the current one.
		
		Different modes of feeding are available, see documentation of
		BatcherThreading.FEED_MODES for more details.
		
		Arguments:
			new_collection {list} -- list of Batches
		
		Keyword Arguments:
			mode {BatcherThreading.FEED_MODES} -- (default: {FEED_MODES.FLOW})
		"""
		assert all([b.type == self.type for b in new_collection])
		if mode == self.FEED_MODES.REPLACE:
			self._batches = new_collection
		elif mode == self.FEED_MODES.FLOW:
			for bi in tqdm(range(len(new_collection))):
				batch = new_collection.pop()
				for record in batch.record_gen():
					self.add_record(record)
				batch.reset()
		elif mode == self.FEED_MODES.APPEND:
			self._batches.extend(new_collection)

class FastaBatcher(BatcherThreading):
	"""docstring for FastaBatcher"""

	def __init__(self, threads = 1, size = None):
		"""Initialize FastaBatcher instance.
		
		A parent batcher class can be specified, whose attributes are inherited.
		
		Keyword Arguments:
			threads {int} -- number of threads for parallelization
			                 (overridden by parent.threads)
			size {int} -- batch size (overridden by parent.size)
		"""
		super().__init__(threads, size)

	def do(self, fasta, k):
		"""Start batching the fasta file.
		
		Batches a fasta file up to the specified number (self.size) of k-mers.
		
		Arguments:
			fasta {string} -- path to fasta file
			k {int} -- length of k-mers
		"""
		assert os.path.isfile(fasta)
		assert k > 1

		batcher = FastaRecordBatcher(parent = self)
		with open(fasta, "r+") as FH:
			for record in SimpleFastaParser(FH):
				batcher.do(record, k)
				self.feed_collection(batcher.collection, self.FEED_MODES.APPEND)

class FastaRecordBatcher(BatcherThreading):
	"""docstring for FastaRecordBatcher"""


	def __init__(self, threads = 1, size = None, parent = None):
		"""Initialize FastaRecordBatcher instance.
		
		A parent batcher class can be specified, whose attributes are inherited.
		
		Keyword Arguments:
			threads {int} -- number of threads for parallelization
			                 (overridden by parent.threads)
			size {int} -- batch size (overridden by parent.size)
			parent {Batcher} -- parent batcher to inherit attributes from
			                    (default: {None})
		"""
		if type(None) != type(parent):
			self.__size = parent.size
			size = parent.size
			self.threads = parent.threads
			threads = parent.threads
			self.__natype = parent.natype
			self._batches = parent.collection
			self._tmp = parent.tmp
		super().__init__(threads, size)

	def do(self, record, k):
		"""Start batching a fasta record.
		
		Requires a fasta record with header and sequence.
		
		Arguments:
			record {tuple} -- (header, sequence)
			k {int} -- length of k-mers
		"""
		record_name = record[0].split(" ")[0]
		if 1 == self.threads:
			kmerGen = Sequence.kmerator(record[1], k, self.natype, record_name)
			for kmer in tqdm(kmerGen):
				if kmer.is_ab_checked():
					self.add_record(kmer)
		else:
			batches = Parallel(n_jobs = self.threads, verbose = 11
				)(delayed(FastaRecordBatcher.build_batch
					)(seq, record_name, k, self, i)
					for (seq, i) in Sequence.batcher(record[1], k, self.size))
			self.feed_collection(batches, self.FEED_MODES.REPLACE)

	@staticmethod
	def build_batch(seq, name, k, batcher, i = 0):
		"""Builds a Batch.
		
		Arguments:
			seq {string} -- sequence
			name {string} -- header
			k {int} -- k for k-mering
			batcher {BatcherBase} -- parent
		
		Keyword Arguments:
			i {number} -- position offset (default: {0})
		
		Returns:
			Batch
		"""
		batch = Batch(batcher)
		recordGen = Sequence.kmerator(seq, k, batcher.natype, name, i)
		batch.add_all((k for k in recordGen if k.is_ab_checked()))
		batch.write(doSort = True)
		return batch

class Batch(object):
	"""docstring for Batch"""
	
	__written = False
	__i = 0
	__tmp_dir = None
	__tmp = None
	suffix = ".fa"

	def __init__(self, batcher, size = 1):
		"""Initialize a Batch.
		
		Uses the parent Batcher to set default values.
		
		Arguments:
			batcher {BatcherBase} -- parent batcher.
		"""
		super().__init__()
		assert batcher.size >= 1
		self.__size = max(int(batcher.size), size)
		self.__remaining = self.__size
		self.__records = [None] * self.__size
		self.__type = batcher.type
		self.__tmp_dir = batcher.tmp.name

	@property
	def is_written(self):
		return self.__written
	@property
	def current_size(self):
		return self.__i
	@property
	def size(self):
		return self.__size
	@property
	def remaining(self):
		return self.__remaining
	@property
	def type(self):
		return self.__type
	@property
	def tmp(self):
		if type(None) == type(self.__tmp):
			with tempfile.NamedTemporaryFile(mode = "w+",
				dir = self.__tmp_dir,
				prefix = str(hash(time.time())),
				suffix = self.suffix) as TH:
				self.__tmp = TH.name
		return self.__tmp
	@property
	def info(self):
		"""Prints Batch information in a readable format."""
		info = "%s\ntype: %s\nsize: %d" % (self.tmp, self.type, self.size)
		info += "\ni: %d\nremaining: %d" %(self.current_size, self.remaining)
		info += "\nwritten: %r\n" % self.is_written
		return info

	@property
	def sorted(self, keyAttr = "seq"):
		"""Generator of sorted records.
		
		Keyword Arguments:
			keyAttr {str} -- attribute key for sorting (default: {"seq"})
		
		Returns:
			generator
		"""
		return sorted(self.record_gen(), key = lambda x: getattr(x, keyAttr))

	def record_gen(self):
		"""Generator of records.
		
		Yields:
			record
		"""
		if self.is_written:
			with open(self.tmp, "r+") as TH:
				for record in SimpleFastaParser(TH):
					yield KMer.from_fasta(record)
		else:
			for record in self.__records:
				if not type(None) == type(record):
					yield record

	def add(self, record):
		"""Add a record to the current batch.
		
		Does not work if the batch is full. Also, the record type must match the
		batch type.
		
		Arguments:
			record -- record of the same type as self.type
		"""
		assert not self.is_written, "this batch has been stored locally."
		assert not self.is_full(), "this batch is full."
		assert type(record) == self.type, "record must be %s, not %s." % (
			self.type, type(record))
		self.__records[self.__i] = record
		self.__i += 1
		self.__remaining -= 1

	def add_all(self, recordGen):
		"""Adds all records from a generator to the current Batch.
		
		Arguments:
			recordGen {generator} -- record generator
		"""
		for record in recordGen:
			self.add(record)

	def to_write(self, f = "as_fasta", doSort = False):
		"""Generator of writeable records.
		
		Generator function that converts batch records into writeable ones.
		
		Keyword Arguments:
			f {str} -- name of record in-built function for writeable format]
			           (default: {"as_fasta"})
		"""
		if doSort:
			return (getattr(r, f)() for r in self.sorted
				if not type(None) == type(r))
		else:
			return (getattr(r, f)() for r in self.record_gen()
				if not type(None) == type(r))

	def write(self, f = "as_fasta", doSort = False):
		"""Writes the batch to file.
		
		Keyword Arguments:
			f {str} -- name of method in records class for string-like
			           representation (default: {"as_fasta"})
			doSort {bool} -- whether to sort when writing (default: {False})
		"""
		with open(self.tmp, "w+") as TH:
			TH.write("".join(self.to_write(f, doSort)))
		self.__records = None
		self.__written = True

	def reset(self):
		"""Reset the batch.
		
		Empties current records collection and any written file.
		"""
		os.remove(self.tmp)
		self.__written = False
		self.__i = 0
		self.__remaining = self.size
		self.__records = [None] * self.__size

	def is_full(self):
		"""Whether the Batch collection is full.
		"""
		return 0 == self.remaining
