# This is a Python implementation of the following jsonLogic JS library:
# https://github.com/jwadhams/json-logic-js
from __future__ import unicode_literals

import sys
from six.moves import reduce
import logging

logger = logging.getLogger(__name__)

try:
    unicode
except NameError:
    pass
else:
    # Python 2 fallback.
    str = unicode


def if_(*args):
    """Implements the 'if' operator with support for multiple elseif-s."""
    for i in range(0, len(args) - 1, 2):
        if args[i]:
            return args[i + 1]
    if len(args) % 2:
        return args[-1]
    else:
        return None


def soft_equals(a, b):
    """Implements the '==' operator, which does type JS-style coertion."""
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) is bool(b)
    return a == b


def hard_equals(a, b):
    """Implements the '===' operator."""
    if type(a) != type(b):
        return False
    return a == b


def less(a, b, *args):
    """Implements the '<' operator with JS-style type coertion."""
    types = set([type(a), type(b)])
    if float in types or int in types:
        try:
            a, b = float(a), float(b)
        except TypeError:
            # NaN
            return False
    return a < b and (not args or less(b, *args))

def less_or_equal(a, b, *args):
    """Implements the '<=' operator with JS-style type coertion."""
    return (
        less(a, b) or soft_equals(a, b)
    ) and (not args or less_or_equal(b, *args))


def to_numeric(arg):
    """
    Converts a string either to int or to float.
    This is important, because e.g. {"!==": [{"+": "0"}, 0.0]}
    """
    if isinstance(arg, str):
        if '.' in arg:
            return float(arg)
        else:
            return int(arg)
    return arg

def plus(*args):
    """Sum converts either to ints or to floats."""
    return sum(to_numeric(arg) for arg in args)


def minus(*args):
    """Also, converts either to ints or to floats."""
    if len(args) == 1:
        return -to_numeric(args[0])
    return to_numeric(args[0]) - to_numeric(args[1])


def merge(*args):
    """Implements the 'merge' operator for merging lists."""
    ret = []
    for arg in args:
        if isinstance(arg, list) or isinstance(arg, tuple):
            ret += list(arg)
        else:
            ret.append(arg)
    return ret


def get_var(data, var_name=None, not_found=None):
    """Gets variable value from data dictionary."""
    try:
        if var_name is None or len(var_name) == 0:
            return 1
    except TypeError:
        pass
    try:
        for key in str(var_name).split('.'):
            try:
                data = data[key]
            except TypeError:
                data = data[int(key)]
    except (KeyError, TypeError, ValueError):
        return not_found
    else:
        return data


def missing(data, *args):
    """Implements the missing operator for finding missing variables."""
    not_found = object()
    if args and isinstance(args[0], list):
        args = args[0]
    ret = []
    for arg in args:
        if get_var(data, arg, not_found) is not_found:
            ret.append(arg)
    return ret


def missing_some(data, min_required, args):
    """Implements the missing_some operator for finding missing variables."""
    if min_required < 1:
        return []
    found = 0
    not_found = object()
    ret = []
    for arg in args:
        if get_var(data, arg, not_found) is not_found:
            ret.append(arg)
        else:
            found += 1
            if found >= min_required:
                return []
    return ret

def substr(data, index, ln=None):
    substr = data[index:]
    if ln is not None:
        return substr[:ln]
    else:
        return substr

def map_(values, data):
    if values is None:
        return []
    ret = []
    op = list(data.keys())[0]
    for value in values:
        if op == "var":
            ret.append(jsonLogic(data, value))
        else:
            ret.append(operations[op](value, data[op][1]))
    return ret

def filter_(values, condition):
    ret = []
    for value in values:
        if type(condition) is type({}):
            op = list(condition.keys())[0]
            if operations[op](value, condition[op][1]):
                ret.append(value)
        else:
            if bool(value) is condition:
                ret.append(value)
    return ret

