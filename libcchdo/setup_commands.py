import os
import sys
import distutils.core
import shutil


# DIRECTORY is the absolute path to the directory that contains setup.py
DIRECTORY = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


PACKAGE_NAME = 'libcchdo'


COVERAGE_PATH = os.path.join(DIRECTORY, 'doc', 'coverage')


class TestCommand(distutils.core.Command):
    """http://da44en.wordpress.com/2002/11/22/using-distutils/"""
    description = "Runs tests"
    user_options = []

    def initialize_options(self):
        self._dir = os.path.join(DIRECTORY, PACKAGE_NAME)
        sys.path.insert(0, self._dir)

    def finalize_options(self):
        pass

    def run(self):
        """Finds all the tests modules in tests/ and runs them."""
        testdir = 'tests'
        testfiles = []
        verbosity = 2

        globbed = glob.glob(os.path.join(self._dir, testdir, '*.py'))
        del globbed[globbed.index(os.path.join(self._dir, testdir, '__init__.py'))]
        for t in globbed:
            testfiles.append(
                '.'.join((PACKAGE_NAME, testdir,
                          os.path.splitext(os.path.basename(t))[0])))

        tests = unittest.TestSuite()
        for t in testfiles:
        	__import__(t)
        	tests.addTests(
        	    unittest.defaultTestLoader.loadTestsFromModule(sys.modules[t]))

        unittest.TextTestRunner(verbosity=verbosity).run(tests)
        del sys.path[0]


class CoverageCommand(TestCommand):
    """Check test coverage
       API for coverage-python:
       http://nedbatchelder.com/code/coverage/api.html
    """
    description = "Check test coverage"
    user_options = []

    def initialize_options(self):
        # distutils.core.Command is an old-style class.
        TestCommand.initialize_options(self)

        if '.coverage' in os.listdir(self._dir):
            os.unlink('.coverage')

    def finalize_options(self):
        pass

    def run(self):
        import coverage
        self.cov = coverage.coverage()
        self.cov.start()
        TestCommand.run(self)
        self.cov.stop()
        self.cov.save()
        # Somehow os gets set to None.
        import os
        self.cov.report(file=sys.stdout)
        self.cov.html_report(directory=COVERAGE_PATH)
        # Somehow os gets set to None.
        import os
        print os.path.join(COVERAGE_PATH, 'index.html')


class CleanCommand(distutils.core.Command):
    description = "Cleans directories of .pyc files and documentation"
    user_options = []

    def initialize_options(self):
        self._clean_me = []
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.endswith('.pyc'):
                    self._clean_me.append(os.path.join(root, f))

    def finalize_options(self):
        print "Clean."

    def run(self):
        for clean_me in self._clean_me:
            try:
                os.unlink(clean_me)
            except:
                pass


class PurgeCommand(CleanCommand):
    description = "Purges directories of .pyc files, caches, and documentation"
    user_options = []

    def initialize_options(self):
        CleanCommand.initialize_options(self)

    def finalize_options(self):
        print "Purged."

    def run(self):
        doc_dir = os.path.join(DIRECTORY, 'doc')
        if os.path.isdir(doc_dir):
        	shutil.rmtree(doc_dir)

        build_dir = os.path.join(DIRECTORY, 'build')
        if os.path.isdir(build_dir):
        	shutil.rmtree(build_dir)

        dist_dir = os.path.join(DIRECTORY, 'dist')
        if os.path.isdir(dist_dir):
        	shutil.rmtree(dist_dir)

        CleanCommand.run(self)


class ProfileCommand(distutils.core.Command):
    description = "Run profiler on a test script"
    user_options = [('file=', 'f', 'A file to profile (required)'), ]

    def initialize_options(self):
        self.file = None

    def finalize_options(self):
        pass

    def run(self):
        if not self.file:
            print >>sys.stderr, ('Please give a file to profile: '
                                 'setup.py profile --file=path/to/file')
            return 1

        import cProfile
        cProfile.run("import imp;imp.load_source('_', '%s')" % self.file)


class REPLCommand(distutils.core.Command):
    description = "Launch a REPL with the library loaded"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import code
        import readline
        console = code.InteractiveConsole()
        map(console.runsource, """\
import sys
import os
import libcchdo as L
import libcchdo.db.model.legacy as DBML
import libcchdo.db.model.convert as DBMC
import libcchdo.db.model.std as STD
#"FIND = L.db.parameters.find_by_mnemonic

#"f = open(os.path.join(mpath, 'testfiles/hy1/i05_33RR20090320_hy1.csv')
#"f = open(os.path.join(mpath, 'testfiles/hy1/p16s_hy1.csv')
#"f = open(os.path.join(mpath, 'testfiles/hy1/tenline_hy1.csv')

#"import cProfile
#"cProfile.run('x = file_to_botdb.convert(d)', 'convert.profile')
#"print 'x = ', x
""".split('\n'))
        console.interact('db: DBML <- DBMC -> STD')


