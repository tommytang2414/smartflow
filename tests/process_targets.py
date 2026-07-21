import time


def return_value(value):
    return value


def sleep_for(seconds):
    time.sleep(seconds)


def fail(message):
    raise ValueError(message)
