from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["xxhash"])
def test_xxh32(selenium):
    import xxhash

    assert xxhash.xxh32("a").intdigest() == 1426945110
    assert xxhash.xxh32("a", 0).intdigest() == 1426945110
    assert xxhash.xxh32("a", 1).intdigest() == 4111757423
    assert xxhash.xxh32("a", 2**32 - 1).intdigest() == 3443684653


@run_in_pyodide(packages=["xxhash"])
def test_xxh32_intdigest(selenium):
    import xxhash

    assert xxhash.xxh32_intdigest("a") == 1426945110
    assert xxhash.xxh32_intdigest("a", 0) == 1426945110
    assert xxhash.xxh32_intdigest("a", 1) == 4111757423
    assert xxhash.xxh32_intdigest("a", 2**32 - 1) == 3443684653


@run_in_pyodide(packages=["xxhash"])
def test_xxh32_update(selenium):
    import random

    import xxhash

    x = xxhash.xxh32()
    x.update("a")
    assert xxhash.xxh32("a").digest() == x.digest()
    assert xxhash.xxh32_digest("a") == x.digest()
    x.update("b")
    assert xxhash.xxh32("ab").digest() == x.digest()
    assert xxhash.xxh32_digest("ab") == x.digest()
    x.update("c")
    assert xxhash.xxh32("abc").digest() == x.digest()
    assert xxhash.xxh32_digest("abc") == x.digest()
    seed = random.randint(0, 2**32)
    x = xxhash.xxh32(seed=seed)
    x.update("a")
    assert xxhash.xxh32("a", seed).digest() == x.digest()
    assert xxhash.xxh32_digest("a", seed) == x.digest()
    x.update("b")
    assert xxhash.xxh32("ab", seed).digest() == x.digest()
    assert xxhash.xxh32_digest("ab", seed) == x.digest()
    x.update("c")
    assert xxhash.xxh32("abc", seed).digest() == x.digest()
    assert xxhash.xxh32_digest("abc", seed) == x.digest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh32_reset(selenium):
    import os

    import xxhash

    x = xxhash.xxh32()
    h = x.intdigest()
    for i in range(10, 50):
        x.update(os.urandom(i))
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh32_copy(selenium):
    import xxhash

    a = xxhash.xxh32()
    a.update("xxhash")
    b = a.copy()
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    b.update("xxhash")
    assert a.digest() != b.digest()
    assert a.intdigest() != b.intdigest()
    assert a.hexdigest() != b.hexdigest()
    a.update("xxhash")
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh32_overflow(selenium):
    import xxhash

    s = "I want an unsigned 32-bit seed!"
    a = xxhash.xxh32(s, seed=0)
    b = xxhash.xxh32(s, seed=2**32)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=0)
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=2**32)
    assert a.digest() == xxhash.xxh32_digest(s, seed=0)
    assert a.digest() == xxhash.xxh32_digest(s, seed=2**32)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=0)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=2**32)
    a = xxhash.xxh32(s, seed=1)
    b = xxhash.xxh32(s, seed=2**32 + 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=1)
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=2**32 + 1)
    assert a.digest() == xxhash.xxh32_digest(s, seed=1)
    assert a.digest() == xxhash.xxh32_digest(s, seed=2**32 + 1)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=1)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=2**32 + 1)
    a = xxhash.xxh32(s, seed=2**33 - 1)
    b = xxhash.xxh32(s, seed=2**34 - 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=2**33 - 1)
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=2**34 - 1)
    assert a.digest() == xxhash.xxh32_digest(s, seed=2**33 - 1)
    assert a.digest() == xxhash.xxh32_digest(s, seed=2**34 - 1)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=2**33 - 1)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=2**34 - 1)
    a = xxhash.xxh32(s, seed=2**65 - 1)
    b = xxhash.xxh32(s, seed=2**66 - 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=2**65 - 1)
    assert a.intdigest() == xxhash.xxh32_intdigest(s, seed=2**66 - 1)
    assert a.digest() == xxhash.xxh32_digest(s, seed=2**65 - 1)
    assert a.digest() == xxhash.xxh32_digest(s, seed=2**66 - 1)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=2**65 - 1)
    assert a.hexdigest() == xxhash.xxh32_hexdigest(s, seed=2**66 - 1)


