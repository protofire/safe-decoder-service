# Responses of POST https://api.shasta.trongrid.io/wallet/getcontract

from safe_eth.eth.clients import ContractMetadata

from .tron_abi_mock import mock_tron_abi_json

tron_grid_contract_mock: dict = {
    "name": "MultiSendCallOnly",
    "abi": mock_tron_abi_json,
    "origin_address": "41495369e87dd860a5546bd0d6c276691f61e9a4cb",
    "contract_address": "41f1dd46af04774c999e213fa6df2b4278bba8a757",
}

# Safe proxies and unverified contracts are returned without ABI entries
tron_grid_proxy_mock: dict = {
    "abi": {},
    "origin_address": "411cd2a7aa6203dcb9bb40cf8d916011cefef82af1",
    "contract_address": "41d72c8d27d0f45173d3178e35b2d496f56a407ff7",
}

# Addresses without contract code
tron_grid_not_found_mock: dict = {}

tron_grid_metadata_mock = ContractMetadata(
    "MultiSendCallOnly",
    [
        {
            "inputs": [{"name": "transactions", "type": "bytes"}],
            "name": "multiSend",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function",
        }
    ],
    False,
)
