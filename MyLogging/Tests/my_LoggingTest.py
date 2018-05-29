import logging.config
import sys
from multiprocessing import Process
from random import choice

import buildLog as mlog
import eValuation as eVal
import logging_tree
from my_Loggin import ContextFilter, LogRecordSocketReceiver, LoggingContext

USERS = ['jim', 'fred', 'sheila']
IPS = ['123.231.231.123', '127.0.0.1', '192.168.0.1']
HOSTS = ['PC352', 'PC465', 'PC835']
logerlist = ['mainLog', 'secondaryLog', 'rotateLog', 'usersLog', 'watchedLog']
titlelist = ('mainLog', 'secondaryLog', 'rotateLog', 'usersLog', 'watchedLog')

levels = (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL)

mlp = mlog.MyloLogging()

f = ContextFilter(choice(USERS), choice(IPS), choice(HOSTS))

mlp.build_logging()
mlp.buildQueue()

## Uncomment to use single args
# mlp.loggerSet('mainLog', logging.INFO, 'my app', 'mainfilehand')
## Uncomment to use a list or dict
mlp.lopggerSetList(logerlist)

# uselogger = mlp.loggers['watchedLog']
# ad = CustomAdapter(uselogger, {'connid': 81})

# uselogger2 = mlp.loggers['rotateLog']
# stad = StyleAdapter(uselogger2)

mlp.startQueue()

print()
# lt =logging_tree.tree()
# print(lt)
logging_tree.printout(node=None)
print()

print('Starting TCP server...')
tcpserver = LogRecordSocketReceiver()
# lock = Lock()
tcpserve = Process(target=tcpserver.serve_until_stopped)
tcpserve.start()
# tcpserver.serve_forever()

mlp.loggers['mainLog'].debug('some debug message')
mlp.loggers['secondaryLog'].debug('some secondary debug massage')

# oldhandler = mlp.handlers['consolehand']
# newhandler = mlp.handlers['mainfilehand']
# mlp.loggers['mainLog'].removeHandler(oldhandler)
# mlp.loggers['mainLog'].addHandler(newhandler)
mlp.loggers['mainLog'].debug('some debug message')
mlp.loggers['mainLog'].info('some info message')
mlp.loggers['mainLog'].warning('some warn message')
mlp.loggers['mainLog'].error('some error message')
mlp.loggers['mainLog'].critical('some critical message')

# Test Logging Context
# set level high
mlp.loggers['mainLog'].setLevel(logging.ERROR)
mlp.loggers['mainLog'].debug('2. You should not see this message')

with LoggingContext(mlp.loggers['mainLog'], level=logging.DEBUG):
	mlp.loggers['mainLog'].debug('3. This should appear once on stderr.')
mlp.loggers['mainLog'].debug('4. This should not appear.')
h = logging.StreamHandler(sys.stdout)
with LoggingContext(mlp.loggers['mainLog'], level=logging.DEBUG, handler=h, close=True):
	mlp.loggers['mainLog'].debug('5. This should appear twice - once on stderr and once on stdout.')
mlp.loggers['mainLog'].info('6. This should appear just once on stderr.')
mlp.loggers['mainLog'].debug('7. This should not appear.')

##Reset Handlers
# mlp.loggers['mainLog'].removeHandler(newhandler)
# mlp.loggers['mainLog'].addHandler(oldhandler)

# newhandler = mlp.handlers['secondfilehand']
# mlp.loggers['secondaryLog'].addHandler(newhandler)
mlp.loggers['secondaryLog'].setLevel(logging.WARNING)
mlp.loggers['secondaryLog'].info('some secondary info')
# mlp.loggers['secondaryLog'].removeHandler(oldhandler)
mlp.loggers['secondaryLog'].warning('some secondary warning')
mlp.loggers['secondaryLog'].error('another secondary error message')

##Reset Handlers
# mlp.loggers['secondaryLog'].removeHandler(newhandler)

# newhandler = mlp.handlers['userfilehand']
# mlp.loggers['usersLog'].addHandler(newhandler)
mlp.loggers['usersLog'].setLevel(logging.DEBUG)
mlp.loggers['usersLog'].addFilter(f)

mlp.loggers['usersLog'].debug('a debug message with user info')

mlp.loggers['usersLog'].critical('another critical message with %s and user info', 'Using options')

for x in range(10):
	lvl = choice(levels)
	lvlname = logging.getLevelName(lvl)
	mlp.loggers['usersLog'].log(lvl, 'A message at %s level with %d %s', lvlname, 2, 'some parameters')

##Reset Handlers
# mlp.loggers['usersLog'].removeHandler(newhandler)

# newhandler = mlp.handlers['rotatehand']
# mlp.loggers['rotateLog'].addHandler(newhandler)
mlp.loggers['rotateLog'].critical('Look Out!!!!')

# mlp.loggers['rotateLog'].removeHandler(newhandler)

# newhandler = mlp.handlers['watchFile']
# mlp.loggers['watchedLog'].addHandler(newhandler)
mlp.loggers['watchedLog'].critical('It is All Bad!!!')

##Reset All Handlers
# mlp.loggers['watchedLog'].removeHandler(newhandler)
# mlp.loggers['watchedLog'].addHandler(oldhandler)

# mlp.loggers['watchedLog'].removeHandler(oldhandler)
# newhandler = mlp.handlers['sockethand']
# mlp.loggers['watchedLog'].addHandler(newhandler)

for x in range(10):
	lvl = choice(levels)
	lvlname = logging.getLevelName(lvl)
	mlp.loggers['watchedLog'].log(lvl, 'A message at %s level with %d %s', lvlname, 2, 'parameters')

# myls = mlog.Log_Server()
# myls.start_log_server(8080)

# myls.stop_log_server()
print('stopping que')
mlp.stopQueue()
print('Main Test Done!')

context = dict(vars(logging))
context['handlers'] = mlp.handlers
evaluator = eVal.Evaluator(context, True)
while True:
	line = input('Enter source to evaluate or enter to exit:').strip()
	if not line:
		break
	try:
		result = evaluator.evaluate(line.strip(), '<interactive>')
		print(result)
	except eVal.EvaluationError as e:
		print(e)

tcpserve.terminate()
print('Log Processing Test Complete!')
exit(0)
