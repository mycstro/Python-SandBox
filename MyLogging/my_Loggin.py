import logging
import logging.config
import logging.handlers
import multiprocessing
import pickle
import socketserver
import struct
from multiprocessing import Process

try:
	import Queue as queue
except ImportError:
	import queue


class CustomQueueHandler(logging.Handler):
	"""
	This handler sends events to a queue. Typically, it would be used together
	with a multiprocessing Queue to centralise logging to file in one process
	(in a multi-process application), so as to avoid file write contention
	between processes.
	"""

	def __init__(self, queue):
		"""
		Initialise an instance, using the passed queue.
		"""
		logging.Handler.__init__(self)
		self.queue = queue

	def enqueue(self, record):
		"""
		Enqueue a record.
		The base implementation uses put_nowait. You may want to override
		this method if you want to use blocking, timeouts or custom queue
		implementations.
		"""
		self.queue.put_nowait(record)

	def prepare(self, record):
		"""
		Prepares a record for queuing. The object returned by this method is
		enqueued.
		The base implementation formats the record to merge the message
		and arguments, and removes unpickleable items from the record
		in-place.
		You might want to override this method if you want to convert
		the record to a dict or JSON string, or send a modified copy
		of the record while leaving the original intact.
		"""
		# The format operation gets traceback text into record.exc_text
		# (if there's exception data), and also puts the message into
		# record.message. We can then use this to replace the original
		# msg + args, as these might be unpickleable. We also zap the
		# exc_info attribute, as it's no longer needed and, if not None,
		# will typically not be pickleable.
		self.format(record)
		record.msg = record.message
		record.args = None
		record.exc_info = None
		return record

	def emit(self, record):
		"""
		Emit a record.
		Writes the LogRecord to the queue, preparing it for pickling first.
		"""
		try:
			self.enqueue(self.prepare(record))
		except (KeyboardInterrupt, SystemExit):
			raise
		except:
			self.handleError(record)


class CustomQueueListener(logging.handlers.QueueListener):
	"""
	This class implements an internal threaded listener which watches for
	LogRecords being added to a queue, removes them and passes them to a
	list of handlers for processing.
	"""

	_sentinel = None

	def __init__(self, queue, *handlers):
		super(CustomQueueListener, self).__init__(queue, *handlers)
		"""
		Initialise an instance with the specified queue and
		handlers.
		"""
		# Changing this to a list from tuple in the parent class
		self.queue = queue
		# self.handlers = handlers
		# self._stop = threading.Event()
		# self._thread = None

		self.handlers = list(handlers)
		self._stop = multiprocessing.Event()
		self._process = None

	# def dequeue(self, block):
	# 	"""
	# 	Dequeue a record and return it, optionally blocking.
	# 	The base implementation uses get. You may want to override this method
	# 	if you want to use timeouts or work with custom queue implementations.
	# 	"""
	# 	return self.queue.get(block)

	def start(self):
		"""
		Start the listener.
		This starts up a background thread to monitor the queue for
		LogRecords to process.
		"""
		# self._thread = t = threading.Thread(target=self._monitor)
		# t.setDaemon(True)
		# t.start()

		self._process = sps = Process(target=self._monitor, name='que_monitor')
		sps.daemon = True
		sps.start()

	def prepare(self, record):
		"""
		Prepare a record for handling.
		This method just returns the passed-in record. You may want to
		override this method if you need to do any custom marshalling or
		manipulation of the record before passing it to the handlers.
		"""

		return record

	def handle(self, record):
		"""
		Override handle a record.

		This just loops through the handlers offering them the record
		to handle.

		:param record: The record to handle.
		"""
		record = self.prepare(record)
		for handler in self.handlers:
			if record.levelno >= handler.level:  # This check is not in the parent class
				handler.handle(record)

	def addHandler(self, hdlr):
		"""
		Add the specified handler to this logger.
		"""
		if not (hdlr in self.handlers):
			self.handlers.append(hdlr)

	def removeHandler(self, hdlr):
		"""
		Remove the specified handler from this logger.
		"""
		if hdlr in self.handlers:
			hdlr.close()
			self.handlers.remove(hdlr)

	def _monitor(self):
		"""
		Monitor the queue for records, and ask the handler
		to deal with them.
		This method runs on a separate, internal thread.
		The thread will terminate if it sees a sentinel object in the queue.
		"""
		q = self.queue
		has_task_done = hasattr(q, 'task_done')
		while not self._stop.is_set():
			try:
				record = self.dequeue(True)
				if record is self._sentinel:
					break
				self.handle(record)
				if has_task_done:
					q.task_done()
			except queue.Empty:
				pass
		# There might still be records in the queue.
		while True:
			try:
				record = self.dequeue(False)
				if record is self._sentinel:
					break
				self.handle(record)
				if has_task_done:
					q.task_done()
			except queue.Empty:
				break

	def stop(self):
		"""
		Stop the listener.
		This asks the thread to terminate, and then waits for it to do so.
		Note that if you don't call this before your application exits, there
		may be some records still left on the queue, which won't be processed.
		"""
		self._stop.set()
		self.queue.put_nowait(self._sentinel)
		# self._thread.join()
		# self._thread = None
		self._process.terminate()
		self._process = None


