import os


HERE = os.path.dirname(__file__)


def get_hook_dirs():
    return [HERE]


def get_test_dirs():
    return [os.path.join(HERE, 'tests')]
