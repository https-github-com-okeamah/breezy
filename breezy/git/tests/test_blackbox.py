from ...tests.script import TestCaseWithTransportAndScript
    def test_cat_revision(self):
        self.simple_commit()
        output, error = self.run_bzr(['cat-revision', '-r-1'], retcode=3)
        self.assertContainsRe(
            error,
            'brz: ERROR: Repository .* does not support access to raw '
            'revision texts')
        self.assertEqual(output, '')

    def test_push_without_calculate_revnos(self):
        self.run_bzr(['init', '--git', 'bla'])
        self.run_bzr(['init', '--git', 'foo'])
        self.run_bzr(['commit', '--unchanged', '-m', 'bla', 'foo'])
        output, error = self.run_bzr(
            ['push', '-Ocalculate_revnos=no', '-d', 'foo', 'bla'])
        self.assertEqual("", output)
        self.assertContainsRe(
            error,
            'Pushed up to revision id git(.*).\n')

    def test_push_lossy_non_mainline(self):
        self.run_bzr(['init', '--git', 'bla'])
        self.run_bzr(['init', 'foo'])
        self.run_bzr(['commit', '--unchanged', '-m', 'bla', 'foo'])
        self.run_bzr(['branch', 'foo', 'foo1'])
        self.run_bzr(['commit', '--unchanged', '-m', 'bla', 'foo1'])
        self.run_bzr(['commit', '--unchanged', '-m', 'bla', 'foo'])
        self.run_bzr(['merge', '-d', 'foo', 'foo1'])
        self.run_bzr(['commit', '--unchanged', '-m', 'merge', 'foo'])
        output, error = self.run_bzr(['push', '--lossy', '-r1.1.1', '-d', 'foo', 'bla'])
        self.assertEqual("", output)
        self.assertEqual(
            'Pushing from a Bazaar to a Git repository. For better '
            'performance, push into a Bazaar repository.\n'
            'All changes applied successfully.\n'
            'Pushed up to revision 2.\n', error)

        self.assertContainsRe(output, 'revno: 1')

    def test_log_without_revno(self):
        # Smoke test for "bzr log -v" in a git repository.
        self.simple_commit()

        # Check that bzr log does not fail and includes the revision.
        output, error = self.run_bzr(['log', '-Ocalculate_revnos=no'])
        self.assertNotContainsRe(output, 'revno: 1')

    def test_commit_without_revno(self):
        repo = GitRepo.init(self.test_dir)
        output, error = self.run_bzr(
            ['commit', '-Ocalculate_revnos=yes', '--unchanged', '-m', 'one'])
        self.assertContainsRe(error, 'Committed revision 1.')
        output, error = self.run_bzr(
            ['commit', '-Ocalculate_revnos=no', '--unchanged', '-m', 'two'])
        self.assertNotContainsRe(error, 'Committed revision 2.')
        self.assertContainsRe(error, 'Committed revid .*.')
        # Some older versions of Dulwich (< 0.19.12) formatted diffs slightly
        # differently.
        from dulwich import __version__ as dulwich_version
        if dulwich_version < (0, 19, 12):
            self.assertEqual(output,
                             'diff --git /dev/null b/a\n'
                             'old mode 0\n'
                             'new mode 100644\n'
                             'index 0000000..c197bd8 100644\n'
                             '--- /dev/null\n'
                             '+++ b/a\n'
                             '@@ -0,0 +1 @@\n'
                             '+contents of a\n')
        else:
            self.assertEqual(output,
                             'diff --git a/a b/a\n'
                             'old file mode 0\n'
                             'new file mode 100644\n'
                             'index 0000000..c197bd8 100644\n'
                             '--- /dev/null\n'
                             '+++ b/a\n'
                             '@@ -0,0 +1 @@\n'
                             '+contents of a\n')
class SwitchScriptTests(TestCaseWithTransportAndScript):

    def test_switch_preserves(self):
        # See https://bugs.launchpad.net/brz/+bug/1820606
        self.run_script("""
$ brz init --git r
Created a standalone tree (format: git)
$ cd r
$ echo original > file.txt
$ brz add
adding file.txt
$ brz ci -q -m "Initial"
$ echo "entered on master branch" > file.txt
$ brz stat
modified:
  file.txt
$ brz switch -b other
2>Tree is up to date at revision 1.
2>Switched to branch other
$ cat file.txt
entered on master branch
""")

