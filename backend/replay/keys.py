def pair_key(pair: tuple[str, str]) -> str:
    return "|".join(part.replace("~", "~0").replace("|", "~1") for part in pair)


def split_key(value: str) -> tuple[str, str]:
    first, second = value.split("|", 1)
    return first.replace("~1", "|").replace("~0", "~"), second.replace("~1", "|").replace("~0", "~")
