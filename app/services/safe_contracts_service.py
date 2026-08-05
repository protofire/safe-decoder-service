import logging
from functools import cache
from typing import cast

from eth_typing import ABI
from hexbytes import HexBytes
from safe_eth.eth.contracts import (
    get_compatibility_fallback_handler_V1_3_0_contract,
    get_compatibility_fallback_handler_V1_4_1_contract,
    get_multi_send_call_only_contract,
    get_multi_send_contract,
    get_proxy_factory_V1_0_0_contract,
    get_proxy_factory_V1_1_1_contract,
    get_proxy_factory_V1_3_0_contract,
    get_proxy_factory_V1_4_1_contract,
    get_safe_to_l2_migration_contract,
    get_safe_V1_0_0_contract,
    get_safe_V1_1_1_contract,
    get_safe_V1_3_0_contract,
    get_safe_V1_4_1_contract,
    get_sign_message_lib_contract,
    get_simulate_tx_accessor_V1_4_1_contract,
)
from safe_eth.safe.safe_deployments import default_safe_deployments
from web3 import Web3

from app.config import settings
from app.datasources.abis.safe import safe_migration_abi
from app.datasources.db.models import Abi, Contract

logger = logging.getLogger(__name__)

_DUMMY_W3 = Web3()

# Version used for the display name of the contracts defined on SAFE_DEPLOYMENTS_OVERRIDES,
# every overridden deployment is a 1.4.1 release (TRON tx service `/api/v1/about/singletons/`
# reports 1.4.1+L2 for both TRON Mainnet and Shasta).
_OVERRIDE_DEPLOYMENTS_VERSION = "1.4.1"

# Maps (contract_name, version) to ABI.
# version=None means the ABI applies regardless of version for that contract name.
_CONTRACT_ABI_MAP: dict[tuple[str, str | None], ABI] = {
    ("GnosisSafe", "1.0.0"): get_safe_V1_0_0_contract(_DUMMY_W3).abi,
    ("GnosisSafe", "1.1.1"): get_safe_V1_1_1_contract(_DUMMY_W3).abi,
    ("GnosisSafe", "1.3.0"): get_safe_V1_3_0_contract(_DUMMY_W3).abi,
    # GnosisSafeL2 / SafeL2 share the same function signatures as their L1 counterparts;
    ("GnosisSafeL2", "1.3.0"): get_safe_V1_3_0_contract(_DUMMY_W3).abi,
    ("Safe", "1.4.1"): get_safe_V1_4_1_contract(_DUMMY_W3).abi,
    ("SafeL2", "1.4.1"): get_safe_V1_4_1_contract(_DUMMY_W3).abi,
    ("SafeMigration", "1.4.1"): safe_migration_abi,
    ("SafeToL2Migration", "1.4.1"): get_safe_to_l2_migration_contract(_DUMMY_W3).abi,
    ("MultiSend", None): get_multi_send_contract(_DUMMY_W3).abi,
    ("MultiSendCallOnly", None): get_multi_send_call_only_contract(_DUMMY_W3).abi,
    ("SignMessageLib", None): get_sign_message_lib_contract(_DUMMY_W3).abi,
    ("CompatibilityFallbackHandler", "1.3.0"): get_compatibility_fallback_handler_V1_3_0_contract(_DUMMY_W3).abi,
    ("CompatibilityFallbackHandler", "1.4.1"): get_compatibility_fallback_handler_V1_4_1_contract(_DUMMY_W3).abi,
    ("ProxyFactory", "1.0.0"): get_proxy_factory_V1_0_0_contract(_DUMMY_W3).abi,
    ("ProxyFactory", "1.1.1"): get_proxy_factory_V1_1_1_contract(_DUMMY_W3).abi,
    ("GnosisSafeProxyFactory", "1.3.0"): get_proxy_factory_V1_3_0_contract(_DUMMY_W3).abi,
    ("SafeProxyFactory", "1.4.1"): get_proxy_factory_V1_4_1_contract(_DUMMY_W3).abi,
    ("SimulateTxAccessor", "1.4.1"): get_simulate_tx_accessor_V1_4_1_contract(_DUMMY_W3).abi,
}


