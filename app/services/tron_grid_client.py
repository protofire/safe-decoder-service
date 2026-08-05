import os
from typing import Any

import aiohttp
from eth_typing import ChecksumAddress
from safe_eth.eth import EthereumNetwork
from safe_eth.eth.clients import ContractMetadata

from app.services.abi_normalizer import normalize_abi


class TronGridClientConfigurationProblem(Exception):
    pass


class AsyncTronGridClient:
    """
    Get contract metadata from TronGrid. TRON stores the ABI on chain, so no source
    verification is involved.

    Reference: https://developers.tron.network/reference/wallet-getcontract
    """

    NETWORK_WITH_URL = {
        EthereumNetwork.TRON_MAINNET: "https://api.trongrid.io",
        EthereumNetwork.TRON_SHASTA: "https://api.shasta.trongrid.io",
        EthereumNetwork.TRON_NILE: "https://nile.trongrid.io",
    }

    def __init__(
        self,
        network: EthereumNetwork,
        api_key: str = "",
        request_timeout: int = int(
            os.environ.get("TRONGRID_CLIENT_REQUEST_TIMEOUT", 10)
        ),
        max_requests: int = 1,
    ):
        self.network = network
        self.base_url = self.NETWORK_WITH_URL.get(network, "")
        if not self.base_url:
            raise TronGridClientConfigurationProblem(
                f"Network {network.name} - {network.value} not supported"
            )
        self.request_timeout = request_timeout
        # Limit simultaneous connections to the same host, TronGrid rate limits at ~1 request/second
        self.async_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit_per_host=max_requests),
            headers={"TRON-PRO-API-KEY": api_key} if api_key else None,
        )

    @staticmethod
    def _get_tron_address(address: ChecksumAddress) -> str:
        """
        :param address:
        :return: TRON hex address, the EVM one prefixed with the `0x41` version byte
        """
        return f"41{address[2:].lower()}"

    @staticmethod
    def _process_contract_metadata(
        contract_data: dict[str, Any],
    ) -> ContractMetadata | None:
        """
        Return a ContractMetadata from TronGrid response

        :param contract_data:
        :return:
        """
        # Proxies and addresses without contract code are returned without ABI entries
        if abi := normalize_abi(contract_data.get("abi") or {}):
            return ContractMetadata(contract_data.get("name"), abi, False)
        return None

    async def async_get_contract_metadata(
        self, contract_address: ChecksumAddress
    ) -> ContractMetadata | None:
        async with self.async_session.post(
            f"{self.base_url}/wallet/getcontract",
            json={"value": self._get_tron_address(contract_address)},
            timeout=aiohttp.ClientTimeout(total=self.request_timeout),
        ) as response:
            if not response.ok:
                return None
            contract_data = await response.json()

        return self._process_contract_metadata(contract_data)
