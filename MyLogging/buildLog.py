import logging
import logging.config
import logging.handlers
import os
from logging.config import dictConfig, fileConfig

import my_Loggin as mylog

try:
	import Queue as queue
except ImportError:
	import queue


class MyloLogging:

	def __init__(self):
		# print("Logging tree at init")
		# logging_tree.printout(node=None)
		# logging.info("Loading basic configuration")
		logging.basicConfig(level=logging.DEBUG,
		                    format='%(asctime)-15s %(processName)-10s %(threadName)s %(name)s %(levelname)-8s %(message)s',
		                    datefmt='%m-%d %H:%M',
		                    filename='/var/log/mylo/temp.log',
		                    filemode='w')
		logging.info("Setting queue size to no limit")
		self.que = queue.Queue(-1)  # no limit on size
		logging.info("Compiling list")
		self.loggers = {}
		self.handlers = {}
		self.formatters = {}
		self.listeners = {}
		self.titles = {}

		self.myloging_dict = dict(
			version=1,
			disable_existing_loggers=True,
			loggers={
				'logger': {'handlers': [''],
				           'level'   : '', }
			},
			formatters={},
			handlers={},
			listeners={},
			filters={},
			root={},
		)

	def build_from_ini(self, iniFile):
		fileConfig(iniFile)

	def build_from_dict(self, configDict='default'):
		if configDict == 'default':
			configDict = self.myloging_dict
		dictConfig(configDict)

	def buildQueue(self):
		que = queue.Queue(-1)  # no limit on size
		self.quehand = mylog.CustomQueueHandler(que)
		addHandl = self.handlers
		nam1 = 'listener'
		num1 = 0
		for items in addHandl.items():
			num1 += 1
			listname = nam1 + str(num1)
			self.listeners[listname] = mylog.CustomQueueListener(que, items)
		self.handlers['quehand'] = self.quehand

	def startQueue(self):
		listenerslist = self.listeners
		for items in listenerslist:
			self.listeners[items].start()

	def stopQueue(self):
		listenerslist = self.listeners
		for items in listenerslist:
			self.listeners[items].stop()

	def loggerSetExtra(self, logname, lvl, handle='quehand'):
		slgll = self.loggers[logname]
		slgll.propagate = True
		logging.info("Setting Level {} to Logger {}".format(lvl, logname))
		slgll.setLevel(lvl)
		logging.info("Setting Handler {} to Logger {}".format(handle, logname))
		slgch = self.handlers[handle]
		slgll.addHandler(slgch)

	def loggerSetList(self, logname, lvls=logging.DEBUG, titles="None", handlez="consolehand"):
		for (logn, titl) in zip(logname, titles):
			logging.info("Gathering Loggers and Titles")
			if titles == "None":
				lognamelist = logn
				defaulttitle = "My_Logging"
				logging.info("No Title Provided, \nSetting title to {}".format(defaulttitle))
				logging.info("\nCreating Logger {} with propagation".format(lognamelist))
				self.loggers[lognamelist] = logging.getLogger(defaulttitle)
				self.loggerSetExtra(lognamelist, lvls, handlez)
			elif titles != "None":
				lognamelist = logn
				titlelistz = titl
				logging.info("String Provided. Title is: {}".format(titlelistz))
				logging.info("\nCreating Logger {} with propagation".format(lognamelist))
				self.loggers[lognamelist] = logging.getLogger(titlelistz)
				self.loggerSetExtra(lognamelist, lvls, handlez)

	def build_logging(self):
		# create formatters
		sfsbf = self.formatters['BOM'] = mylog.SyslogBOMFormatter(logging.BASIC_FORMAT)
		sfplf = self.formatters['Process'] = logging.Formatter(
			'%(asctime)s %(process)s %(processName)-10s \n%(threadName)s %(name)s %(levelname)-8s \n%(message)s')
		sftlf = self.formatters['Thread'] = logging.Formatter('%(thread)d %(threadName)s: %(asctime)s - %(message)s')
		sfslf = self.formatters['Simple'] = logging.Formatter('%(asctime)s - %(name)-12s: %(levelname)-8s %(message)s')
		sfvlf = self.formatters['Verbose'] = logging.Formatter(
			'%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
		sfuilf = self.formatters['User_Info'] = logging.Formatter(
			'%(asctime)-15s %(name)-5s %(levelname)-8s HOST: %(host)s IP: %(ip)-15s User: %(user)-8s %(message)s')

		# create SysLog Handler
		try:
			shslh = self.handlers['systLog'] = logging.handlers.SysLogHandler(address='/dev/log')
			shslh.setLevel(os.environ.get("LOGLEVEL", "INFO"))
		except AttributeError:
			shslh = self.handlers['systLog'] = logging.handlers.SysLogHandler(
				facility=logging.handlers.SysLogHandler.LOG_DAEMON)
			shslh.setLevel(os.environ.get("LOGLEVEL", "INFO"))
		### add formatter to Syslog Handler
		shslh.setFormatter(sfsbf)

		# create console handler with a higher log level
		shcsh = self.handlers['consolehand'] = logging.StreamHandler()
		### add formatter to console
		shcsh.setFormatter(sftlf)

		# crate Watched File Handler
		shwfh = self.handlers['watchFile'] = logging.handlers.WatchedFileHandler(
			os.environ.get("LOGFILE", 'watchedLog.log'))
		shwfh.setLevel(os.environ.get("LOGLEVEL", "DEBUG"))
		### add formatter to File Watcher Handler
		shwfh.setFormatter(sfvlf)

		# create Socket Handler
		self.handlers['sockethand'] = logging.handlers.SocketHandler('localhost',
		                                                             logging.handlers.DEFAULT_TCP_LOGGING_PORT)

		# create Rotational File Handler
		shrfh = self.handlers['rotatehand'] = logging.handlers.RotatingFileHandler('rotate.log', 'a', 500, 5)
		shrfh.setLevel(logging.INFO)
		### add formatter to Rotational File Handler
		shrfh.setFormatter(sfvlf)

		# create Main File Handler
		shmfh = self.handlers['mainfilehand'] = logging.FileHandler('main.log')
		### add formatter to Main File Handler
		shmfh.setFormatter(sfslf)

		# create Secondary File Handler
		shsfh = self.handlers['secondfilehand'] = logging.FileHandler('secondary.log')
		### add formatter to Second File Handler
		shsfh.setFormatter(sfplf)

		# create User File Handler
		shufh = self.handlers['userfilehand'] = logging.FileHandler('users.log')
		shufh.setLevel(logging.DEBUG)
		### add formatter to User File Handler
		shufh.setFormatter(sfuilf)
