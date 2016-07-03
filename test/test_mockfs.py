import unittest
from mockfs import MockFS


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
