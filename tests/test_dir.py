# Copyright (C) 2009-2018 Jelmer Vernooij <jelmer@jelmer.uk>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Test the GitDir class"""

from __future__ import absolute_import

from dulwich.repo import Repo as GitRepo
import os

from .... import (
    controldir,
    errors,
    urlutils,
    )
from ....tests import TestSkipped

from .. import (
    dir,
    tests,
    workingtree,
    )


class TestGitDir(tests.TestCaseInTempDir):

    def test_get_head_branch_reference(self):
        GitRepo.init(".")

        gd = controldir.ControlDir.open('.')
        self.assertEquals(
            "%s,branch=master" %
                urlutils.local_path_to_url(os.path.abspath(".")),
            gd.get_branch_reference())

    def test_open_existing(self):
        GitRepo.init(".")

        gd = controldir.ControlDir.open('.')
        self.assertIsInstance(gd, dir.LocalGitDir)

    def test_open_workingtree(self):
        GitRepo.init(".")

        gd = controldir.ControlDir.open('.')
        raise TestSkipped
        wt = gd.open_workingtree()
        self.assertIsInstance(wt, workingtree.GitWorkingTree)

    def test_open_workingtree_bare(self):
        GitRepo.init_bare(".")

        gd = controldir.ControlDir.open('.')
        self.assertRaises(errors.NoWorkingTree, gd.open_workingtree)


class TestGitDirFormat(tests.TestCase):

    def setUp(self):
        super(TestGitDirFormat, self).setUp()
        self.format = dir.LocalGitControlDirFormat()

    def test_get_format_description(self):
        self.assertEquals("Local Git Repository",
                          self.format.get_format_description())

    def test_eq(self):
        format2 = dir.LocalGitControlDirFormat()
        self.assertEquals(self.format, format2)
        self.assertEquals(self.format, self.format)
        bzr_format = controldir.format_registry.make_controldir("default")
        self.assertNotEquals(self.format, bzr_format)

