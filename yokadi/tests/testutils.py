# -*- coding: UTF-8 -*-
"""
Utils for unit-test
@author: Aurélien Gâteau <mail@agateau.com>
@license: GPL v3 or later
"""

import os


def multiLinesAssertEqual(test, str1, str2):
    lst1 = str1.splitlines()
    lst2 = str2.splitlines()
    for row, lines in enumerate(zip(lst1, lst2)):
        line1, line2 = lines
        test.assertEqual(line1, line2, "Error line %d:\n%r\n!=\n%r" % (row + 1, line1, line2))
    test.assertEqual(len(lst1), len(lst2))


class TestRenderer(object):
    """
    A fake renderer, which stores all rendered tasks in taskDict
    """
    def __init__(self):
        self.taskDict = {}

    def addTaskList(self, sectionName, taskList):
        self.taskDict[sectionName] = taskList

    def end(self):
        pass


class EnvironSaver(object):
    """
    This class saves and restore the environment.

    Can be used manually or as a context manager.
    """
    def __init__(self):
        self.save()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore()
        return False

    def save(self):
        self.oldEnv = dict(os.environ)

    def restore(self):
        # Do not use `os.environ = env`: this would replace the special os.environ
        # object with a plain dict. We must update the *existing* object.
        os.environ.clear()
        os.environ.update(self.oldEnv)
# vi: ts=4 sw=4 et
