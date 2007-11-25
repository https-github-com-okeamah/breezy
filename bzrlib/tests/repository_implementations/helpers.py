# Copyright (C) 2007 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Helper classes for repository implementation tests."""

from cStringIO import StringIO

from bzrlib import (
    inventory,
    osutils,
    revision as _mod_revision,
    )
from bzrlib.repofmt.knitrepo import RepositoryFormatKnit
from bzrlib.tests.repository_implementations import TestCaseWithRepository
from bzrlib.tests import TestNotApplicable


class TestCaseWithBrokenRevisionIndex(TestCaseWithRepository):

    def make_repo_with_extra_ghost_index(self):
        """Make a corrupt repository.
        
        It will contain one revision, 'revision-id'.  The knit index will claim
        that it has one parent, 'incorrect-parent', but the revision text will
        claim it has no parents.

        Note: only the *cache* of the knit index is corrupted.  Thus the
        corruption will only last while the repository is locked.  For this
        reason, the returned repo is locked.
        """
        if not isinstance(self.repository_format, RepositoryFormatKnit):
            # XXX: Broken revision graphs can happen to weaves too, but they're
            # pretty deprecated.  Ideally these tests should apply to any repo
            # where repo.revision_graph_can_have_wrong_parents() is True, but
            # at the moment we only know how to corrupt knit repos.
            raise TestNotApplicable(
                "%s isn't a knit format" % self.repository_format)

        repo = self.make_repository('broken')
        repo.lock_write()
        repo.start_write_group()
        try:
            inv = inventory.Inventory(revision_id='revision-id')
            inv.root.revision = 'revision-id'
            inv_sha1 = repo.add_inventory('revision-id', inv, [])
            if repo.supports_rich_root():
                root_id = inv.root.file_id
                vf = repo.weave_store.get_weave_or_empty(root_id,
                    repo.get_transaction())
                vf.add_lines('revision-id', [], [])
            revision = _mod_revision.Revision('revision-id',
                committer='jrandom@example.com', timestamp=0,
                inventory_sha1=inv_sha1, timezone=0, message='message',
                parent_ids=[])
            # Manually add the revision text using the RevisionStore API, with
            # bad parents.
            rev_tmp = StringIO()
            repo._revision_store._serializer.write_revision(revision, rev_tmp)
            rev_tmp.seek(0)
            repo._revision_store.get_revision_file(repo.get_transaction()
                ).add_lines_with_ghosts(revision.revision_id,
                ['incorrect-parent'],
                osutils.split_lines(rev_tmp.read()))
        except:
            repo.abort_write_group()
            repo.unlock()
            raise
        else:
            repo.commit_write_group()
            repo.unlock()

        repo.lock_write()
        self.addCleanup(repo.unlock)
        return repo

