from unittest.mock import patch

from hexbytes import HexBytes
from safe_eth.eth.contracts import get_safe_V1_4_1_contract
from web3 import Web3

from app.datasources.db.database import db_session_context
from app.datasources.db.models import Contract
from app.services.abis import AbiService
from app.services.safe_contracts_service import (
    _generate_safe_contract_display_name,
    _get_address_to_abi_map,
    _get_deployments_by_chain_id,
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

    async def asyncTearDown(self):
        _get_deployments_by_chain_id.cache_clear()
        _get_address_to_abi_map.cache_clear()

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
        mock_get_deployments.return_value = CANONICAL_DEPLOYMENTS
        await Contract.get_or_create(HexBytes("0x1234"), 1)

        await update_safe_contracts_info()

        contract = await Contract.get_contract(
            HexBytes("0x9641d764fc13c8B624c04430C7356C1C7C8102e2"), 1
        )
        self.assertIsNotNone(contract)
        self.assertEqual(contract.name, "MultiSendCallOnly")
        self.assertEqual(contract.display_name, "Safe: MultiSendCallOnly 1.4.1")
        self.assertTrue(contract.trusted_for_delegate_call)

        contract = await Contract.get_contract(
            HexBytes("0x38869bf66a61cF6bDB996A6aE40D5853Fd43B526"), 1
        )
        self.assertIsNotNone(contract)
        self.assertEqual(contract.name, "MultiSend")
        self.assertEqual(contract.display_name, "Safe: MultiSend 1.4.1")
        self.assertTrue(contract.trusted_for_delegate_call)

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
            (TRON_SHASTA_CHAIN_ID, "0xf1dd46Af04774C999e213FA6dF2b4278BBa8A757"): (
                "MultiSendCallOnly",
                "Safe: MultiSendCallOnly 1.4.1",
                True,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x288603d5B09ce4d0Fe8b9Dd7A9Af87e02d0De5e6"): (
                "SignMessageLib",
                "Safe: SignMessageLib 1.4.1",
                True,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x5b84368e2fDe91C994434A4acBd29A0E1d60a1eA"): (
                "MultiSend",
                "Safe: MultiSend 1.4.1",
                True,
            ),
            (TRON_SHASTA_CHAIN_ID, "0x2e6355a073170c38b778af539b8f11e207ca4e30"): (
                "SafeL2",
                "SafeL2 1.4.1",
                False,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x6A8824d50B7AeEc29A6eC61ce928d964331AB35f"): (
                "MultiSendCallOnly",
                "Safe: MultiSendCallOnly 1.4.1",
                True,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x3711BA027fD46D537e17b2B12231818b4df89f14"): (
                "SignMessageLib",
                "Safe: SignMessageLib 1.4.1",
                True,
            ),
            (TRON_MAINNET_CHAIN_ID, "0x92F65C8F5eeB25617Acf7F3626936B5AB0C63680"): (
                "MultiSend",
                "Safe: MultiSend 1.4.1",
                True,
            ),
            (TRON_MAINNET_CHAIN_ID, "0xddBB124aA9f02C1234026E4f9AB106169FAaf15e"): (
                "SafeL2",
                "SafeL2 1.4.1",
                False,
            ),
        }
        for tron_chain_id in (TRON_SHASTA_CHAIN_ID, TRON_MAINNET_CHAIN_ID):
            contracts = [
                contract
                for contract in await Contract.get_all()
                if contract.chain_id == tron_chain_id
            ]
            self.assertEqual(len(contracts), 4)
        for (chain_id, address), (name, display_name, trusted) in expected.items():
            contract = await Contract.get_contract(HexBytes(address), chain_id)
            self.assertIsNotNone(contract, address)
            self.assertEqual(contract.name, name)
            self.assertEqual(contract.display_name, display_name)
            self.assertEqual(contract.trusted_for_delegate_call, trusted)
            self.assertIsNotNone(contract.abi_id, address)

        # SafeL2 is not deployed on its canonical address, but shares the 1.4.1 ABI
        contract = await Contract.get_contract(
            HexBytes("0x2e6355a073170c38b778af539b8f11e207ca4e30"),
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
        self.assertEqual(len(contracts), 8)
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
                HexBytes("0xf1dd46Af04774C999e213FA6dF2b4278BBa8A757"), 1
            )
        )
