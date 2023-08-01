import re


def natural_key(string: str) -> list:
    """Return key for string natural sort

    Args:
        string (str): Input string

    Returns:
        list: Sort key
    """
    return [int(s) if s.isdecimal() else s for s in re.split(r"(\d+)", string)]
