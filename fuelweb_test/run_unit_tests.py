import os
import sys
import unittest

sys.path.insert(0,
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if __name__ == '__main__':
    from unit_tests.models.test_environment import TestEnvironment

    suite = unittest.TestSuite()
    suite.addTest(TestEnvironment('test_cdrom_keys'))
    suite.addTest(TestEnvironment('test_usb_keys'))
    unittest.TextTestRunner(verbosity=2).run(suite)
