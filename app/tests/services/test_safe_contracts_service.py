from unittest.mock import patch

from hexbytes import HexBytes
from safe_eth.eth.contracts import get_safe_V1_4_1_contract
from web3 import Web3

from app.config import settings
from app.datasources.db.database import db_session_context
from app.datasources.db.models import Abi, AbiSource, Contract
from app.services.abis import AbiService
from app.services.safe_contracts_service import (
    _CONTRACT_ABI_MAP,
    _generate_safe_contract_display_name,
    _get_address_to_abi_map,
    _get_address_to_abi_map_for_chain,
    _get_deployments_by_chain_id,
    _revoke_stale_canonical_trust,
    update_safe_contracts_info,
)

from ..datasources.db.async_db_test_case import AsyncDbTestCase

TRON_SHASTA_CHAIN_ID = 2494104990
TRON_MAINNET_CHAIN_ID = 728126428
CANONICAL_DEPLOYMENTS = [
    ("1.4.1", "MultiSendCallOnly", "0x9641d764fc13c8B624c04430C7356C1C7C8102e2"),
    ("1.4.1", "MultiSend", "0x38869bf66a61cF6bDB996A6aE40D5853Fd43B526"),
]


class TestContractMetadataService(AsyncDbTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        _get_deployments_by_chain_id.cache_clear()
        _get_address_to_abi_map.cache_clear()
        _get_address_to_abi_map_for_chain.cache_clear()

    async def asyncTearDown(self):
        _get_deployments_by_chain_id.cache_clear()
        _get_address_to_abi_map.cache_clear()
        _get_address_to_abi_map_for_chain.cache_clear()

    def test_generate_safe_contract_display_name(self):
        test_cases = [
            ("GnosisSafe", "1.3.0", "Safe 1.3.0"),  # removes Gnosis, keeps Safe
            ("GnosisMultiSend", "1.0.0", "Safe: MultiSend 1.0.0"),  # adds Safe:
            ("SignMessageLib", "1.0.0", "Safe: SignMessageLib 1.0.0"),  # adds Safe:
            ("SafeMigration", "1.1.1", "SafeMigration 1.1.1"),  # already has Safe
            (
                "GnosisSafeProxyFactory",
                "1.2.0",
                "SafeProxyFactory 1.2.0",
            ),  # removes Gnosis, keeps Safe
        ]
        for name, version, expected_result in test_cases:
            self.assertEqual(
                _generate_safe_contract_display_name(name, version), expected_result
            )

    @db_session_context
    @patch("app.services.safe_contracts_service._get_default_deployments_by_version")
    async def test_update_safe_contracts_info(self, mock_get_deployments):
        # Non-override chain parity: assert the seeded rows match exactly what
        # _get_default_deployments_by_version() + CONTRACTS_TRUSTED_FOR_DELEGATE_CALL
        # + _get_address_to_abi_map() say should be there, rather than hand-listing rows.
        mock_get_deployments.return_value = CANONICAL_DEPLOYMENTS
        await AbiService().load_local_abis_in_database()
        await Contract.get_or_create(HexBytes("0x1234"), 1)
        address_to_abi = _get_address_to_abi_map()

        await update_safe_contracts_info()

        contracts = [c for c in await Contract.get_all() if c.chain_id == 1]
        self.assertEqual(len(contracts), len(CANONICAL_DEPLOYMENTS) + 1)
        for version, contract_name, contract_address in CANONICAL_DEPLOYMENTS:
            contract = await Contract.get_contract(HexBytes(contract_address), 1)
            self.assertIsNotNone(contract, contract_address)
            self.assertEqual(contract.name, contract_name)
            self.assertEqual(
                contract.display_name,
                _generate_safe_contract_display_name(contract_name, version),
            )
            self.assertEqual(
                contract.trusted_for_delegate_call,
                contract_name in settings.CONTRACTS_TRUSTED_FOR_DELEGATE_CALL,
            )
            has_abi = contract_address in address_to_abi
            self.assertEqual(contract.abi_id is not None, has_abi, contract_address)

    @db_session_context
    @patch("app.services.safe_contracts_service._get_default_deployments_by_version")
    async def test_update_safe_contracts_info_with_overrides(
        self, mock_get_deployments
    ):
        mock_get_deployments.return_value = CANONICAL_DEPLOYMENTS
        await AbiService().load_local_abis_in_database()
        await Contract.get_or_create(HexBytes("0x1234"), 1)

        await update_safe_contracts_info()

        expected = {
            (TRON_SHASTA_CHAIN_ID, "0x48a430a9e259b1fa41408cef6103c56d8051ef36"): (
                "Safe",
                "Safe 1.4.1",
                False,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x1bdf92b7ad0aa881e811c540bde8600c3e2a41c8"): (
                "SafeL2",
                "SafeL2 1.4.1",
                False,
            ),
            (TRON_SHASTA_CHAIN_ID, "0xe010048abee39457ddaa556ed782732ca80ab39c"): (
                "SafeProxyFactory",
                "SafeProxyFactory 1.4.1",
                False,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x165a462e2017d8bf5e156e6d1ca6ac807023f861"): (
                "MultiSend",
                "Safe: MultiSend 1.4.1",
                False,
            ),
            (TRON_SHASTA_CHAIN_ID, "0xf22794c67fe86468272a25401fe95acb6df39f19"): (
                "MultiSendCallOnly",
                "Safe: MultiSendCallOnly 1.4.1",
                True,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x2c8c449ae05a7d43b9ebe1bd49600630d11c3ab5"): (
                "CompatibilityFallbackHandler",
                "Safe: CompatibilityFallbackHandler 1.4.1",
                False,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x18e47340854f3612974bf5342ba88262a348e589"): (
                "SignMessageLib",
                "Safe: SignMessageLib 1.4.1",
                True,
            ),
            (TRON_SHASTA_CHAIN_ID, "0xfe9c59afbc538185b3412269864192e29c5578f1"): (
                "SimulateTxAccessor",
                "Safe: SimulateTxAccessor 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x1619de3c122b610ef788a1bc13772a0c8506ed09"): (
                "Safe",
                "Safe 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x5c03b2637513d2ee57603d8aef67f6989b426c14"): (
                "SafeL2",
                "SafeL2 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x39235a65aed90f13a2bbec5c53f0d710cdbbc5d7"): (
                "SafeProxyFactory",
                "SafeProxyFactory 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x92f65c8f5eeb25617acf7f3626936b5ab0c63680"): (
                "MultiSend",
                "Safe: MultiSend 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x6a8824d50b7aeec29a6ec61ce928d964331ab35f"): (
                "MultiSendCallOnly",
                "Safe: MultiSendCallOnly 1.4.1",
                True,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x3f70526ed0567473d3ce222e3aae634baa932c8e"): (
                "CompatibilityFallbackHandler",
                "Safe: CompatibilityFallbackHandler 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x3711ba027fd46d537e17b2b12231818b4df89f14"): (
                "SignMessageLib",
                "Safe: SignMessageLib 1.4.1",
                True,
            ),
            (TRON_MAINNET_CHAIN_ID, "0xb7b37186a996b2e6371397a6056fdd34ef33ad92"): (
                "SimulateTxAccessor",
                "Safe: SimulateTxAccessor 1.4.1",
                False,
            ),
        }
        for tron_chain_id in (TRON_SHASTA_CHAIN_ID, TRON_MAINNET_CHAIN_ID):
            contracts = [
                contract
                for contract in await Contract.get_all()
                if contract.chain_id == tron_chain_id
            ]
            self.assertEqual(len(contracts), 8)
        for (chain_id, address), (name, display_name, trusted) in expected.items():
            contract = await Contract.get_contract(HexBytes(address), chain_id)
            self.assertIsNotNone(contract, address)
            self.assertEqual(contract.name, name)
            self.assertEqual(contract.display_name, display_name)
            self.assertEqual(contract.trusted_for_delegate_call, trusted)
            self.assertIsNotNone(contract.abi_id, address)

        # Canonical deployments are not seeded on override chains
        self.assertIsNone(
            await Contract.get_contract(
                HexBytes("0x9641d764fc13c8B624c04430C7356C1C7C8102e2"),
                TRON_MAINNET_CHAIN_ID,
            )
        )

        # SafeL2 shares the 1.4.1 ABI
        contract = await Contract.get_contract(
            HexBytes("0x1bdf92b7ad0aa881e811c540bde8600c3e2a41c8"),
            TRON_SHASTA_CHAIN_ID,
        )
        self.assertEqual(contract.abi.abi_json, get_safe_V1_4_1_contract(Web3()).abi)

    @db_session_context
    @patch("app.services.safe_contracts_service._get_default_deployments_by_version")
    async def test_update_safe_contracts_info_with_empty_database(
        self, mock_get_deployments
    ):
        mock_get_deployments.return_value = CANONICAL_DEPLOYMENTS
        self.assertEqual(await Contract.get_all(), [])

        await update_safe_contracts_info()

        contracts = await Contract.get_all()
        self.assertEqual(len(contracts), 16)
        self.assertEqual(
            {contract.chain_id for contract in contracts},
            {TRON_SHASTA_CHAIN_ID, TRON_MAINNET_CHAIN_ID},
        )

    @db_session_context
    async def test_update_safe_contracts_info_without_overrides(self):
        await Contract.get_or_create(HexBytes("0x1234"), 1)

        await update_safe_contracts_info()

        # Canonical deployments are only inserted on chains without overrides
        contract = await Contract.get_contract(
            HexBytes("0x9641d764fc13c8B624c04430C7356C1C7C8102e2"), 1
        )
        self.assertIsNotNone(contract)
        self.assertEqual(contract.name, "MultiSendCallOnly")
        self.assertIsNone(
            await Contract.get_contract(
                HexBytes("0x9641d764fc13c8B624c04430C7356C1C7C8102e2"),
                TRON_SHASTA_CHAIN_ID,
            )
        )
        self.assertIsNone(
            await Contract.get_contract(
                HexBytes("0xf22794c67fe86468272a25401fe95acb6df39f19"), 1
            )
        )

    @db_session_context
    async def test_update_safe_contracts_info_revokes_stale_canonical_trust(self):
        # decoder.stage already seeded the canonical MultiSendCallOnly for every
        # chain id present in the DB, including the TRON chain id, before overrides
        # existed - its trusted_for_delegate_call=True must be revoked once the
        # chain is override-only. Chain 1 (no override) must keep trusted=True.
        canonical_multisend_call_only = "0x9641d764fc13c8B624c04430C7356C1C7C8102e2"
        await Contract.get_or_create(
            HexBytes(canonical_multisend_call_only),
            TRON_MAINNET_CHAIN_ID,
            name="MultiSendCallOnly",
            trusted_for_delegate_call=True,
        )
        await Contract.get_or_create(
            HexBytes(canonical_multisend_call_only),
            1,
            name="MultiSendCallOnly",
            trusted_for_delegate_call=True,
        )

        await update_safe_contracts_info()

        tron_contract = await Contract.get_contract(
            HexBytes(canonical_multisend_call_only), TRON_MAINNET_CHAIN_ID
        )
        self.assertFalse(tron_contract.trusted_for_delegate_call)

        other_chain_contract = await Contract.get_contract(
            HexBytes(canonical_multisend_call_only), 1
        )
        self.assertTrue(other_chain_contract.trusted_for_delegate_call)

    @db_session_context
    @patch("app.services.safe_contracts_service._get_default_deployments_by_version")
    async def test_revoke_stale_canonical_trust_case_insensitive_overlap(
        self, mock_get_deployments
    ):
        # A canonical address kept as an override, but in different case, must
        # never be revoked - HexBytes comparison, not raw string comparison.
        mixed_case_address = "0x9641D764fc13c8b624c04430c7356c1c7c8102E2"
        mock_get_deployments.return_value = [
            ("1.4.1", "MultiSendCallOnly", mixed_case_address)
        ]
        with patch.dict(
            settings.SAFE_DEPLOYMENTS_OVERRIDES,
            {
                TRON_MAINNET_CHAIN_ID: {
                    "MultiSendCallOnly": [mixed_case_address.lower()]
                }
            },
        ):
            _get_deployments_by_chain_id.cache_clear()
            await Contract.get_or_create(
                HexBytes(mixed_case_address),
                TRON_MAINNET_CHAIN_ID,
                name="MultiSendCallOnly",
                trusted_for_delegate_call=True,
            )

            revoked_count = await _revoke_stale_canonical_trust(TRON_MAINNET_CHAIN_ID)

            self.assertEqual(revoked_count, 0)
            contract = await Contract.get_contract(
                HexBytes(mixed_case_address), TRON_MAINNET_CHAIN_ID
            )
            self.assertTrue(contract.trusted_for_delegate_call)

    @db_session_context
    @patch("app.services.safe_contracts_service._get_default_deployments_by_version")
    async def test_update_safe_contracts_info_is_idempotent(self, mock_get_deployments):
        mock_get_deployments.return_value = CANONICAL_DEPLOYMENTS
        await AbiService().load_local_abis_in_database()
        await Contract.get_or_create(HexBytes("0x1234"), 1)

        # Preseed rows with wrong metadata: canonical row on chain 1 with wrong
        # name/display_name/trusted and a pre-linked, distinct abi_id that must
        # survive (existing abi_id is never overwritten); override row on TRON
        # with wrong metadata and no abi linked yet, which must get one.
        abi_source, _ = await AbiSource.get_or_create("test", "https://example.com")
        preexisting_abi, _ = await Abi.get_or_create_abi(
            get_safe_V1_4_1_contract(Web3()).abi, abi_source.id
        )
        canonical_address = CANONICAL_DEPLOYMENTS[0][2]
        await Contract.get_or_create(
            HexBytes(canonical_address),
            1,
            name="WrongName",
            display_name="Wrong Display",
            trusted_for_delegate_call=False,
            abi_id=preexisting_abi.id,
        )
        override_address = settings.SAFE_DEPLOYMENTS_OVERRIDES[TRON_MAINNET_CHAIN_ID][
            "SignMessageLib"
        ][0]
        await Contract.get_or_create(
            HexBytes(override_address),
            TRON_MAINNET_CHAIN_ID,
            name="WrongName",
            display_name="Wrong Display",
            trusted_for_delegate_call=False,
        )

        await update_safe_contracts_info()

        canonical_contract = await Contract.get_contract(HexBytes(canonical_address), 1)
        self.assertEqual(canonical_contract.name, CANONICAL_DEPLOYMENTS[0][1])
        self.assertEqual(
            canonical_contract.display_name,
            _generate_safe_contract_display_name(
                CANONICAL_DEPLOYMENTS[0][1], CANONICAL_DEPLOYMENTS[0][0]
            ),
        )
        self.assertTrue(canonical_contract.trusted_for_delegate_call)
        # abi_id is never overwritten once set
        self.assertEqual(canonical_contract.abi_id, preexisting_abi.id)

        override_contract = await Contract.get_contract(
            HexBytes(override_address), TRON_MAINNET_CHAIN_ID
        )
        self.assertEqual(override_contract.name, "SignMessageLib")
        self.assertTrue(override_contract.trusted_for_delegate_call)
        # Missing abi gets linked
        self.assertIsNotNone(override_contract.abi_id)

        first_run_contracts = {
            (contract.address, contract.chain_id): (
                contract.name,
                contract.display_name,
                contract.trusted_for_delegate_call,
                contract.abi_id,
            )
            for contract in await Contract.get_all()
        }

        await update_safe_contracts_info()
        second_run_contracts = {
            (contract.address, contract.chain_id): (
                contract.name,
                contract.display_name,
                contract.trusted_for_delegate_call,
                contract.abi_id,
            )
            for contract in await Contract.get_all()
        }

        self.assertEqual(first_run_contracts, second_run_contracts)

    def test_get_deployments_by_chain_id_empty_override_seeds_nothing(self):
        self.addCleanup(_get_deployments_by_chain_id.cache_clear)
        with patch.dict(settings.SAFE_DEPLOYMENTS_OVERRIDES, {999: {}}, clear=False):
            _get_deployments_by_chain_id.cache_clear()
            self.assertEqual(_get_deployments_by_chain_id(999), [])

    def test_get_address_to_abi_map_for_chain_scopes_override_collision(self):
        # An override address that happens to reuse a canonical address must
        # resolve to the override chain's own ABI mapping, not swap in whatever
        # ABI that address maps to on another (canonical) chain.
        canonical_address = "0x9641d764fc13c8B624c04430C7356C1C7C8102e2"
        self.addCleanup(_get_deployments_by_chain_id.cache_clear)
        self.addCleanup(_get_address_to_abi_map_for_chain.cache_clear)
        with patch.dict(
            settings.SAFE_DEPLOYMENTS_OVERRIDES,
            {999: {"SignMessageLib": [canonical_address]}},
        ):
            _get_deployments_by_chain_id.cache_clear()
            _get_address_to_abi_map_for_chain.cache_clear()

            override_abi_map = _get_address_to_abi_map_for_chain(999)

            self.assertEqual(
                override_abi_map[canonical_address],
                _CONTRACT_ABI_MAP[("SignMessageLib", None)],
            )
