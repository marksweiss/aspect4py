# By Mark Weiss
# Based on and steals liberally from http://avinashv.net/2008/04/python-decorators-syntactic-sugar/, by Avinasho Nora

import sys
import datetime

now = datetime.datetime.now


# To overwrite logging target, overwrite stdout
class Log(object):
    def __init__(self, out=None):
        if out:
            sys.stdout = out    
    
    def write(self, msg):
        print msg  # redirects based on sys.stdout binding in __int__()


class AspectBase(object):
    '''Base class for all AOP decorators. 
       Creates function binding in base class and provides default __init__() so derived classes are not cluttered with it'''
    def __init__(self, dec_func):
        self.dec_func = dec_func
        self.log = Log()

    def __call__(self, *args, **kwargs):
        raise 'Must be implemented in derived classes'

class AspectParamBase(AspectBase):
    '''Base class for all AOP decorators which want to recieve parameters. 
       Creates function binding in base class and provides default __init__() so derived classes are not cluttered with it.
       
       Parses the decorated function docstring to extract an external function to call in the decorator function, 
       the number of decorator functions argumentst to pass on, the keyword arguments to pass on, any other optional
       literal arguments to pass on, and whether or not the return value of the decorated function should also be
       passed to the external function as an argument.
       
       Syntax of the docstring as follows:
       [@NAME OF DECORATOR FUNCTION] [NAME OF EXTERNAL FUNCTION] *args([# OF ARGS TO PASS]) **kwargs([KWARGS KEYS TO PASS]) ([LITERAL ARGS TO PASS]) [return [OPTIONAL]]
       
       Example: @Postcondition is_return_gt100 *args(n) **kwargs(a) (100, 200) return'''
    def __init__(self, dec_func, condition_type):
        AspectBase.__init__(self, dec_func)
        
        for args_str in self.dec_func.__doc__.split('\n'):            
            if args_str.startswith(condition_type):
                try:
                    # Parse the name of the decorator function to call
                    idx_l = len(condition_type) + 1
                    idx_r = args_str.index(' ', idx_l)
                    self.ext_func = eval(args_str[idx_l:idx_r])

                    # Parse *args arguments. This is handled as simply the number of these
                    #  args, sequentially, to pass to the decorator
                    idx_l = args_str.index('(', idx_r)
                    idx_r = args_str.index(')', idx_l + 1)                        
                    self.num_call_args = args_str[idx_l:idx_r + 1].count(',') + 1

                    # Parse the keyword args to pass to the decorator. These are actually loaded
                    #  into a dict by arg key, and the arg value is loaded into the dict as an evaled value, not a string
                    idx_l = args_str.index('(', idx_r) + 1
                    idx_r = args_str.index(')', idx_l + 1) - 1
                    kwargs_keys = args_str[idx_l:idx_r + 1].split(',')
                    self.kwargs_keys = eval(args_str[idx_l:idx_r + 1])
                
                    # Parse the tuple of additional literal argument values to pass to the decorator
                    #   These are passed after the *args args (and before **kwargs, because they have to be)
                    idx_l = args_str.index('(', idx_r)
                    idx_r = args_str.index(')', idx_l + 1)                    
                    self.lit_args = eval(args_str[idx_l:idx_r + 1])
                        
                    # Parse for the return flag. If this is set, the return value is passed
                    #  to the decorator. Set flag here to indicate this call wants to test return value
                    if args_str.endswith("return"):
                        self.is_test_return = True

                    break
                except:
                    err_str = 'Illegal docstring format for parameterized decorator. Must be: "@dec_func ext_func (args) (kwargs)" ' + \
                              '(args) and (kwargs) tuples must be provided, even if they are empty tuples.'
                    print err_str
                    raise # ValueError might be raised here by any str.index() call. Want to fail.               
    
    def apply_ext_dec(self, *args, **kwargs):
        '''Helper which calls the ext_func, the callout to the function the decorator calls, and automatically handles
           unpacking the correct args, kwargs and additional literal args parsed from the docstring in __init__().
           This is just to encapsulate this somewhat obtuse syntax so that users just have a totally clean call:
           self.apply_ext_dec(*args, **kwargs)'''
        # First arg is the external function passed to __init__(), second is concat of number args to call plus lit args 
        #  passed to __init__() and third are kwargs with keys matching the kwargs keys passed to __init__()
        apply(self.ext_func, args[0:self.num_call_args] + self.lit_args, dict([(k, kwargs[k]) for k in self.kwargs_keys]))        
    
    def __call__(self, *args, **kwargs):
        '''NOTE: derived classes should call apply_decorator(self, *args, **kwargs) in their derived __call__() as desired
           to call an external decorator with the desired *args, **kwargs and additional literal args as documented in 
           __init__().docstring above'''
        raise 'Must be implemented in derived classes'

                    
