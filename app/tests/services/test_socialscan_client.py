import unittest
from typing import Any
from unittest import mock

from safe_eth.eth import EthereumNetwork
from safe_eth.eth.clients import ContractMetadata
from safe_eth.eth.clients.etherscan_client_v2 import EtherscanRateLimitError

from app.services.socialscan_client import (
    AsyncSocialscanClient,
    SocialscanClientConfigurationProblem,
)

SEISMIC_BASE_URL = "https://api.socialscan.io/seismic-testnet/v1/developer/api"

get_source_code_payload = {
    "status": "1",
    "message": "OK",
    "result": [
        {
            "SourceCode": "{}",
            "ABI": '[{"inputs": [{"internalType": "address", "name": "to", "type": "address"}], "name": "transfer", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]',
            "ContractName": "Guard",
            "CompilerVersion": "v0.7.6+commit.7338295f",
            "OptimizationUsed": "1",
            "Runs": "200",
            "ConstructorArguments": None,
            "EVMVersion": "Default",
            "Library": "",
            "LicenseType": "",
            "Proxy": "0",
            "Implementation": None,
            "SwarmSource": "",
        }
    ],
}

no_data_found_payload: dict[str, Any] = {"status": "0", "message": "No data found"}

unverified_contract_payload: dict[str, Any] = {
    "status": "1",
    "message": "OK",
    "result": [{}],
}

rate_limit_payload = {
    "status": "0",
    "message": "NOTOK",
    "result": "Max rate limit reached, please use API Key for higher rate limit",
}


class FakeResponse:
    def __init__(self, json_payload: Any, ok: bool = True):
        self.ok = ok
        self._json_payload = json_payload

    async def json(self) -> Any:
        return self._json_payload


class FakeGetContext:
    def __init__(self, response: FakeResponse):
        self._response = response

    async def __aenter__(self) -> FakeResponse:
        return self._response

    async def __aexit__(self, *args: Any) -> None:
        return None


class TestAsyncSocialscanClient(unittest.IsolatedAsyncioTestCase):
    async def _get_client(self) -> AsyncSocialscanClient:
        client = AsyncSocialscanClient(
            EthereumNetwork(5124),
            base_url=SEISMIC_BASE_URL,
            api_key="test-api-key",
        )
        self.addAsyncCleanup(client.async_session.close)
        return client

    def _mock_response(
        self, client: AsyncSocialscanClient, json_payload: Any, ok: bool = True
    ) -> None:
        client.async_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=FakeGetContext(FakeResponse(json_payload, ok=ok))
            )
        )

    async def test_init_raises_without_configuration(self):
        with self.assertRaises(SocialscanClientConfigurationProblem):
            AsyncSocialscanClient(
                EthereumNetwork(5124), base_url="", api_key="test-api-key"
            )
        with self.assertRaises(SocialscanClientConfigurationProblem):
            AsyncSocialscanClient(
                EthereumNetwork(5124), base_url=SEISMIC_BASE_URL, api_key=""
            )

    async def test_build_url(self):
        client = await self._get_client()
        address = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
        self.assertEqual(
            client.build_url(f"module=contract&action=getsourcecode&address={address}"),
            f"{SEISMIC_BASE_URL}?module=contract&action=getsourcecode&address={address}&apikey=test-api-key",
        )

    async def test_async_get_contract_metadata(self):
        client = await self._get_client()
        self._mock_response(client, get_source_code_payload)
        contract_metadata = await client.async_get_contract_metadata(
            "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
        )
        self.assertEqual(
            contract_metadata,
            ContractMetadata(
                "Guard",
                [
                    {
                        "inputs": [
                            {
                                "internalType": "address",
                                "name": "to",
                                "type": "address",
                            }
                        ],
                        "name": "transfer",
                        "outputs": [],
                        "stateMutability": "nonpayable",
                        "type": "function",
                    }
                ],
                False,
                None,
            ),
        )

    async def test_async_get_contract_metadata_no_data_found(self):
        # SocialScan returns `{"status": "0", "message": "No data found"}` without
        # a `result` key for unverified/unknown addresses
        client = await self._get_client()
        self._mock_response(client, no_data_found_payload)
        contract_metadata = await client.async_get_contract_metadata(
            "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
        )
        self.assertIsNone(contract_metadata)

    async def test_async_get_contract_metadata_unverified_contract(self):
        # SocialScan returns `{"status": "1", "result": [{}]}` for existing but
        # unverified contracts
        client = await self._get_client()
        self._mock_response(client, unverified_contract_payload)
        contract_metadata = await client.async_get_contract_metadata(
            "0x91EDd1341DCB5515EAf5Ef34338bb2460241F3bF"
        )
        self.assertIsNone(contract_metadata)

    async def test_async_get_contract_metadata_rate_limit(self):
        client = await self._get_client()
        self._mock_response(client, rate_limit_payload)
        with self.assertRaises(EtherscanRateLimitError):
            await client.async_get_contract_metadata(
                "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
            )
