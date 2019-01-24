import os, sys
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import textbook_utils as tu
sys.path.remove("../utils")
from datetime import datetime
import pytest
import unittest

class TestApp(unittest.TestCase):
    pass

if __name__ == '__main__':
    unittest.main()
