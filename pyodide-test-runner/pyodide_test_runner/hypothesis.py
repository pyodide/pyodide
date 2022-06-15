import pickle
from zoneinfo import ZoneInfo

from hypothesis import HealthCheck, settings, strategies


def is_picklable(x):
    try:
        pickle.dumps(x)
        return True
    except Exception:
        return False


def is_equal_to_self(x):
    try:
        return x == x
    except Exception:
        return False


try:
    from exceptiongroup import ExceptionGroup
except ImportError:

    class ExceptionGroup:
        pass


# Generate an object of any type
any_strategy = (
    strategies.from_type(type)
    .flatmap(strategies.from_type)
    .filter(lambda x: not isinstance(x, ZoneInfo))
    .filter(is_picklable)
    .filter(lambda x: not isinstance(x, ExceptionGroup))
)

any_equal_to_self_strategy = any_strategy.filter(is_equal_to_self)

std_hypothesis_settings = settings(
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def is_picklable(x):
    try:
        pickle.dumps(x)
        return True
    except Exception:
        return False


strategy = (
    strategies.from_type(type)
    .flatmap(strategies.from_type)
    .filter(lambda x: not isinstance(x, ZoneInfo))
    .filter(is_picklable)
)