class LogRecordTCPHandler(socketserver.BaseRequestHandler):
	"""
	The request handler class for our server.

	It is instantiated once per connection to the server, and must
	override the handle() method to implement communication to the
	client.
	"""

	def handle(self):
		# self.request is the TCP socket connected to the client
		self.data = self.request.recv(1024).strip()
		print("{} wrote:".format(self.client_address[0]))
		print(self.data)
		# just send back the same data, but upper-cased
		self.request.sendall(self.data.upper())


class LogRecordThreadingTCPHandler(socketserver.StreamRequestHandler):

	def handle(self):
		# self.rfile is a file-like object created by the handler;
		# we can now use e.g. readline() instead of raw recv() calls
		self.data = self.rfile.readline().strip()
		print("{} wrote:".format(self.client_address[0]))
		print(self.data)
		# Likewise, self.wfile is a file-like object used to write back
		# to the client
		self.wfile.write(self.data.upper())


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
	# Handler for a streaming logging request.
	def handle(self):
		# Handle multiple requests - each expected to be a 4-byte length,
		# followed by the LogRecord in pickle format.
		while True:
			chunk = self.connection.recv(4)
			if len(chunk) < 4:
				break
			slen = struct.unpack('>L', chunk)[0]
			chunk = self.connection.recv(slen)
			while len(chunk) < slen:
				chunk = chunk + self.connection.recv(slen - len(chunk))
				obj = self.unPickle(chunk)
				record = logging.makeLogRecord(obj)
				self.handleLogRecord(record)

	def unPickle(self, data):
		return pickle.loads(data)

	def handleLogRecord(self, record):
		if self.server.logname is not None:
			name = self.server.logname
		else:
			name = record.name
		logger = logging.getLogger(name)
		logger.handle(record)


class SyslogBOMFormatter(logging.Formatter):
	def format(self, record):
		result = super().format(record)
		return result


class OneLineExceptionFormatter(logging.Formatter):
	def formatException(self, exc_info):
		result = super().formatException(exc_info)
		return repr(result)

	def format(self, record):
		result = super().format(record)
		if record.exc_text:
			result = result.replace("\n", "")
		return result


class ContextFilter(logging.Filter):

	def __init__(self, userslist, ipslist, hostslist):
		logging.Filter.__init__(self)
		self.users = userslist
		self.ips = ipslist
		self.hosts = hostslist

	def filter(self, record):
		record.ip = self.ips
		record.user = self.users
		record.host = self.hosts
		return True, record.user, record.ip, record.host


class LoggingContext(object):
	def __init__(self, logger, level=None, handler=None, close=True):
		self.logger = logger
		self.level = level
		self.handler = handler
		self.close = close

	def __enter__(self):
		if self.level is not None:
			self.old_level = self.logger.level
			self.logger.setLevel(self.level)
		if self.handler:
			self.logger.addHandler(self.handler)

	def __exit__(self, et, ev, tb):
		if self.level is not None:
			self.logger.setLevel(self.old_level)
		if self.handler:
			self.logger.removeHandler(self.handler)
		if self.handler and self.close:
			self.handler.close()


class Log_Server():
	def start_log_server(self, port):
		# read initial config file
		# logging.config.fileConfig('logging.conf')
		# create and start listener on port
		print('Log Server Started')
		self.t = logging.config.listen(port)
		self.t.start()
		logger = logging.getLogger('log server log')

	def stop_log_server(self):
		# cleanup
		print('Log Server Stopped')
		logging.config.stopListening()
		self.t.join()


class Message(object):
	def __init__(self, fmt, args):
		self.fmt = fmt
		self.args = args

	def __str__(self):
		return self.fmt.format(*self.args)


class StyleAdapter(logging.LoggerAdapter):
	def __init__(self, logger, extra=None):
		super(StyleAdapter, self).__init__(logger, extra or {})

	def log(self, level, msg, *args, **kwargs):
		if self.isEnabledFor(level):
			msg, kwargs = self.process(msg, kwargs)
			self.logger._log(level, Message(msg, args), (), **kwargs)


class CustomAdapter(logging.LoggerAdapter):
	def process(self, msg, kwargs):
		return '[%s] %s' % (self.extra['connid'], msg), kwargs


class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
	# Simple TCP socket-based logging receiver.

	allow_reuse_address = True
	timeout = 1

	def __init__(self, host='localhost', port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
	             handler=LogRecordStreamHandler, timeout=1):
		self.abort = 0
		self.timeout = timeout
		self.logname = None

		try:
			socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)

		except OSError:
			nport = 9010
			socketserver.ThreadingTCPServer.__init__(self, (host, nport), handler)

	def serve_until_stopped(self):
		try:
			import select
			abort = 0
			while not abort:
				rd, wr, ex = select.select([self.socket.fileno()],
				                           [], [],
				                           self.timeout)
				if rd:
					logging.warning("Found request, now handling")
					self.handle_request()
				logging.warning("No request, continuing to listen for request....")
				abort = self.abort
			else:
				self.abort = + 1
				abort = self.abort
		except KeyboardInterrupt:
			exit(0)


class setListeningPort():
	def __init__(self, port):
		lp = logging.config.listen(port)
		lp.start()

