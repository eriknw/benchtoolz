from itertools import repeat


def zeros_imul(n):
    l = [0]
    l *= n
    return l


def zeros_mul(n):
    return n * [0]


def zeros_repeat(n):
    return list(repeat(0, n))


def zeros_slow(n):
    return [0 for _ in range(n)]