def reduce_(values, data):
    ldata = jsonLogic(values[0], data)
    llogic = values[1]
    init = values[2]
    op = list(llogic.keys())[0]
    if ldata is None:
        return init
    if type(ldata[1]) is type({}):
        tmp = []
        for val in ldata:
            tmp.append(jsonLogic(llogic[op][1], {"current":val}))
        ldata = tmp
    for val in ldata:
        init = jsonLogic({op:[init,val]})
    return init

def all_(values, data):
    lcode = values[1]
    ldata = jsonLogic(values[0], data)
    if ldata is None:
        return False
    if len(ldata) == 0:
        return False
    if type(ldata[1]) is type({}):
        tmp = []
        for val in ldata:
            if not jsonLogic(lcode, val):
                return False
        return True
    l2data = filter_(ldata, values[1])
    return len(ldata) == len(l2data)

def some_(values, data):
    lcode = values[1]
    ldata = jsonLogic(values[0], data)
    if ldata is None:
        return False
    if len(ldata) == 0:
        return False
    if type(ldata[1]) is type({}):
        tmp = []
        for val in ldata:
            if(jsonLogic(lcode, val)):
                return True
        return False
    l2data = filter_(ldata, values[1])
    return len(ldata) >= len(l2data) and len(l2data) > 0

operations = {
    "==": soft_equals,
    "===": hard_equals,
    "!=": lambda a, b: not soft_equals(a, b),
    "!==": lambda a, b: not hard_equals(a, b),
    ">": lambda a, b: less(b, a),
    ">=": lambda a, b: less(b, a) or soft_equals(a, b),
    "<": less,
    "<=": less_or_equal,
    "!": lambda a: not a,
    "!!": bool,
    "%": lambda a, b: a % b,
    "and": lambda *args: reduce(lambda total, arg: total and arg, args, True),
    "or": lambda *args: reduce(lambda total, arg: total or arg, args, False),
    "?:": lambda a, b, c: b if a else c,
    "if": if_,
    "log": lambda a: logger.info(a) or a,
    "in": lambda a, b: a in b if "__contains__" in dir(b) else False,
    "cat": lambda *args: "".join(str(arg) for arg in args),
    "+": plus,
    "*": lambda *args: reduce(lambda total, arg: total * float(arg), args, 1),
    "-": minus,
    "/": lambda a, b=None: a if b is None else float(a) / float(b),
    "min": lambda *args: min(args),
    "max": lambda *args: max(args),
    "merge": merge,
    "count": lambda *args: sum(1 if a else 0 for a in args),
    "substr": substr,
    "reduce": reduce_,
}


def jsonLogic(tests, data=None):
    """Executes the json-logic with given data."""
    # You've recursed to a primitive, stop!
    if tests is None or not isinstance(tests, dict):
        return tests

    data = data or {}

    operator = list(tests.keys())[0]
    values = tests[operator]

    # Easy syntax for unary operators, like {"var": "x"} instead of strict
    # {"var": ["x"]}
    if not isinstance(values, list) and not isinstance(values, tuple):
        values = [values]

    if operator == 'filter':
        values[0] = jsonLogic(values[0], data)
        return filter_(values[0], values[1])

    if operator == 'map':
        values[0] = jsonLogic(values[0], data)
        return map_(values[0], values[1])

    if operator == 'reduce':
        return reduce_(values, data)

    if operator == 'all':
        return all_(values, data)

    if operator == 'some':
        return some_(values, data)

    if operator == 'none':
        return not some_(values, data)

    # Recursion!
    values = [jsonLogic(val, data) for val in values]

    if operator == 'var':
        return get_var(data, *values)
    if operator == 'missing':
        return missing(data, *values)
    if operator == 'missing_some':
        return missing_some(data, *values)

    if operator not in operations:
        raise ValueError("Unrecognized operation %s" % operator)

    return operations[operator](*values)
