import unittest

from TankTests import TankTestCase
import yandextank.core as tankcore


class CommonUtilsTest(TankTestCase):
    def setUp(self):
        self.stest = [
            ('5s', 5),
            ('1w1s', 604801),
            ('1w2d3h4m5s', 788645),
            ('1w2d3h4m6', 788646),
        ]
        self.mstest = [('1w2d3h4m5s6ms', 788645006), ('1w2d3h4m5s6', 788645006)]

    def test_expand_to_seconds(self):
        for i in self.stest:
            self.assertEqual(tankcore.expand_to_seconds(i[0]), i[1])

    def test_expand_to_seconds_fail(self):
        try:
            tankcore.expand_to_seconds("100n")
            raise RuntimeError("Exception expected")
        except ValueError, ex:
            # it's ok, we have excpected exception
            print ex


    def test_expand_to_milliseconds(self):
        for i in self.mstest:
            self.assertEqual(tankcore.expand_to_milliseconds(i[0]), i[1])


    def test_expand_to_milliseconds_fail(self):
        try:
            tankcore.expand_to_milliseconds("100n")
            raise RuntimeError("Exception expected")
        except ValueError, ex:
            # it's ok, we have excpected exception
            pass


if __name__ == '__main__':
    unittest.main()
