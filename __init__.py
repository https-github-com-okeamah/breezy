# Copyright (C) 2009-2018 Jelmer Vernooij <jelmer@jelmer.uk>
# Copyright (C) 2006-2009 Canonical Ltd

# Authors: Robert Collins <robert.collins@canonical.com>
#          Jelmer Vernooij <jelmer@jelmer.uk>
#          John Carr <john.carr@unrouted.co.uk>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


"""A GIT branch and repository format implementation for bzr."""

from __future__ import absolute_import

import os
import sys

import breezy

from .info import (
    bzr_compatible_versions,
    bzr_plugin_version as version_info,
    dulwich_minimum_version,
    )

if version_info[3] == 'final':
    version_string = '%d.%d.%d' % version_info[:3]
else:
    version_string = '%d.%d.%d%s%d' % version_info
__version__ = version_string

if breezy.version_info[:3] not in bzr_compatible_versions:
    from ...errors import IncompatibleVersion
    raise IncompatibleVersion(breezy,
            bzr_compatible_versions, breezy.version_info[:3])

try:
    from ...i18n import load_plugin_translations
except ImportError: # No translations for bzr < 2.5
    gettext = lambda x: x
else:
    translation = load_plugin_translations("bzr-git")
    gettext = translation.gettext

from ... import (
    __version__ as breezy_version,
    errors as bzr_errors,
    trace,
    )

from ...controldir import (
    ControlDirFormat,
    Prober,
    format_registry,
    network_format_registry as controldir_network_format_registry,
    )

from ...transport import (
    register_lazy_transport,
    register_transport_proto,
    transport_server_registry,
    )
from ...commands import (
    plugin_cmds,
    )


if getattr(sys, "frozen", None):
    # allow import additional libs from ./_lib for bzr.exe only
    sys.path.append(os.path.normpath(
        os.path.join(os.path.dirname(__file__), '_lib')))


def import_dulwich():
    try:
        from dulwich import __version__ as dulwich_version
    except ImportError:
        raise bzr_errors.DependencyNotPresent("dulwich",
            "bzr-git: Please install dulwich, https://launchpad.net/dulwich")
    else:
        if dulwich_version < dulwich_minimum_version:
            raise bzr_errors.DependencyNotPresent("dulwich",
                "bzr-git: Dulwich is too old; at least %d.%d.%d is required" %
                    dulwich_minimum_version)


_versions_checked = False
def lazy_check_versions():
    global _versions_checked
    if _versions_checked:
        return
    import_dulwich()
    _versions_checked = True

format_registry.register_lazy('git',
    __name__ + ".dir", "LocalGitControlDirFormat",
    help='GIT repository.', native=False, experimental=False,
    )

format_registry.register_lazy('git-bare',
    __name__ + ".dir", "BareLocalGitControlDirFormat",
    help='Bare GIT repository (no working tree).', native=False,
    experimental=False,
    )

from ...revisionspec import (RevisionSpec_dwim, revspec_registry)
revspec_registry.register_lazy("git:", __name__ + ".revspec",
    "RevisionSpec_git")
RevisionSpec_dwim.append_possible_lazy_revspec(
    __name__ + ".revspec", "RevisionSpec_git")


class LocalGitProber(Prober):

    def probe_transport(self, transport):
        try:
            external_url = transport.external_url()
        except bzr_errors.InProcessTransport:
            raise bzr_errors.NotBranchError(path=transport.base)
        if (external_url.startswith("http:") or
            external_url.startswith("https:")):
            # Already handled by RemoteGitProber
            raise bzr_errors.NotBranchError(path=transport.base)
        from ... import urlutils
        if urlutils.split(transport.base)[1] == ".git":
            raise bzr_errors.NotBranchError(path=transport.base)
        if not transport.has_any(['objects', '.git/objects']):
            raise bzr_errors.NotBranchError(path=transport.base)
        lazy_check_versions()
        from .dir import (
            BareLocalGitControlDirFormat,
            LocalGitControlDirFormat,
            )
        if transport.has_any(['.git/objects']):
            return LocalGitControlDirFormat()
        if transport.has('info') and transport.has('objects'):
            return BareLocalGitControlDirFormat()
        raise bzr_errors.NotBranchError(path=transport.base)

    @classmethod
    def known_formats(cls):
        from .dir import (
            BareLocalGitControlDirFormat,
            LocalGitControlDirFormat,
            )
        return set([BareLocalGitControlDirFormat(), LocalGitControlDirFormat()])


