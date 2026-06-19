import logging
from typing import cast

from hexbytes import HexBytes

from app.config import settings
from app.datasources.abis.seismic import src20_abi
from app.datasources.db.models import Abi, Contract

logger = logging.getLogger(__name__)


async def update_seismic_contracts_info() -> None:
    """
    Register the configured SRC-20 shielded token contracts directly in the DB,
    linking each address to the hardcoded ``src20_abi``.

    Addresses are read from ``settings.SRC20_TOKEN_ADDRESSES`` (chain_id -> list of
    addresses). These contracts are unverified on their explorer, so their ABI can
    never be fetched automatically; hardcoding the address -> ABI link upgrades
    SRC-20 transfer decoding accuracy from ONLY_FUNCTION_MATCH (the selector is
    registered globally) to FULL_MATCH for the configured token addresses.

    Relies on ``AbiService.load_local_abis_in_database`` having already stored
    ``src20_abi``; if it has not, the seeding is skipped.
    """
    if not settings.SRC20_TOKEN_ADDRESSES:
        logger.info("No SRC-20 token addresses configured, skipping seeding")
        return

    abi = await Abi.get_abi(cast(list[dict], src20_abi))
    if abi is None:
        logger.warning(
            "src20_abi not found in database, skipping SRC-20 contract "
            "seeding (run load_local_abis_in_database first)"
        )
        return

    registered = 0
    for chain_id, addresses in settings.SRC20_TOKEN_ADDRESSES.items():
        for address in addresses:
            contract, created = await Contract.get_or_create(
                HexBytes(address), chain_id
            )
            contract.name = "SRC20"
            contract.display_name = "SRC-20 Token"
            # Don't clobber a real fetched ABI if one was somehow already linked.
            if contract.abi_id is None:
                contract.abi_id = abi.id
            await contract.update()
            registered += 1
            logger.info(
                "Registered SRC-20 contract %s on chain %d (created=%s)",
                address,
                chain_id,
                created,
            )

    logger.info("Finished registering %d SRC-20 contract(s)", registered)
