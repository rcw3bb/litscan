"""Module docstring with 'excluded_module' value."""

MODULE_STR = "module_string"
MODULE_NUM = 100


def my_func() -> str:
    """Function docstring."""
    x = "func_string"
    n = 42
    return x


class MyClass:
    class_var = "class_var"

    def method(self) -> None:
        """Method docstring."""
        msg = "method_string"
        count = 7


async def async_func() -> None:
    """Async function docstring."""
    value = "async_string"
    num = 55
