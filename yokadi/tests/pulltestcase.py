import unittest

from tempfile import TemporaryDirectory

from yokadi.core import db, dbutils
from yokadi.core.db import Task
from yokadi.sync.pull import pull
from yokadi.sync.vcschanges import VcsChanges
from yokadi.tests.testutils import createFile


class StubConflictResolver(object):
    def resolve(self, vcsImpl, conflict):
        return False


class StubVcsImpl(object):
    def setDir(self, repoDir):
        pass

    def pull(self):
        pass

    def getConflicts(self):
        return []

    def isWorkTreeClean(self):
        return True

    def commitAll(message=""):
        pass

    def getChangesSince(self, commitId):
        return VcsChanges()

    def updateBranch(self, branch, commitId):
        pass


def createTaskFile(dirname, uuid, projectName, title):
    content = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Yokadi calendar //yokadi.github.com//
BEGIN:VTODO
DTSTART;VALUE=DATE-TIME:20160112T191200
RELATED-TO:yokadi-project-{projectName}
SUMMARY:{title}
UID:yokadi-task-{uuid}
END:VTODO
END:VCALENDAR
""".format(**locals())
    createFile(dirname, uuid + ".ics", content)


class PullTestCase(unittest.TestCase):
    def setUp(self):
        db.connectDatabase("", memoryDatabase=True)
        db.setDefaultConfig()
        self.session = db.getSession()

    def testNothingToDo(self):
        with TemporaryDirectory() as tmpDir:
            vcsImpl = StubVcsImpl()
            pull(tmpDir, vcsImpl)

    def testRemoteChangesOnly(self):
        with TemporaryDirectory() as tmpDir:
            # Create two tasks, one which will be modified and one which will be
            # removed
            modifiedTask = dbutils.addTask("prj", "Modified", interactive=False)
            modifiedTask.uuid = "1234-modified"
            self.session.add(modifiedTask)

            removedTask = dbutils.addTask("prj", "Removed", interactive=False)
            removedTask.uuid = "1234-removed"
            self.session.add(removedTask)
            self.session.commit()

            # Prepare a fake vcs pull: create files which would result from the
            # pull and create a VcsImpl to fake it
            createTaskFile(tmpDir, uuid="1234-added", projectName="prj", title="Added")
            createTaskFile(tmpDir, uuid="1234-modified", projectName="prj2", title="New task title")

            class MyVcsImpl(StubVcsImpl):
                def getChangesSince(self, commitId):
                    changes = VcsChanges()
                    changes.added = {"1234-added.ics"}
                    changes.modified = {"1234-modified.ics"}
                    changes.removed = {"1234-removed.ics"}
                    return changes

            # Do the pull
            pull(tmpDir, MyVcsImpl())

            # Check changes
            modifiedTask2 = dbutils.getTaskFromId(modifiedTask.id)
            self.assertEqual(modifiedTask2.project.name, "prj2")
            self.assertEqual(modifiedTask2.title, "New task title")

            addedTask = self.session.query(Task).filter_by(uuid="1234-added").one()
            self.assertEqual(addedTask.project.name, "prj")
            self.assertEqual(addedTask.title, "Added")

            lst = self.session.query(Task).filter_by(id=removedTask.id)
            self.assertEqual(len(list(lst)), 0)

    def testRemoteAndLocalChanges(self):
        with TemporaryDirectory() as tmpDir:
            # Prepare a fake vcs pull: create an added file
            # and create a VcsImpl to fake it
            createTaskFile(tmpDir, uuid="1234-added", projectName="prj", title="Added")

            class MyVcsImpl(StubVcsImpl):
                def __init__(self):
                    self.commitAllCallCount = 0

                def getChangesSince(self, commitId):
                    changes = VcsChanges()
                    changes.added = {"1234-added.ics"}
                    return changes

                def isWorkTreeClean(self):
                    return False

                def commitAll(self, message=""):
                    self.commitAllCallCount += 1

            # Do the pull
            vcsImpl = MyVcsImpl()
            pull(tmpDir, vcsImpl)

            # Check changes. Since work tree was not clean there should be a
            # commit to finish the merge.
            self.assertEqual(vcsImpl.commitAllCallCount, 1)

            addedTask = self.session.query(Task).filter_by(uuid="1234-added").one()
            self.assertEqual(addedTask.project.name, "prj")
            self.assertEqual(addedTask.title, "Added")

    def testConflictsAbortMerge(self):
        with TemporaryDirectory() as tmpDir:
            class MyVcsImpl(StubVcsImpl):
                def __init__(self):
                    self.abortMergeCallCount = 0
                    self.commitAllCallCount = 0

                def getChangesSince(self, commitId):
                    changes = VcsChanges()
                    changes.added = {"1234-conflict.ics"}
                    return changes

                def isWorkTreeClean(self):
                    return False

                def getConflicts(self):
                    return [(b'UU', '1234-conflict.ics')]

                def abortMerge(self):
                    self.abortMergeCallCount += 1

                def commitAll(self, message=""):
                    self.commitAllCallCount += 1

            # Do the pull
            vcsImpl = MyVcsImpl()
            pull(tmpDir, vcsImpl)

            # Check changes. Since there was a conflict there should be no
            # commit.
            self.assertEqual(vcsImpl.abortMergeCallCount, 1)
            self.assertEqual(vcsImpl.commitAllCallCount, 0)

    def testConflictsSolved(self):
        with TemporaryDirectory() as tmpDir:
            createTaskFile(tmpDir, uuid="1234-conflict", projectName="prj", title="Added")

            class MyConflictResolver(StubConflictResolver):
                def resolve(self, vcsImpl, conflict):
                    return True

            class MyVcsImpl(StubVcsImpl):
                def __init__(self):
                    self.abortMergeCallCount = 0
                    self.commitAllCallCount = 0

                def getChangesSince(self, commitId):
                    changes = VcsChanges()
                    changes.added = {"1234-conflict.ics"}
                    return changes

                def isWorkTreeClean(self):
                    return False

                def getConflicts(self):
                    return [(b'UU', '1234-conflict.ics')]

                def abortMerge(self):
                    self.abortMergeCallCount += 1

                def commitAll(self, message=""):
                    self.commitAllCallCount += 1

            # Do the pull
            vcsImpl = MyVcsImpl()
            conflictResolver = MyConflictResolver()
            pull(tmpDir, vcsImpl=vcsImpl, conflictResolver=conflictResolver)

            # Check changes. Conflict has been solved, there should be a merge.
            self.assertEqual(vcsImpl.abortMergeCallCount, 0)
            self.assertEqual(vcsImpl.commitAllCallCount, 1)
