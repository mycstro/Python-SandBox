import ast


class EvaluationError(ValueError):
	pass


class Evaluator(object):
	builtin_names = {
		'None' : None,
		'False': False,
		'True' : True,
	}

	operators = {
		'add'     : lambda x, y: x + y,
		'bitand'  : lambda x, y: x & y,
		'bitor'   : lambda x, y: x | y,
		'bitxor'  : lambda x, y: x ^ y,
		'div'     : lambda x, y: x / y,
		'eq'      : lambda x, y: x == y,
		'floordiv': lambda x, y: x // y,
		'gt'      : lambda x, y: x > y,
		'gte'     : lambda x, y: x >= y,
		'in'      : lambda x, y: x in y,
		'invert'  : lambda x: ~x,
		'lshift'  : lambda x, y: x << y,
		'lt'      : lambda x, y: x < y,
		'lte'     : lambda x, y: x <= y,
		'mod'     : lambda x, y: x % y,
		'mult'    : lambda x, y: x * y,
		'not'     : lambda x: not x,
		'noteq'   : lambda x, y: x != y,
		'notin'   : lambda x, y: x not in y,
		'pow'     : lambda x, y: x ** y,
		'rshift'  : lambda x, y: x >> y,
		'sub'     : lambda x, y: x - y,
		'uadd'    : lambda x: +x,
		'usub'    : lambda x: -x,
	}

	handlers = {}

	def __init__(self, context=None, allow_imports=False):
		self.context = context or {}
		self.source = None
		self.allow_imports = allow_imports

	def get_fragment(self, offset):
		fragment_len = 10
		s = 'at position %d: %r' % (offset, self.source[offset:offset + fragment_len])
		if offset + fragment_len < len(self.source):
			s += '...'
		return s

	def evaluate(self, node, filename=None):
		if isinstance(node, str):
			self.source = node
			kwargs = dict(mode='eval')
			if filename:
				kwargs['filename'] = filename
			try:
				node = ast.parse(node, **kwargs)
			except SyntaxError as e:
				s = self.get_fragment(e.offset)
				raise EvaluationError('syntax error %s' % s)
		node_type = node.__class__.__name__.lower()
		if node_type in self.handlers:
			handler = self.handlers[node_type]
		else:
			handler = getattr(self, 'do_%s' % node_type, None)
		if handler is None:
			if self.source is None:
				s = '(source not available)'
			else:
				s = self.get_fragment(node.col_offset)
			raise EvaluationError("don't know how to evaluate %r %s" % (
				node_type, s))
		return handler(node)

	def do_attribute(self, node):
		print(node)
		container = self.evaluate(node.value)
		print(container)
		return getattr(container, node.attr)

	def do_binop(self, node):
		op = node.op.__class__.__name__.lower()
		if op not in self.operators:
			raise EvaluationError('unsupported operation: %r' % op)
		lhs = self.evaluate(node.left)
		rhs = self.evaluate(node.right)
		return self.operators[op](lhs, rhs)

	def do_boolop(self, node):
		result = self.evaluate(node.values[0])
		is_or = node.op.__class__ is ast.Or
		is_and = node.op.__class__ is ast.And
		assert is_or or is_and
		if (is_and and result) or (is_or and not result):
			for n in node.values[1:]:
				result = self.evaluate(n)
				if (is_or and result) or (is_and and not result):
					break
		return result

	def do_compare(self, node):
		lhs = self.evaluate(node.left)
		result = True
		for op, right in zip(node.ops, node.comparators):
			op = op.__class__.__name__.lower()
			if op not in self.operators:
				raise EvaluationError('unsupported operation: %r' % op)
			rhs = self.evaluate(right)
			result = self.operators[op](lhs, rhs)
			if not result:
				break
			lhs = rhs
		return result

	def do_dict(self, node):
		e = self.evaluate
		return dict((e(k), e(v)) for k, v in zip(node.keys, node.values))

	def do_ellipsis(self, node):
		return Ellipsis

	def do_expr(self, node):
		return self.evaluate(node.value)

	do_index = do_expr

	def do_expression(self, node):
		return self.evaluate(node.body)

	def do_extslice(self, node):
		e = self.evaluate
		return tuple((e(n) for n in node.dims))

	def do_list(self, node):
		return list([self.evaluate(n) for n in node.elts])

	def do_name(self, node):
		if node.id in self.builtin_names:
			result = self.builtin_names[node.id]
		elif node.id in self.context:
			result = self.context[node.id]
		else:
			if not self.allow_imports:
				raise EvaluationError('unknown name: %r' % node.id)
			try:
				result = __import__(node.id)
			except ImportError:
				raise EvaluationError('unknown name: %r' % node.id)
		return result

	def do_num(self, node):
		return node.n

	def do_slice(self, node):
		if node.lower is None:
			lower = None
		else:
			lower = self.evaluate(node.lower)
		if node.upper is None:
			upper = None
		else:
			upper = self.evaluate(node.upper)
		if node.step is None:
			step = None
		else:
			step = self.evaluate(node.step)
		return slice(lower, upper, step)

	def do_str(self, node):
		return node.s

	def do_subscript(self, node):
		assert node.ctx.__class__ is ast.Load
		val = self.evaluate(node.value)
		if not isinstance(node.slice, (ast.Index, ast.Slice, ast.Ellipsis,
		                               ast.ExtSlice)):
			raise EvaluationError('Unable to get subscript: %r',
			                      node.slice.__class__.__name__)
		indices = self.evaluate(node.slice)
		if isinstance(node.slice, ast.ExtSlice):
			result = val[(indices)]
		else:
			result = val.__getitem__(indices)
		return result

	def do_tuple(self, node):
		return tuple([self.evaluate(n) for n in node.elts])

	def do_unaryop(self, node):
		op = node.op.__class__.__name__.lower()
		operand = self.evaluate(node.operand)
		if op not in self.operators:
			raise EvaluationError('unsupported operation: %r' % op)
		return self.operators[op](operand)
