import os, sys
import unittest
import string
import random
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import app_utils as au
from datetime import datetime
import pytest

# class TestCase():
#     """Go through every month and test that the semester works as expected"""
#     @mock.patch("../utils/app_utils.datetime")
def test_get_curr_semester():
    # assertEqual('190112', r)
    # datetime_mock.date.today = Mock(return_value=datetime.strptime('Jun 1 2005', '%b %d %Y'))
    for i in range(1, 6):
        assert au.get_curr_semester(datetime(2018, i, 2)) == "SP18"
    for i in range(6, 8):
        assert au.get_curr_semester(datetime(2018, i, 2)) == "SU18"
    for i in range(8, 13):
        assert au.get_curr_semester(datetime(2018, i, 2)) == "FA18"


if __name__ == '__main__':
    test_get_curr_semester()
