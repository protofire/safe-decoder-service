import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from safe_eth.eth import EthereumNetwork
from safe_eth.eth.utils import fast_to_checksum_address

from app.services.tron_grid_client import (
    AsyncTronGridClient,
    TronGridClientConfigurationProblem,
)

from ..mocks.tron_grid_mocks import (
    tron_grid_contract_mock,
    tron_grid_metadata_mock,
    tron_grid_not_found_mock,
    tron_grid_proxy_mock,
)

MULTI_SEND_CALL_ONLY_ADDRESS = fast_to_checksum_address(
    "0xf1dd46Af04774C999e213FA6dF2b4278BBa8A757"
)


def mock_post(response_json: dict, ok: bool = True) -> MagicMock:
    """
    :return: A mock replacing `aiohttp.ClientSession.post`
    """
    response = MagicMock()
    response.ok = ok
    response.json = AsyncMock(return_value=response_json)
    async_context_manager = MagicMock()
    async_context_manager.__aenter__ = AsyncMock(return_value=response)
    async_context_manager.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=async_context_manager)


class TestAsyncTronGridClient(unittest.IsolatedAsyncioTestCase):
    async def test_unsupported_network(self):
        with self.assertRaises(TronGridClientConfigurationProblem):
            AsyncTronGridClient(EthereumNetwork.MAINNET)

    async def test_base_urls(self):
        expected_base_urls = {
            EthereumNetwork.TRON_MAINNET: "https://api.trongrid.io",
            EthereumNetwork.TRON_SHASTA: "https://api.shasta.trongrid.io",
            EthereumNetwork.TRON_NILE: "https://nile.trongrid.io",
        }
        for network, base_url in expected_base_urls.items():
            self.assertEqual(AsyncTronGridClient(network).base_url, base_url)

    async def test_api_key_header(self):
        client = AsyncTronGridClient(EthereumNetwork.TRON_SHASTA)
        self.assertNotIn("TRON-PRO-API-KEY", client.async_session.headers)
        client = AsyncTronGridClient(EthereumNetwork.TRON_SHASTA, api_key="a-key")
        self.assertEqual(client.async_session.headers["TRON-PRO-API-KEY"], "a-key")

    async def test_async_get_contract_metadata(self):
        client = AsyncTronGridClient(EthereumNetwork.TRON_SHASTA)
        post_mock = mock_post(tron_grid_contract_mock)
        with mock.patch.object(aiohttp.ClientSession, "post", post_mock):
            contract_metadata = await client.async_get_contract_metadata(
                MULTI_SEND_CALL_ONLY_ADDRESS
            )

        post_mock.assert_called_once_with(
            "https://api.shasta.trongrid.io/wallet/getcontract",
            json={"value": "41f1dd46af04774c999e213fa6df2b4278bba8a757"},
            timeout=aiohttp.ClientTimeout(total=client.request_timeout),
        )
        self.assertEqual(contract_metadata, tron_grid_metadata_mock)

    async def test_async_get_contract_metadata_without_abi(self):
        client = AsyncTronGridClient(EthereumNetwork.TRON_SHASTA)
        for response_json in (tron_grid_proxy_mock, tron_grid_not_found_mock):
            with mock.patch.object(
                aiohttp.ClientSession, "post", mock_post(response_json)
            ):
                self.assertIsNone(
                    await client.async_get_contract_metadata(
                        MULTI_SEND_CALL_ONLY_ADDRESS
                    )
                )

    async def test_async_get_contract_metadata_error_response(self):
        client = AsyncTronGridClient(EthereumNetwork.TRON_SHASTA)
        with mock.patch.object(
            aiohttp.ClientSession, "post", mock_post(tron_grid_contract_mock, ok=False)
        ):
            self.assertIsNone(
                await client.async_get_contract_metadata(MULTI_SEND_CALL_ONLY_ADDRESS)
            )
