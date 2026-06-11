"""
Client for Hemera/SocialScan explorers (Etherscan-compatible API).

Reference: https://thehemera.gitbook.io/explorer-api

Differences from the Etherscan API V2:
  - Per-chain base url (``https://api.socialscan.io/{chain-name}/v1/developer/api``),
    without ``chainid`` query param or ``/v2/api`` path.
  - ``apikey`` query param is mandatory (header auth is rejected).
  - Unknown addresses return ``{"status": "0", "message": "No data found"}``
    with no ``result`` key at all, while ``getsourcecode`` for existing but
    unverified contracts returns ``"result": [{}]``.
  - ``Implementation``/``ConstructorArguments`` may be JSON null instead of ``""``
    (already handled by the parent's parsing).

Only the async code path is used by ``ContractMetadataService``, so the inherited
sync ``_do_request`` is intentionally not overridden.
"""

import os
from typing import Any

import aiohttp
from safe_eth.eth import EthereumNetwork
from safe_eth.eth.clients.etherscan_client_v2 import (
    AsyncEtherscanClientV2,
    EtherscanRateLimitError,
)


class SocialscanClientConfigurationProblem(Exception):
    pass


class AsyncSocialscanClient(AsyncEtherscanClientV2):
    def __init__(
        self,
        network: EthereumNetwork,
        base_url: str,
        api_key: str,
        request_timeout: int = int(
            os.environ.get("ETHERSCAN_CLIENT_REQUEST_TIMEOUT", 10)
        ),
        max_requests: int = 10,
    ):
        if not base_url:
            raise SocialscanClientConfigurationProblem(
                f"No SocialScan API url configured for {network}"
            )
        if not api_key:
            raise SocialscanClientConfigurationProblem(
                f"SocialScan API key is required for {network}"
            )
        super().__init__(
            network,
            api_key=api_key,
            request_timeout=request_timeout,
            max_requests=max_requests,
        )
        self.base_api_url = base_url

    def build_url(self, query: str) -> str:
        # The base url is the full endpoint path. `urljoin` cannot be used as it
        # would strip the `/{chain-name}/v1/developer/api` path
        return f"{self.base_api_url}?{query}&apikey={self.api_key}"

    @staticmethod
    def _process_get_contract_source_code_response(response):
        # SocialScan returns `[{}]` for existing but unverified contracts, which
        # would break the parent's parsing with a `KeyError` on `ContractName`
        if response and isinstance(response, list) and not response[0]:
            return None
        return AsyncEtherscanClientV2._process_get_contract_source_code_response(
            response
        )

    async def _async_do_request(
        self, url: str
    ) -> dict[str, Any] | list[Any] | str | None:
        async with self.async_session.get(
            url, timeout=aiohttp.ClientTimeout(total=self.request_timeout)
        ) as response:
            if response.ok:
                response_json = await response.json()
                # SocialScan omits `result` for "No data found" responses
                result = response_json.get("result")
                if result is None:
                    return None
                if isinstance(result, str) and "Max rate limit reached" in result:
                    raise EtherscanRateLimitError
                if response_json.get("status") == "1":
                    return result
            return None