class TestCommand(distutils.core.Command):
    """http://da44en.wordpress.com/2002/11/22/using-distutils/"""
    description = "Runs tests"
    user_options = []

    def initialize_options(self):
        self._dir = os.path.join(DIRECTORY, PACKAGE_NAME)
        sys.path.insert(0, self._dir)

    def finalize_options(self):
        pass

    def run(self):
        """Finds all the tests modules in tests/ and runs them."""
        testdir = 'tests'
        testfiles = []
        verbosity = 2

        globbed = glob.glob(os.path.join(self._dir, testdir, '*.py'))
        del globbed[globbed.index(os.path.join(self._dir, testdir, '__init__.py'))]
        for t in globbed:
            testfiles.append(
                '.'.join((PACKAGE_NAME, testdir,
                          os.path.splitext(os.path.basename(t))[0])))

        tests = unittest.TestSuite()
        for t in testfiles:
        	__import__(t)
        	tests.addTests(
        	    unittest.defaultTestLoader.loadTestsFromModule(sys.modules[t]))

        unittest.TextTestRunner(verbosity=verbosity).run(tests)
        del sys.path[0]


class CoverageCommand(TestCommand):
    """Check test coverage
       API for coverage-python:
       http://nedbatchelder.com/code/coverage/api.html
    """
    description = "Check test coverage"
    user_options = []

    def initialize_options(self):
        # distutils.core.Command is an old-style class.
        TestCommand.initialize_options(self)

        if '.coverage' in os.listdir(self._dir):
            os.unlink('.coverage')

    def finalize_options(self):
        pass

    def run(self):
        import coverage
        self.cov = coverage.coverage()
        self.cov.start()
        TestCommand.run(self)
        self.cov.stop()
        self.cov.save()
        # Somehow os gets set to None.
        import os
        self.cov.report(file=sys.stdout)
        self.cov.html_report(directory=COVERAGE_PATH)
        # Somehow os gets set to None.
        import os
        print os.path.join(COVERAGE_PATH, 'index.html')


class CleanCommand(distutils.core.Command):
    description = "Cleans directories of .pyc files and documentation"
    user_options = []

    def initialize_options(self):
        self._clean_me = []
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.endswith('.pyc'):
                    self._clean_me.append(os.path.join(root, f))

    def finalize_options(self):
        print "Clean."

    def run(self):
        for clean_me in self._clean_me:
            try:
                os.unlink(clean_me)
            except:
                pass


class PurgeCommand(CleanCommand):
    description = "Purges directories of .pyc files, caches, and documentation"
    user_options = []

    def initialize_options(self):
        CleanCommand.initialize_options(self)

    def finalize_options(self):
        print "Purged."

    def run(self):
        doc_dir = os.path.join(DIRECTORY, 'doc')
        if os.path.isdir(doc_dir):
        	shutil.rmtree(doc_dir)

        build_dir = os.path.join(DIRECTORY, 'build')
        if os.path.isdir(build_dir):
        	shutil.rmtree(build_dir)

        dist_dir = os.path.join(DIRECTORY, 'dist')
        if os.path.isdir(dist_dir):
        	shutil.rmtree(dist_dir)

        CleanCommand.run(self)


class ProfileCommand(distutils.core.Command):
    description = "Run profiler on a test script"
    user_options = [('file=', 'f', 'A file to profile (required)'), ]

    def initialize_options(self):
        self.file = None

    def finalize_options(self):
        pass

    def run(self):
        if not self.file:
            print >>sys.stderr, ('Please give a file to profile: '
                                 'setup.py profile --file=path/to/file')
            return 1

        import cProfile
        cProfile.run("import imp;imp.load_source('_', '%s')" % self.file)


class REPLCommand(distutils.core.Command):
    description = "Launch a REPL with the library loaded"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import code
        import readline
        console = code.InteractiveConsole()
        map(console.runsource, """\
import sys
import os
import libcchdo as L
import libcchdo.db.model.legacy as DBML
import libcchdo.db.model.convert as DBMC
import libcchdo.db.model.std as STD
#"FIND = L.db.parameters.find_by_mnemonic

#"f = open(os.path.join(mpath, 'testfiles/hy1/i05_33RR20090320_hy1.csv')
#"f = open(os.path.join(mpath, 'testfiles/hy1/p16s_hy1.csv')
#"f = open(os.path.join(mpath, 'testfiles/hy1/tenline_hy1.csv')

#"import cProfile
#"cProfile.run('x = file_to_botdb.convert(d)', 'convert.profile')
#"print 'x = ', x
""".split('\n'))
        console.interact('db: DBML <- DBMC -> STD')



