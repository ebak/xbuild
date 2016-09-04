import unittest
from mockfs import MockFS
from xbuild.fs import joinPath, Cleaner


class Test(unittest.TestCase):

    def test0(self):
        def fileCheck(*fpaths):
            for fpath in fpaths:
                self.assertTrue(fs.exists(fpath))
                self.assertTrue(fs.isfile(fpath))
                self.assertFalse(fs.isdir(fpath))

        def dirCheck(*fpaths):
            for fpath in fpaths:
                self.assertTrue(fs.exists(fpath))
                self.assertFalse(fs.isfile(fpath))
                self.assertTrue(fs.isdir(fpath))
            
        fs = MockFS()
        self.assertFalse(fs.exists('src/math/vector.c'))
        self.assertFalse(fs.isfile('src/math/vector.c'))
        self.assertFalse(fs.isdir('src/math/vector.c'))
        fs.mkdirs('src/math/utils')
        fs.write('README.txt', 'hello')
        self.assertEquals('hello', fs.read('README.txt'))
        fs.write('README.txt', 'Hello!')
        self.assertEquals('Hello!', fs.read('README.txt'))
        fs.write('src/main.c', '// main')
        self.assertEquals('// main', fs.read('src/main.c'))
        try:
            fs.mkdirs('src/main.c/utils')
            self.fail()
        except:
            pass
        print fs.show()
        fileCheck('README.txt', 'src/main.c')
        dirCheck('', 'src', 'src/math', 'src/math/', 'src/math/utils')

    def testRemove(self):
        fs = MockFS()
        fs.write('src/petymeg/pupak.c', 'Hello', mkDirs=True)
        fs.write('src/petymeg/piroska.c', 'Bello', mkDirs=True)
        self.assertTrue(fs.isfile('src/petymeg/pupak.c'))
        self.assertTrue(fs.isfile('src/petymeg/piroska.c'))
        self.assertTrue(fs.isdir('src/petymeg/'))
        self.assertTrue(fs.isdir('src'))
        fs.remove('src/petymeg/pupak.c')
        self.assertFalse(fs.isfile('src/petymeg/pupak.c'))
        self.assertTrue(fs.isfile('src/petymeg/piroska.c'))
        self.assertTrue(fs.isdir('src/petymeg/'))
        self.assertTrue(fs.isdir('src'))

    def testRmDir(self):
        fs = MockFS()
        fs.mkdirs('src/petymeg/pupak')
        fs.mkdirs('src/hallo/csocsi')
        self.assertTrue(fs.isdir('src/petymeg/pupak'))
        fs.rmdir('src/petymeg/pupak')
        fs.rmdir('src/hallo/csocsi')
        print fs.show()
    
    # TODO: move to test_fs.py
    def testTokenizePath(self):
        fs = MockFS()
        
        def check(fpath, refTokens):
            tokens = fs.tokenizePath(fpath)
            print '{} -> {}'.format(fpath, tokens)
            self.assertListEqual(refTokens, tokens)

        check('/home/endre/cucc', ['/home', 'endre', 'cucc'])
        check('endre/cucc', ['endre', 'cucc'])
        check('', [])
        check('.', [])
        check('/', ['/'])
        check('/file1.txt', ['/file1.txt'])
        check('\\', [])
        check(r'C:\Users\ebak\picea\readme.txt', ['C:/Users', 'ebak', 'picea', 'readme.txt'])
        check(r'C:\Users\ebak\picea/readme.txt', ['C:/Users', 'ebak', 'picea', 'readme.txt'])

    # TODO: move to test_fs.py
    def testJoinPath(self):
        fs = MockFS()
        
        def check(rpath, *tokens):
            fpath = fs.joinPath(*tokens)
            print '{} -> {}'.format(tokens, fpath)
            self.assertEqual(rpath, fpath)

        check('', '')
        check('/', '/')
        check('/home', '/', 'home')
        check('c:/users/ebak', 'c:', 'users', 'ebak')
        check('/home/endre/stuff', '/home', 'endre', 'stuff')

 
class CleanerTest(unittest.TestCase):

    def buildFsTree(self, maxDepth=3, dirLeafs=3, fileLeafs=3):
        fs = MockFS()
        dirPaths, filePaths = set(), set()

        def fillDir(dirPath, depth):
            for fn in range(fileLeafs):
                fpath = joinPath(dirPath, 'file{}.txt'.format(fn))
                fs.write(fpath, 'file {} content\n'.format(fn))
                filePaths.add(fpath)
            if depth < maxDepth:
                subDepth =  depth + 1
                for dn in range(dirLeafs):
                    subDirPath = joinPath(dirPath, 'dir{}'.format(dn))
                    dirPaths.add(subDirPath)
                    fs.mkdirs(subDirPath)
                    fillDir(subDirPath, subDepth)
        fillDir('/', 0)
        return fs, dirPaths, filePaths

    def checkFS(self, fs, fPaths, rmfPaths, dPaths, rmdPaths):
        for fPath in fPaths:
            if fPath in rmfPaths:
                self.assertFalse(fs.isfile(fPath))
                self.assertFalse(fs.isdir(fPath))
            else:
                self.assertTrue(fs.isfile(fPath), 'fPath={}'.format(fPath))
                self.assertFalse(fs.isdir(fPath))
        for dPath in dPaths:
            if dPath in rmdPaths:
                self.assertFalse(fs.isfile(dPath))
                self.assertFalse(fs.isdir(dPath))
            else:
                self.assertFalse(fs.isfile(dPath))
                self.assertTrue(fs.isdir(dPath))
            
    def testCleanOneFile(self):
        fs, dPaths, fPaths = self.buildFsTree()
        # print fs.show()
        cleaner = Cleaner(fs, absPaths=['/dir0/dir0/dir0/file0.txt'])
        rmdirs, rmfiles = cleaner.clean()
        self.assertListEqual([], rmdirs)
        self.assertListEqual(['/dir0/dir0/dir0/file0.txt'], rmfiles)
        self.checkFS(
            fs,
            fPaths,
            ['/dir0/dir0/dir0/file0.txt'],
            dPaths,
            [])

    def testCleanDirByFiles(self):
        fs, dPaths, fPaths = self.buildFsTree()
        cleaner = Cleaner(fs, absPaths=['/dir0/dir0/dir0/file0.txt', '/dir0/dir0/dir0/file1.txt', '/dir0/dir0/dir0/file2.txt'])
        rmdirs, rmfiles = cleaner.clean()
        self.assertListEqual(['/dir0/dir0/dir0'], rmdirs)
        self.assertListEqual([], rmfiles)
        self.checkFS(
            fs,
            fPaths,
            ['/dir0/dir0/dir0/file0.txt', '/dir0/dir0/dir0/file1.txt', '/dir0/dir0/dir0/file2.txt'],
            dPaths,
            ['/dir0/dir0/dir0'])

    def testCleanDir(self):
        fs, dPaths, fPaths = self.buildFsTree()
        cleaner = Cleaner(fs, absDirPaths=['/dir0/dir0/dir0'])
        rmdirs, rmfiles = cleaner.clean()
        self.assertListEqual(['/dir0/dir0/dir0'], rmdirs)
        self.assertListEqual([], rmfiles)
        self.checkFS(
            fs,
            fPaths,
            ['/dir0/dir0/dir0/file0.txt', '/dir0/dir0/dir0/file1.txt', '/dir0/dir0/dir0/file2.txt'],
            dPaths,
            ['/dir0/dir0/dir0'])