class TimedCall(AspectBase):
    '''Decoration: Wraps __call__() in datetime calls to log execution time of function'''  
    def __call__(self, *args, **kwargs):
        # Oh boy, this is a hack. Wrap this in a try/finally just to be able to log end time from finally,
        #  which is both guaranteed to fire and guaranteed to fire after the try block call has returned
        start = 0
        try:
            start = now()
            return self.dec_func(*args, **kwargs)
        finally:
            self.log.write('Call elapsed time: ' + str(now() - start))


class Timestamp(AspectBase):
    '''Decoration: Prints datetime.now()'''    
    def __call__(self, *args, **kwargs):
        self.log.write(now())
        return self.dec_func(*args, **kwargs)


class Trace(AspectBase):
    '''Decoration: Prints function name and args'''
    def __call__(self, *args, **kwargs):
        ret = self.dec_func(*args, **kwargs)
        self.log.write('Function: ' + self.dec_func.__name__ + 
                       '\tArgs: ' + (', '.join([str(arg) for arg in args]) + 
                       ', '.join([(str(k) + "=" + str(kwargs[k])) for k in kwargs.keys()])) + 
                       '\tReturn: ' + str(ret))
        return ret


# Stolen from here: http://avinashv.net/2008/04/python-decorators-syntactic-sugar/
class Memoize(AspectBase):
    # Notice the pattern here to add an attribute to a derived class, here we need a dict for state as 
    #  decorated function recurses
    def __init__(self, dec_func):
        AspectBase.__init__(self, dec_func)
        self.memoized = {}
    
    def __call__(self, *args, **kwargs):
        try:
            return self.memoized[args]
        except KeyError:
            self.memoized[args] = self.function(*args, **kwargs)
            return self.memoized[args]


class PreconditionException(Exception): pass

class Precondition(AspectParamBase):
    '''Decoration: '''  
    def __init__(self, dec_func):
        AspectParamBase.__init__(self, dec_func, "@" + "Precondition")
    
    def __call__(self, *args, **kwargs):        
        # Call the precondition predicate. Raise a custom exception that Precondition call failed if it returned false.
        if not self.apply_ext_dec(*args, **kwargs):
            raise PreconditionException, "Error: precond: " + str(self.ext_func.__name__) + "  args: " + str(args[0:self.num_call_args]) 

        return self.dec_func(*args, **kwargs)


class PostconditionException(Exception): pass

class Postcondition(AspectParamBase):
    '''Decoration: '''  
    def __init__(self, dec_func):
        AspectParamBase.__init__(self, dec_func, "@" + "Postcondition")
    
    def __call__(self, *args, **kwargs):
        ret = self.dec_func(*args, **kwargs)
        if self.is_test_return:
            # Call the postcondition predicate. Raise a custom exception that Postcondition call failed if it returned false.
            if not self.apply_ext_dec(*args, **kwargs):
                raise PostconditionException, "Error: postcond: " + str(self.ext_func.__name__) + "  args: " + str((ret,) + self.lit_args) 

        return ret



# Tests
def is_positive(*args, **kwargs):
    # Just to verify args being passed
    for arg in args:
        print arg
        print arg
    for k in kwargs.keys():
        print k + " : " + str(kwargs[k])     
   
    return args[0] > 0
    
def is_return_gt100(*args, **kwargs):
    # Just to verify args being passed
    for arg in args:
        print arg
    for k in kwargs.keys():
        print k + " : " + str(kwargs[k])     
   
    return args[0] <= args[1]    

@Precondition
def square_pre(n, **kwargs):
    '''@Precondition is_positive *args(n) **kwargs('a') (100, 200)'''
    print "in square pre"
    return n * n

@Postcondition
def square_post(n, **kwargs):
    '''@Postcondition is_return_gt100 *args(n) **kwargs('a') (100, 200) return'''
    print "in square post"
    return n * n

@Timestamp
def square(n):
    print "in square"
    return n * n

@TimedCall
def square2(n):
    print "\nin square2"
    return n * n

@Trace
def square3(n):
    print "in square3"
    return n * n

# Boo-yah! They are composable and decorated function is only called once!
@Timestamp
@Trace
def square4(n):
    print "in square4"
    return n * n

# Boo-yah! They are composable and decorated function is only called once!
@TimedCall
@Timestamp
@Trace
def square5(n):
    print "in square5"
    return n * n
    
# Stolen from here: http://avinashv.net/2008/04/python-decorators-syntactic-sugar/
@Memoize
def fibonacci(n):
  print "in fib"
  if n in (0, 1): return n
  return fibonacci(n - 1) + fibonacci(n - 2)
  

if __name__ == "__main__":
    #print square_pre(5)
    #print square_pre(-1)
    print square_post(11, a=10)
    #print square_post(10)
    #print square(10)
    #print square2(10)
    #print ""
    #print square3(10)
    #print ""
    #print square4(n=5)
    #print ""
    #print square5(12)
    #print ""
    #print fibonacci(15)