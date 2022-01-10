import rust
from timeit import default_timer as timer
from pydantic import BaseModel

# multiply
result = rust.multiply(2, 3)
print(result)

# sum of list of numbers:
def sum_list(numbers: list) -> int:
    total = 0
    for number in numbers:
        total += number
    return total


result = rust.list_sum([10, 10, 10, 10, 10])
print(result)


# Working with different types:

# word printer:
rust.word_printer("hello", 3, False, True)
rust.word_printer("eyb", 3, True, False)

# print a list of strings to console
a_list = ["one", "two", "three"]
rust.vector_printer(a_list)

another_list = ["1", "2", "3", "4", "5", "6", "7", "8"]
rust.array_printer(another_list)

# print a dictionary to console:
a_dict = {
    "key 1": "value 1",
    "key 2": "value 2",
    "key 3": "value 3",
    "key 4": "value 4",
}

rust.dict_printer(a_dict)

# the following two functions will fail because 'dict_printer'
#  is expecting a dict with string keys and string values:
try:
    rust.dict_printer("wrong type")
except TypeError as e:
    print(f"Caught a type error: {e}")

try:
    rust.dict_printer({"a": 1, "b": 2})
except TypeError as e:
    print(f"Caught a type error: {e}")


# count occurrences of a word in a string:
def count_occurences(contents: str, needle: str) -> int:
    total = 0
    for line in contents.splitlines():
        for word in line.split(" "):
            if word == needle or word == needle + ".":
                total += 1
    return total


text = (
    """🐍 searches through the words. Here are some additional words for 🐍.\nSome words\n"""
    * 1000
)


res = count_occurences(text, "words")
print("count_occurences for 'words' in Python:", res)

rust_res = rust.count_occurences(text, "words")
print("count_occurences for 'words' in Rust:", rust_res)

start = timer()
res = count_occurences(text, "🐍")
elapsed = round(timer() - start, 10)
print(f"count_occurences for '🐍' in Python took {elapsed}. Result: {res}")

start = timer()
rust_res = rust.count_occurences(text, "🐍")
elapsed = round(timer() - start, 10)
print(f"count_occurences for '🐍' in Python took {elapsed}. Result: {rust_res}")

# Calculating fibonacci
from fib import get_fibonacci

print(f"Fibonacci number in Python and in Rust:")
for i in range(10):
    res_python = get_fibonacci(i)
    res_rust = rust.get_fibonacci(i)
    print(f"number{i}:\t{res_python}\tand in Rust: {res_rust}")


py_start = timer()
for i in range(999):
    get_fibonacci(150)

py_res = get_fibonacci(150)
py_elapsed = round(timer() - py_start, 5)
ru_start = timer()
for i in range(999):
    rust.get_fibonacci(150)

ru_res = rust.get_fibonacci(150)
ru_elapsed = round(timer() - ru_start, 5)
print("Calculating the 150th fibonacci number 1000 times.")
print(f"Python took {py_elapsed} seconds and got:\t{py_res}.")
print(f"Rust took {ru_elapsed} seconds and got:\t{ru_res}.")

# Using a struct that is defined in Rust, a struct called RustStruct:
rust_struct = rust.RustStruct(data="some data", vector=[255, 255, 255])

# Calling some methods on the struct:
rust_struct.extend_vector([1, 1, 1, 1])
rust_struct.printer()


# sending over a Pydantic basemodel:
class Human(BaseModel):
    name: str
    age: int


jan = Human(name="Jan", age=6)
rust.human_says_hi(jan.json())

# Have Rust use the Python logger:
import logging

FORMAT = "%(levelname)s %(name)s %(asctime)-15s %(filename)s:%(lineno)d %(message)s"
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logging.info("Logging from the Python code")
rust.log_example()
rust.log_different_levels()

# 'handle' a Rust error in Python by catching the exception:
print(rust.greater_than_2(3))
try:
    print(rust.greater_than_2(1))
except Exception as e:
    print(f"Caught an exception: {e}")
    print(type(e))
print("Still going strong.")
