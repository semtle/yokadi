

class PullUi(object):
    MERGE = "merge"
    RENAME = "rename"
    CANCEL = "cancel"

    def resolveConflicts(self, vcsImpl):
        """
        Must iterate on all conflicts returned by vcsImpl and fix them.
        Returns True if conflicts were solved, False otherwise.
        """
        raise NotImplementedError()

    def getMergeStrategy(self, vcsImpl):
        # Must return either MERGE, RENAME or CANCEL
        raise NotImplementedError()