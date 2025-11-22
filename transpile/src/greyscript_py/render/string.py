"""Render GS strings."""


def encode_gs_string(text: str) -> str:
    """Encode text as a GS string."""
    ret = '"'
    for val in text:
        # TODO investigate what kinds of valid unicode we allow in the string.
        if val == '"':
            ret += '""'
        else:
            ret += val
    return ret + '"'
