from MonCollector.agent.metric.custom import Custom
import time
import unittest

class  Custom_TestCase(unittest.TestCase):
    def setUp(self):
        pass
    #def tearDown(self):
    #    self.foo.dispose()
    #    self.foo = None

    def test_custom_(self):
        custom_config = {'tail': [], 'call': ['ZGlmZkV4:aWZjb25maWcgLXMgZXRoMCB8IGF3ayAnJDE9PSJldGgwIiB7cHJpbnQgJDR9Jw==:1']}
        self.foo = Custom(**custom_config)

        #self.assertEqual(x, y, "Msg");
        x = self.foo.check()
        print x
        self.assertEquals(["0"], x)
        time.sleep(1)
        y = self.foo.check()
        print y
        assert x != y;
        time.sleep(0.5)
        print self.foo.check()
        
    def test_custom_nodiff(self):
        custom_config = {'tail': [], 'call': ['ZGlmZkV4:aWZjb25maWcgLXMgZXRoMCB8IGF3ayAnJDE9PSJldGgwIiB7cHJpbnQgJDR9Jw==:0']}
        self.foo = Custom(**custom_config)

        x = self.foo.check()
        print "second test", x
        self.assertNotEquals(["0.0"], x)
        time.sleep(1)
        y = self.foo.check()
        print y
        assert x < y;
        time.sleep(0.5)
        z = self.foo.check()
        print z
        assert z > y;
        
    def test_custom_fail(self):
        custom_config = {'tail': [], 'call': ['cXVlcnkgY291bnQ=:cXVlcnlfY2xhc3NpZnlfY2xpZW50IGZzdGF0cyB8IGdyZXAgY2xhc3MtY21kIHwgY3V0IC1mIDM=:1']}
        self.foo = Custom(**custom_config)

        x = self.foo.check()
        
    def test_custom_fail2(self):
        custom_config = {'tail': [], 'call': ['TnVtUGhyYXNlcw==:Y2F0IC92YXIvdG1wL3N0YXQx:0']}
        self.foo = Custom(**custom_config)

        x = self.foo.check()

if __name__ == '__main__':
    unittest.main()