@run_in_pyodide(packages=["xxhash"])
def test_xxh64(selenium):
    import xxhash

    assert xxhash.xxh64("a").intdigest() == 15154266338359012955
    assert xxhash.xxh64("a", 0).intdigest() == 15154266338359012955
    assert xxhash.xxh64("a", 1).intdigest() == 16051599287423682246
    assert xxhash.xxh64("a", 2**64 - 1).intdigest() == 6972758980737027682


@run_in_pyodide(packages=["xxhash"])
def test_xxh64_intdigest(selenium):
    import xxhash

    assert xxhash.xxh64_intdigest("a") == 15154266338359012955
    assert xxhash.xxh64_intdigest("a", 0) == 15154266338359012955
    assert xxhash.xxh64_intdigest("a", 1) == 16051599287423682246
    assert xxhash.xxh64_intdigest("a", 2**64 - 1) == 6972758980737027682


@run_in_pyodide(packages=["xxhash"])
def test_xxh64_update(selenium):
    import random

    import xxhash

    x = xxhash.xxh64()
    x.update("a")
    assert xxhash.xxh64("a").digest() == x.digest()
    assert xxhash.xxh64_digest("a") == x.digest()
    x.update("b")
    assert xxhash.xxh64("ab").digest() == x.digest()
    assert xxhash.xxh64_digest("ab") == x.digest()
    x.update("c")
    assert xxhash.xxh64("abc").digest() == x.digest()
    assert xxhash.xxh64_digest("abc") == x.digest()
    seed = random.randint(0, 2**64)
    x = xxhash.xxh64(seed=seed)
    x.update("a")
    assert xxhash.xxh64("a", seed).digest() == x.digest()
    assert xxhash.xxh64_digest("a", seed) == x.digest()
    x.update("b")
    assert xxhash.xxh64("ab", seed).digest() == x.digest()
    assert xxhash.xxh64_digest("ab", seed) == x.digest()
    x.update("c")
    assert xxhash.xxh64("abc", seed).digest() == x.digest()
    assert xxhash.xxh64_digest("abc", seed) == x.digest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh64_reset(selenium):
    import os

    import xxhash

    x = xxhash.xxh64()
    h = x.intdigest()
    for i in range(10, 50):
        x.update(os.urandom(i))
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh64_copy(selenium):
    import xxhash

    a = xxhash.xxh64()
    a.update("xxhash")
    b = a.copy()
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    b.update("xxhash")
    assert a.digest() != b.digest()
    assert a.intdigest() != b.intdigest()
    assert a.hexdigest() != b.hexdigest()
    a.update("xxhash")
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh64_overflow(selenium):
    import xxhash

    s = "I want an unsigned 64-bit seed!"
    a = xxhash.xxh64(s, seed=0)
    b = xxhash.xxh64(s, seed=2**64)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh64_intdigest(s, seed=0)
    assert a.intdigest() == xxhash.xxh64_intdigest(s, seed=2**64)
    assert a.digest() == xxhash.xxh64_digest(s, seed=0)
    assert a.digest() == xxhash.xxh64_digest(s, seed=2**64)
    assert a.hexdigest() == xxhash.xxh64_hexdigest(s, seed=0)
    assert a.hexdigest() == xxhash.xxh64_hexdigest(s, seed=2**64)
    a = xxhash.xxh64(s, seed=1)
    b = xxhash.xxh64(s, seed=2**64 + 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh64_intdigest(s, seed=1)
    assert a.intdigest() == xxhash.xxh64_intdigest(s, seed=2**64 + 1)
    assert a.digest() == xxhash.xxh64_digest(s, seed=1)
    assert a.digest() == xxhash.xxh64_digest(s, seed=2**64 + 1)
    assert a.hexdigest() == xxhash.xxh64_hexdigest(s, seed=1)
    assert a.hexdigest() == xxhash.xxh64_hexdigest(s, seed=2**64 + 1)
    a = xxhash.xxh64(s, seed=2**65 - 1)
    b = xxhash.xxh64(s, seed=2**66 - 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh64_intdigest(s, seed=2**65 - 1)
    assert a.intdigest() == xxhash.xxh64_intdigest(s, seed=2**66 - 1)
    assert a.digest() == xxhash.xxh64_digest(s, seed=2**65 - 1)
    assert a.digest() == xxhash.xxh64_digest(s, seed=2**66 - 1)
    assert a.hexdigest() == xxhash.xxh64_hexdigest(s, seed=2**65 - 1)
    assert a.hexdigest() == xxhash.xxh64_hexdigest(s, seed=2**66 - 1)


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128(selenium):
    import xxhash

    assert xxhash.xxh3_128("a").intdigest() == 225219434562328483135862406050043285023
    assert (
        xxhash.xxh3_128("a", 0).intdigest() == 225219434562328483135862406050043285023
    )
    assert (
        xxhash.xxh3_128("a", 1).intdigest() == 337425133163118381928709500770786453280
    )
    assert (
        xxhash.xxh3_128("a", 2**64 - 1).intdigest()
        == 198297796855923085494266857744987477846
    )


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_intdigest(selenium):
    import xxhash

    assert xxhash.xxh3_128_intdigest("a") == 225219434562328483135862406050043285023
    assert xxhash.xxh3_128_intdigest("a", 0) == 225219434562328483135862406050043285023
    assert xxhash.xxh3_128_intdigest("a", 1) == 337425133163118381928709500770786453280
    assert (
        xxhash.xxh3_128_intdigest("a", 2**64 - 1)
        == 198297796855923085494266857744987477846
    )


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_update(selenium):
    import random

    import xxhash

    x = xxhash.xxh3_128()
    x.update("a")
    assert xxhash.xxh3_128("a").digest() == x.digest()
    assert xxhash.xxh3_128_digest("a") == x.digest()
    x.update("b")
    assert xxhash.xxh3_128("ab").digest() == x.digest()
    assert xxhash.xxh3_128_digest("ab") == x.digest()
    x.update("c")
    assert xxhash.xxh3_128("abc").digest() == x.digest()
    assert xxhash.xxh3_128_digest("abc") == x.digest()
    seed = random.randint(0, 2**64)
    x = xxhash.xxh3_128(seed=seed)
    x.update("a")
    assert xxhash.xxh3_128("a", seed).digest() == x.digest()
    assert xxhash.xxh3_128_digest("a", seed) == x.digest()
    x.update("b")
    assert xxhash.xxh3_128("ab", seed).digest() == x.digest()
    assert xxhash.xxh3_128_digest("ab", seed) == x.digest()
    x.update("c")
    assert xxhash.xxh3_128("abc", seed).digest() == x.digest()
    assert xxhash.xxh3_128_digest("abc", seed) == x.digest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_reset(selenium):
    import xxhash

    x = xxhash.xxh3_128()
    h = x.intdigest()
    x.update("x" * 10240)
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_seed_reset(selenium):
    import random

    import xxhash

    seed = random.randint(0, 2**64 - 1)
    x = xxhash.xxh3_128(seed=seed)
    h = x.intdigest()
    x.update("x" * 10240)
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_reset_more(selenium):
    import os
    import random

    import xxhash

    x = xxhash.xxh3_128()
    h = x.intdigest()
    for _ in range(random.randint(100, 200)):
        x.reset()
    for i in range(10, 1000):
        x.update(os.urandom(i))
    x.reset()
    assert h == x.intdigest()
    for _ in range(10, 1000):
        x.update(os.urandom(100))
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_seed_reset_more(selenium):
    import os
    import random

    import xxhash

    seed = random.randint(0, 2**64 - 1)
    x = xxhash.xxh3_128(seed=seed)
    h = x.intdigest()
    for _ in range(random.randint(100, 200)):
        x.reset()
    for i in range(10, 1000):
        x.update(os.urandom(i))
    x.reset()
    assert h == x.intdigest()
    for _ in range(10, 1000):
        x.update(os.urandom(100))
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_copy(selenium):
    import xxhash

    a = xxhash.xxh3_128()
    a.update("xxhash")
    b = a.copy()
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    b.update("xxhash")
    assert a.digest() != b.digest()
    assert a.intdigest() != b.intdigest()
    assert a.hexdigest() != b.hexdigest()
    a.update("xxhash")
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_128_overflow(selenium):
    import xxhash

    s = "I want an unsigned 64-bit seed!"
    a = xxhash.xxh3_128(s, seed=0)
    b = xxhash.xxh3_128(s, seed=2**64)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh3_128_intdigest(s, seed=0)
    assert a.intdigest() == xxhash.xxh3_128_intdigest(s, seed=2**64)
    assert a.digest() == xxhash.xxh3_128_digest(s, seed=0)
    assert a.digest() == xxhash.xxh3_128_digest(s, seed=2**64)
    assert a.hexdigest() == xxhash.xxh3_128_hexdigest(s, seed=0)
    assert a.hexdigest() == xxhash.xxh3_128_hexdigest(s, seed=2**64)
    a = xxhash.xxh3_128(s, seed=1)
    b = xxhash.xxh3_128(s, seed=2**64 + 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh3_128_intdigest(s, seed=1)
    assert a.intdigest() == xxhash.xxh3_128_intdigest(s, seed=2**64 + 1)
    assert a.digest() == xxhash.xxh3_128_digest(s, seed=1)
    assert a.digest() == xxhash.xxh3_128_digest(s, seed=2**64 + 1)
    assert a.hexdigest() == xxhash.xxh3_128_hexdigest(s, seed=1)
    assert a.hexdigest() == xxhash.xxh3_128_hexdigest(s, seed=2**64 + 1)
    a = xxhash.xxh3_128(s, seed=2**65 - 1)
    b = xxhash.xxh3_128(s, seed=2**66 - 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh3_128_intdigest(s, seed=2**65 - 1)
    assert a.intdigest() == xxhash.xxh3_128_intdigest(s, seed=2**66 - 1)
    assert a.digest() == xxhash.xxh3_128_digest(s, seed=2**65 - 1)
    assert a.digest() == xxhash.xxh3_128_digest(s, seed=2**66 - 1)
    assert a.hexdigest() == xxhash.xxh3_128_hexdigest(s, seed=2**65 - 1)
    assert a.hexdigest() == xxhash.xxh3_128_hexdigest(s, seed=2**66 - 1)


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64(selenium):
    import xxhash

    assert xxhash.xxh3_64("a").intdigest() == 16629034431890738719
    assert xxhash.xxh3_64("a", 0).intdigest() == 16629034431890738719
    assert xxhash.xxh3_64("a", 1).intdigest() == 15201566949650179872
    assert xxhash.xxh3_64("a", 2**64 - 1).intdigest() == 4875116479388997462


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_intdigest(selenium):
    import xxhash

    assert xxhash.xxh3_64_intdigest("a") == 16629034431890738719
    assert xxhash.xxh3_64_intdigest("a", 0) == 16629034431890738719
    assert xxhash.xxh3_64_intdigest("a", 1) == 15201566949650179872
    assert xxhash.xxh3_64_intdigest("a", 2**64 - 1) == 4875116479388997462


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_update(selenium):
    import random

    import xxhash

    x = xxhash.xxh3_64()
    x.update("a")
    assert xxhash.xxh3_64("a").digest() == x.digest()
    assert xxhash.xxh3_64_digest("a") == x.digest()
    x.update("b")
    assert xxhash.xxh3_64("ab").digest() == x.digest()
    assert xxhash.xxh3_64_digest("ab") == x.digest()
    x.update("c")
    assert xxhash.xxh3_64("abc").digest() == x.digest()
    assert xxhash.xxh3_64_digest("abc") == x.digest()
    seed = random.randint(0, 2**64)
    x = xxhash.xxh3_64(seed=seed)
    x.update("a")
    assert xxhash.xxh3_64("a", seed).digest() == x.digest()
    assert xxhash.xxh3_64_digest("a", seed) == x.digest()
    x.update("b")
    assert xxhash.xxh3_64("ab", seed).digest() == x.digest()
    assert xxhash.xxh3_64_digest("ab", seed) == x.digest()
    x.update("c")
    assert xxhash.xxh3_64("abc", seed).digest() == x.digest()
    assert xxhash.xxh3_64_digest("abc", seed) == x.digest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_reset(selenium):
    import xxhash

    x = xxhash.xxh3_64()
    h = x.intdigest()
    x.update("x" * 10240)
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_seed_reset(selenium):
    import random

    import xxhash

    seed = random.randint(0, 2**64 - 1)
    x = xxhash.xxh3_64(seed=seed)
    h = x.intdigest()
    x.update("x" * 10240)
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_reset_more(selenium):
    import os
    import random

    import xxhash

    x = xxhash.xxh3_64()
    h = x.intdigest()
    for _ in range(random.randint(100, 200)):
        x.reset()
    assert h == x.intdigest()
    for i in range(10, 1000):
        x.update(os.urandom(i))
    x.reset()
    assert h == x.intdigest()
    for _ in range(10, 1000):
        x.update(os.urandom(100))
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_seed_reset_more(selenium):
    import os
    import random

    import xxhash

    seed = random.randint(0, 2**64 - 1)
    x = xxhash.xxh3_64(seed=seed)
    h = x.intdigest()
    for _ in range(random.randint(100, 200)):
        x.reset()
    assert h == x.intdigest()
    for i in range(10, 1000):
        x.update(os.urandom(i))
    x.reset()
    assert h == x.intdigest()
    for _ in range(10, 1000):
        x.update(os.urandom(100))
    x.reset()
    assert h == x.intdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_copy(selenium):
    import xxhash

    a = xxhash.xxh3_64()
    a.update("xxhash")
    b = a.copy()
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    b.update("xxhash")
    assert a.digest() != b.digest()
    assert a.intdigest() != b.intdigest()
    assert a.hexdigest() != b.hexdigest()
    a.update("xxhash")
    assert a.digest() == b.digest()
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()


@run_in_pyodide(packages=["xxhash"])
def test_xxh3_64_overflow(selenium):
    import xxhash

    s = "I want an unsigned 64-bit seed!"
    a = xxhash.xxh3_64(s, seed=0)
    b = xxhash.xxh3_64(s, seed=2**64)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh3_64_intdigest(s, seed=0)
    assert a.intdigest() == xxhash.xxh3_64_intdigest(s, seed=2**64)
    assert a.digest() == xxhash.xxh3_64_digest(s, seed=0)
    assert a.digest() == xxhash.xxh3_64_digest(s, seed=2**64)
    assert a.hexdigest() == xxhash.xxh3_64_hexdigest(s, seed=0)
    assert a.hexdigest() == xxhash.xxh3_64_hexdigest(s, seed=2**64)
    a = xxhash.xxh3_64(s, seed=1)
    b = xxhash.xxh3_64(s, seed=2**64 + 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh3_64_intdigest(s, seed=1)
    assert a.intdigest() == xxhash.xxh3_64_intdigest(s, seed=2**64 + 1)
    assert a.digest() == xxhash.xxh3_64_digest(s, seed=1)
    assert a.digest() == xxhash.xxh3_64_digest(s, seed=2**64 + 1)
    assert a.hexdigest() == xxhash.xxh3_64_hexdigest(s, seed=1)
    assert a.hexdigest() == xxhash.xxh3_64_hexdigest(s, seed=2**64 + 1)
    a = xxhash.xxh3_64(s, seed=2**65 - 1)
    b = xxhash.xxh3_64(s, seed=2**66 - 1)
    assert a.seed == b.seed
    assert a.intdigest() == b.intdigest()
    assert a.hexdigest() == b.hexdigest()
    assert a.digest() == b.digest()
    assert a.intdigest() == xxhash.xxh3_64_intdigest(s, seed=2**65 - 1)
    assert a.intdigest() == xxhash.xxh3_64_intdigest(s, seed=2**66 - 1)
    assert a.digest() == xxhash.xxh3_64_digest(s, seed=2**65 - 1)
    assert a.digest() == xxhash.xxh3_64_digest(s, seed=2**66 - 1)
    assert a.hexdigest() == xxhash.xxh3_64_hexdigest(s, seed=2**65 - 1)
    assert a.hexdigest() == xxhash.xxh3_64_hexdigest(s, seed=2**66 - 1)
