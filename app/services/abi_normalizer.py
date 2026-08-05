from typing import Any


def _normalize_parameters(parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Fill the ``name`` key TRON omits on unnamed parameters, recursing into
    tuple components

    :param parameters: ABI entry ``inputs`` or ``outputs``
    :return: parameters on the Ethereum format
    """
    normalized_parameters = []
    for parameter in parameters:
        normalized_parameter = dict(parameter)
        normalized_parameter.setdefault("name", "")
        if "components" in normalized_parameter:
            normalized_parameter["components"] = _normalize_parameters(
                normalized_parameter["components"]
            )
        normalized_parameters.append(normalized_parameter)
    return normalized_parameters


def normalize_abi(abi: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert a TRON ABI to the Ethereum format, leaving an Ethereum ABI unchanged

    :param abi: TRON ``{"entrys": [...]}`` object or Ethereum list of entries
    :return: ABI entries on the Ethereum format
    :raises ValueError: if a not empty dict is not on the TRON format
    """
    if isinstance(abi, dict):
        if abi and "entrys" not in abi:
            raise ValueError(
                'Unrecognized ABI format, expected an Ethereum ABI list or a TRON {"entrys": [...]} object'
            )
        entries = abi.get("entrys", [])
    else:
        entries = abi
    normalized_entries = []
    for entry in entries:
        normalized_entry = dict(entry)
        for key in ("type", "stateMutability"):
            if key in normalized_entry:
                normalized_entry[key] = normalized_entry[key].lower()
        if normalized_entry.get("type") == "function":
            normalized_entry.setdefault("outputs", [])
        for key in ("inputs", "outputs"):
            if key in normalized_entry:
                normalized_entry[key] = _normalize_parameters(normalized_entry[key])
        normalized_entries.append(normalized_entry)
    return normalized_entries
