
from tinydb import TinyDB, Query
db = TinyDB('./test file/test 1.plasticityassettooldb')
db.insert({'type': 'apple', 'count': 7})