class RemoteGitProber(Prober):

    def probe_http_transport(self, transport):
        from ... import urlutils
        base_url, _ = urlutils.split_segment_parameters(transport.external_url())
        url = urlutils.join(base_url, "info/refs") + "?service=git-upload-pack"
        from ...transport.http._urllib import HttpTransport_urllib, Request
        headers = {"Content-Type": "application/x-git-upload-pack-request"}
        req = Request('GET', url, accepted_errors=[200, 403, 404, 405],
                      headers=headers)
        if req.get_host() == "github.com":
            # GitHub requires we lie. https://github.com/dulwich/dulwich/issues/562
            headers["User-agent"] = "git/Breezy/%s" % breezy_version
        elif req.get_host() == "bazaar.launchpad.net":
            # Don't attempt Git probes against bazaar.launchpad.net; pad.lv/1744830
            raise bzr_errors.NotBranchError(transport.base)
        req.follow_redirections = True
        resp = transport._perform(req)
        if resp.code in (404, 405):
            raise bzr_errors.NotBranchError(transport.base)
        headers = resp.headers
        ct = headers.getheader("Content-Type")
        if ct is None:
            raise bzr_errors.NotBranchError(transport.base)
        if ct.startswith("application/x-git"):
            from .remote import RemoteGitControlDirFormat
            return RemoteGitControlDirFormat()
        else:
            from .dir import (
                BareLocalGitControlDirFormat,
                )
            ret = BareLocalGitControlDirFormat()
            ret._refs_text = resp.read()
            return ret

    def probe_transport(self, transport):
        try:
            external_url = transport.external_url()
        except bzr_errors.InProcessTransport:
            raise bzr_errors.NotBranchError(path=transport.base)

        if (external_url.startswith("http:") or
            external_url.startswith("https:")):
            return self.probe_http_transport(transport)

        if (not external_url.startswith("git://") and
            not external_url.startswith("git+")):
            raise bzr_errors.NotBranchError(transport.base)

        # little ugly, but works
        from .remote import (
            GitSmartTransport,
            RemoteGitControlDirFormat,
            )
        if isinstance(transport, GitSmartTransport):
            return RemoteGitControlDirFormat()
        raise bzr_errors.NotBranchError(path=transport.base)

    @classmethod
    def known_formats(cls):
        from .remote import RemoteGitControlDirFormat
        return set([RemoteGitControlDirFormat()])


ControlDirFormat.register_prober(LocalGitProber)
ControlDirFormat._server_probers.append(RemoteGitProber)

register_transport_proto('git://',
        help="Access using the Git smart server protocol.")
register_transport_proto('git+ssh://',
        help="Access using the Git smart server protocol over SSH.")

register_lazy_transport("git://", __name__ + '.remote',
                        'TCPGitSmartTransport')
register_lazy_transport("git+ssh://", __name__ + '.remote',
                        'SSHGitSmartTransport')


plugin_cmds.register_lazy("cmd_git_import", [], __name__ + ".commands")
plugin_cmds.register_lazy("cmd_git_object", ["git-objects", "git-cat"],
    __name__ + ".commands")
plugin_cmds.register_lazy("cmd_git_refs", [], __name__ + ".commands")
plugin_cmds.register_lazy("cmd_git_apply", [], __name__ + ".commands")
plugin_cmds.register_lazy("cmd_git_push_pristine_tar_deltas",
        ['git-push-pristine-tar', 'git-push-pristine'],
    __name__ + ".commands")

def extract_git_foreign_revid(rev):
    try:
        foreign_revid = rev.foreign_revid
    except AttributeError:
        from .mapping import mapping_registry
        foreign_revid, mapping = \
            mapping_registry.parse_revision_id(rev.revision_id)
        return foreign_revid
    else:
        from .mapping import foreign_vcs_git
        if rev.mapping.vcs == foreign_vcs_git:
            return foreign_revid
        else:
            raise bzr_errors.InvalidRevisionId(rev.revision_id, None)


def update_stanza(rev, stanza):
    mapping = getattr(rev, "mapping", None)
    try:
        git_commit = extract_git_foreign_revid(rev)
    except bzr_errors.InvalidRevisionId:
        pass
    else:
        stanza.add("git-commit", git_commit)

from ...hooks import install_lazy_named_hook
install_lazy_named_hook("breezy.version_info_formats.format_rio",
    "RioVersionInfoBuilder.hooks", "revision", update_stanza,
    "git commits")


transport_server_registry.register_lazy('git',
    __name__ + '.server',
    'serve_git',
    'Git Smart server protocol over TCP. (default port: 9418)')

transport_server_registry.register_lazy('git-receive-pack',
    __name__ + '.server',
    'serve_git_receive_pack',
    help='Git Smart server receive pack command. (inetd mode only)')
transport_server_registry.register_lazy('git-upload-pack',
    __name__ + 'git.server',
    'serve_git_upload_pack',
    help='Git Smart server upload pack command. (inetd mode only)')

from ...repository import (
    format_registry as repository_format_registry,
    network_format_registry as repository_network_format_registry,
    )
repository_network_format_registry.register_lazy('git',
    __name__ + '.repository', 'GitRepositoryFormat')

register_extra_lazy_repository_format = getattr(repository_format_registry,
    "register_extra_lazy")
register_extra_lazy_repository_format(__name__ + '.repository',
    'GitRepositoryFormat')