def _generate_safe_contract_display_name(contract_name: str, version: str) -> str:
    """
    Generates the display name for Safe contract.
    Append Safe at the beginning if the contract name doesn't contain Safe word and append the contract version at the end.

    :param contract_name:
    :param version:
    :return: display_name
    """
    # Remove gnosis word
    contract_name = contract_name.replace("Gnosis", "")
    if "safe" not in contract_name.lower():
        return f"Safe: {contract_name} {version}"
    else:
        return f"{contract_name} {version}"


@cache
def _get_default_deployments_by_version() -> list[tuple[str, str, str]]:
    """
    Get the default deployments by version that are inserted on database.

    :return: list of (version, contract_name, contract_address)
    """
    chain_deployments: list[tuple[str, str, str]] = []
    for version in default_safe_deployments:
        for contract_name, addresses in default_safe_deployments[version].items():
            for contract_address in addresses:
                chain_deployments.append((version, contract_name, contract_address))

    return chain_deployments


@cache
def _get_deployments_by_chain_id(chain_id: int) -> list[tuple[str, str, str]]:
    """
    Get the deployments that are inserted on database for the given `chain_id`.
    Chains defined on `SAFE_DEPLOYMENTS_OVERRIDES` only get their overridden contracts,
    as the canonical addresses are not deployed there.

    :param chain_id:
    :return: list of (version, contract_name, contract_address)
    """
    if overrides := settings.SAFE_DEPLOYMENTS_OVERRIDES.get(chain_id):
        return [
            (_OVERRIDE_DEPLOYMENTS_VERSION, contract_name, contract_address)
            for contract_name, addresses in overrides.items()
            for contract_address in addresses
        ]

    return _get_default_deployments_by_version()


@cache
def _get_address_to_abi_map() -> dict[str, ABI]:
    """
    Maps each known Safe contract address to its ABI.
    Addresses without a known ABI are excluded.

    :return: dict of contract_address -> ABI
    """
    deployments = list(_get_default_deployments_by_version())
    for chain_id in settings.SAFE_DEPLOYMENTS_OVERRIDES:
        deployments += _get_deployments_by_chain_id(chain_id)

    result: dict[str, ABI] = {}
    for version, contract_name, contract_address in deployments:
        abi = _CONTRACT_ABI_MAP.get(
            (contract_name, version)
        ) or _CONTRACT_ABI_MAP.get((contract_name, None))
        if abi is not None:
            result[contract_address] = abi
    return result


async def update_safe_contracts_info() -> None:
    """
    For every known Safe contract address, create or update Contract rows for all
    chain_ids currently present in the DB and every chain defined on
    `SAFE_DEPLOYMENTS_OVERRIDES`, linking the locally known ABI where available.
    """
    chain_ids = set(await Contract.get_distinct_chain_ids()) | set(
        settings.SAFE_DEPLOYMENTS_OVERRIDES
    )

    address_to_abi = _get_address_to_abi_map()

    # Cache DB ABI lookups keyed by Python object id to avoid one query per contract address
    # when multiple addresses share the same ABI object.
    abi_id_cache: dict[int, int | None] = {}

    for chain_id in sorted(chain_ids):
        created_count = 0
        for version, contract_name, contract_address in _get_deployments_by_chain_id(
            chain_id
        ):
            address_bytes = HexBytes(contract_address)
            display_name = _generate_safe_contract_display_name(contract_name, version)
            trusted = contract_name in settings.CONTRACTS_TRUSTED_FOR_DELEGATE_CALL

            # Resolve ABI id once per unique ABI object, not once per contract address
            abi_id: int | None = None
            abi_json = address_to_abi.get(contract_address)
            if abi_json is not None:
                cache_key = id(abi_json)
                if cache_key not in abi_id_cache:
                    abi = await Abi.get_abi(cast(list[dict], abi_json))
                    abi_id_cache[cache_key] = abi.id if abi else None
                abi_id = abi_id_cache[cache_key]

            contract, created = await Contract.get_or_create(address_bytes, chain_id)
            contract.name = contract_name
            contract.display_name = display_name
            contract.trusted_for_delegate_call = trusted
            if abi_id is not None and contract.abi_id is None:
                contract.abi_id = abi_id
            await contract.update()
            if created:
                created_count += 1

        if created_count:
            logger.info(
                "Seeded %d new Safe contracts on chain %d", created_count, chain_id
            )

    logger.info(
        "Finished updating Safe contracts info across %d chains", len(chain_ids)
    )
