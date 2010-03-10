# Copyright (C) 2009 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Custom revision specifier for Subversion."""

# Please note that imports are delayed as much as possible here since
# if DWIM revspecs are supported this module is imported by __init__.py.

from bzrlib.errors import (
    InvalidRevisionId,
    InvalidRevisionSpec,
    )
from bzrlib.revisionspec import (
    RevisionInfo,
    RevisionSpec,
    )


def valid_git_sha1(hex):
    import binascii
    try:
        binascii.unhexlify(hex)
    except TypeError:
        return False
    else:
        return True


class RevisionSpec_git(RevisionSpec):
    """Selects a revision using a Subversion revision number."""

    help_txt = """Selects a revision using a Git revision sha1.
    """

    prefix = 'git:'
    wants_revision_history = False

    def _lookup_git_sha1(self, branch, sha1):
        from bzrlib.plugins.git.errors import (
            GitSmartRemoteNotSupported,
            )
        from bzrlib.plugins.git.mapping import (
            default_mapping,
            )

        bzr_revid = getattr(branch.repository, "lookup_foreign_revision_id",
                              default_mapping.revision_id_foreign_to_bzr)(sha1)
        try:
            if branch.repository.has_revision(bzr_revid):
                history = self._history(branch, bzr_revid)
                return RevisionInfo.from_revision_id(branch, bzr_revid, history)
        except GitSmartRemoteNotSupported:
            return RevisionInfo(branch, None, bzr_revid)
        raise InvalidRevisionSpec(self.user_spec, branch)

    def _history(self, branch, revid):
        history = list(branch.repository.iter_reverse_revision_history(revid))
        history.reverse()
        return history

    def __nonzero__(self):
        from bzrlib.revision import (
            NULL_REVISION,
            )
        # The default implementation uses branch.repository.has_revision()
        if self.rev_id is None:
            return False
        if self.rev_id == NULL_REVISION:
            return False
        return True

    def _find_short_git_sha1(self, branch, sha1):
        from bzrlib.plugins.git.mapping import (
            mapping_registry,
            )
        parse_revid = getattr(branch.repository, "lookup_bzr_revision_id",
                              mapping_registry.parse_revision_id)
        branch.repository.lock_read()
        try:
            graph = branch.repository.get_graph()
            for revid, _ in graph.iter_ancestry([branch.last_revision()]):
                try:
                    foreign_revid, mapping = parse_revid(revid)
                except InvalidRevisionId:
                    continue
                if foreign_revid.startswith(sha1):
                    history = self._history(branch, revid)
                    return RevisionInfo.from_revision_id(branch, revid, history)
            raise InvalidRevisionSpec(self.user_spec, branch)
        finally:
            branch.repository.unlock()

    def _match_on(self, branch, revs):
        loc = self.spec.find(':')
        git_sha1 = self.spec[loc+1:].encode("utf-8")
        if len(git_sha1) > 40 or not valid_git_sha1(git_sha1):
            raise InvalidRevisionSpec(self.user_spec, branch)
        from bzrlib.plugins.git import (
            lazy_check_versions,
            )
        lazy_check_versions()
        if len(git_sha1) == 40:
            return self._lookup_git_sha1(branch, git_sha1)
        else:
            return self._find_short_git_sha1(branch, git_sha1)

    def needs_branch(self):
        return True

    def get_branch(self):
        return None
