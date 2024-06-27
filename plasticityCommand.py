

from enum import Enum
from functools import wraps


def add_prefix_decorator(enum_class):
    original_str_method = enum_class.__str__

    @wraps(original_str_method)
    def modified_str_method(self):
        return f'''{self.__class__.__name__}:{self.value}'''.lower()
    
    enum_class.__str__ = modified_str_method
    return enum_class



@add_prefix_decorator
class App(Enum):
    NEW_WINDOW = 'new-window'
    QUIT ='quit'


@add_prefix_decorator
class Command(Enum):
    # def __str__(self) -> str:
    #     return f'''{self.__class__.__name__}:{self.value}'''.lower()
    
    ABORT ='abort'
    ALTERNATIVE_DUPLICATE = 'alternativ-duplicate'
    
    
n = Command.ALTERNATIVE_DUPLICATE
b = App.NEW_WINDOW
print(n,b)