from ...branch import (
    network_format_registry as branch_network_format_registry,
    )
branch_network_format_registry.register_lazy('git',
    __name__ + '.branch', 'LocalGitBranchFormat')


from ...branch import (
    format_registry as branch_format_registry,
    )
branch_format_registry.register_extra_lazy(
    __name__ + '.branch',
    'LocalGitBranchFormat',
    )
branch_format_registry.register_extra_lazy(
    __name__ + '.remote',
    'RemoteGitBranchFormat',
    )


from ...workingtree import (
    format_registry as workingtree_format_registry,
    )
workingtree_format_registry.register_extra_lazy(
    __name__ + '.workingtree',
    'GitWorkingTreeFormat',
    )

controldir_network_format_registry.register_lazy('git',
    __name__ + ".dir", "GitControlDirFormat")


try:
    from ...registry import register_lazy
except ImportError:
    from ...diff import format_registry as diff_format_registry
    diff_format_registry.register_lazy('git', __name__ + '.send',
        'GitDiffTree', 'Git am-style diff format')

    from ...send import (
        format_registry as send_format_registry,
        )
    send_format_registry.register_lazy('git', __name__ + '.send',
                                       'send_git', 'Git am-style diff format')

    from ...directory_service import directories
    directories.register_lazy('github:', __name__ + '.directory',
                              'GitHubDirectory',
                              'GitHub directory.')
    directories.register_lazy('git@github.com:', __name__ + '.directory',
                              'GitHubDirectory',
                              'GitHub directory.')

    from ...help_topics import (
        topic_registry,
        )
    topic_registry.register_lazy('git', __name__ + '.help', 'help_git',
        'Using Bazaar with Git')

    from ...foreign import (
        foreign_vcs_registry,
        )
    foreign_vcs_registry.register_lazy("git",
        __name__ + ".mapping", "foreign_vcs_git", "Stupid content tracker")
else:
    register_lazy("breezy.diff", "format_registry",
        'git', __name__ + '.send', 'GitDiffTree',
        'Git am-style diff format')
    register_lazy("breezy.send", "format_registry",
        'git', __name__ + '.send', 'send_git',
        'Git am-style diff format')
    register_lazy('breezy.directory_service', 'directories', 'github:',
            __name__ + '.directory', 'GitHubDirectory',
            'GitHub directory.')
    register_lazy('breezy.directory_service', 'directories',
            'git@github.com:', __name__ + '.directory',
            'GitHubDirectory', 'GitHub directory.')
    register_lazy('breezy.help_topics', 'topic_registry',
            'git', __name__ + '.help', 'help_git',
            'Using Bazaar with Git')
    register_lazy('breezy.foreign', 'foreign_vcs_registry', "git",
        __name__ + ".mapping", "foreign_vcs_git", "Stupid content tracker")

def update_git_cache(repository, revid):
    """Update the git cache after a local commit."""
    if getattr(repository, "_git", None) is not None:
        return # No need to update cache for git repositories

    if not repository.control_transport.has("git"):
        return # No existing cache, don't bother updating
    try:
        lazy_check_versions()
    except bzr_errors.DependencyNotPresent, e:
        # dulwich is probably missing. silently ignore
        trace.mutter("not updating git map for %r: %s",
            repository, e)

    from .object_store import BazaarObjectStore
    store = BazaarObjectStore(repository)
    with store.lock_write():
        try:
            parent_revisions = set(repository.get_parent_map([revid])[revid])
        except KeyError:
            # Isn't this a bit odd - how can a revision that was just committed be missing?
            return
        missing_revisions = store._missing_revisions(parent_revisions)
        if not missing_revisions:
            # Only update if the cache was up to date previously
            store._update_sha_map_revision(revid)


def post_commit_update_cache(local_branch, master_branch, old_revno, old_revid,
        new_revno, new_revid):
    if local_branch is not None:
        update_git_cache(local_branch.repository, new_revid)
    update_git_cache(master_branch.repository, new_revid)


def loggerhead_git_hook(branch_app, environ):
    branch = branch_app.branch
    config_stack = branch.get_config_stack()
    if config_stack.get('http_git'):
        return None
    from .server import git_http_hook
    return git_http_hook(branch, environ['REQUEST_METHOD'],
        environ['PATH_INFO'])

install_lazy_named_hook("breezy.branch",
    "Branch.hooks", "post_commit", post_commit_update_cache,
    "git cache")
install_lazy_named_hook("breezy.plugins.loggerhead.apps.branch",
    "BranchWSGIApp.hooks", "controller",
    loggerhead_git_hook, "git support")


from ...config import (
    option_registry,
    Option,
    bool_from_store,
    )

option_registry.register(
    Option('git.http',
           default=None, from_unicode=bool_from_store, invalid='warning',
           help='''\
Allow fetching of Git packs over HTTP.

This enables support for fetching Git packs over HTTP in Loggerhead.
'''))

def test_suite():
    from . import tests
    return tests.test_suite()
