import json
from pathlib import Path

from hexbytes import HexBytes
from typer import BadParameter

from app.commands.styles import print_command_title, success
from app.datasources.db.models import Abi, AbiSource, Contract
from app.services.abi_normalizer import normalize_abi


async def load_abi_command(
    abi_file: str,
    relevance: int = 50,
    description: str | None = None,
    address: str | None = None,
    chain_id: int | None = None,
):
    if (address is None) != (chain_id is None):
        raise BadParameter("--address and --chain-id must be provided together")
    if description and address is None:
        raise BadParameter("--description requires --address and --chain-id")

    print_command_title(f"Loading ABI from {abi_file}")
    try:
        abi_json = normalize_abi(json.loads(Path(abi_file).read_text()))
    except ValueError as exc:
        raise BadParameter(str(exc)) from exc
    if not abi_json:
        raise BadParameter(f"No ABI entries found in {abi_file}")
    abi_source, _ = await AbiSource.get_or_create("manual", "")
    abi, created = await Abi.get_or_create_abi(
        abi_json=abi_json, source_id=abi_source.id, relevance=relevance
    )
    if created:
        success(f"Stored ABI {abi.id} with {len(abi_json)} entries")
    else:
        print(f"ABI already stored with id {abi.id}")

    if address is not None and chain_id is not None:
        contract, _ = await Contract.get_or_create(HexBytes(address), chain_id)
        contract.abi_id = abi.id
        if description:
            contract.description = description
        await contract.update()
        success(f"Linked ABI {abi.id} to contract {address} on chain {chain_id}")
