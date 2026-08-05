import copy
import unittest
from typing import cast

from eth_typing import ABIFunction
from eth_utils import function_abi_to_4byte_selector

from ...services.abi_normalizer import normalize_abi
from ..mocks.abi_mock import mock_abi_json
from ..mocks.tron_abi_mock import mock_tron_abi_json

MULTI_SEND_SELECTOR = bytes.fromhex("8d80ff0a")


class TestAbiNormalizer(unittest.TestCase):
    def test_normalize_abi_tron(self):
        self.assertEqual(
            normalize_abi(mock_tron_abi_json),
            [
                {
                    "inputs": [{"name": "transactions", "type": "bytes"}],
                    "name": "multiSend",
                    "outputs": [],
                    "stateMutability": "payable",
                    "type": "function",
                }
            ],
        )

    def test_normalize_abi_tron_does_not_mutate_input(self):
        expected = copy.deepcopy(mock_tron_abi_json)
        normalize_abi(mock_tron_abi_json)
        self.assertEqual(mock_tron_abi_json, expected)

    def test_normalize_abi_tron_is_supported_by_data_decoder(self):
        # `DataDecoderService._generate_selectors_with_abis_from_abi` filter
        fn_abis = [
            fn_abi
            for fn_abi in normalize_abi(mock_tron_abi_json)
            if fn_abi["type"] == "function"
        ]
        self.assertEqual(len(fn_abis), 1)
        self.assertEqual(
            function_abi_to_4byte_selector(cast(ABIFunction, fn_abis[0])),
            MULTI_SEND_SELECTOR,
        )

    def test_not_normalized_abi_tron_is_not_supported_by_data_decoder(self):
        fn_abis = [
            fn_abi
            for fn_abi in mock_tron_abi_json["entrys"]
            if fn_abi["type"] == "function"
        ]
        self.assertEqual(fn_abis, [])

    def test_normalize_abi_ethereum(self):
        self.assertEqual(normalize_abi(mock_abi_json), mock_abi_json)

    def test_normalize_abi_is_idempotent(self):
        for abi in (mock_tron_abi_json, mock_abi_json):
            normalized = normalize_abi(abi)
            self.assertEqual(normalize_abi(normalized), normalized)

    def test_normalize_abi_tron_unnamed_parameters(self):
        # TRON's protobuf-JSON drops empty strings, so unnamed parameters come
        # without a "name" key, which breaks decoding response validation
        entry = {
            "inputs": [{"type": "address"}, {"type": "bytes32"}],
            "name": "approvedHashes",
            "outputs": [{"type": "uint256"}],
            "stateMutability": "View",
            "type": "Function",
        }
        self.assertEqual(
            normalize_abi({"entrys": [entry]}),
            [
                {
                    "inputs": [
                        {"name": "", "type": "address"},
                        {"name": "", "type": "bytes32"},
                    ],
                    "name": "approvedHashes",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
        )

    def test_normalize_abi_tron_unnamed_tuple_components(self):
        entry = {
            "inputs": [{"type": "tuple", "components": [{"type": "uint256"}]}],
            "name": "execute",
            "type": "Function",
        }
        self.assertEqual(
            normalize_abi({"entrys": [entry]})[0]["inputs"],
            [
                {
                    "name": "",
                    "type": "tuple",
                    "components": [{"name": "", "type": "uint256"}],
                }
            ],
        )

    def test_normalize_abi_empty_dict(self):
        # TronGrid returns `"abi": {}` for proxies and unverified contracts
        self.assertEqual(normalize_abi({}), [])

    def test_normalize_abi_unrecognized_dict(self):
        # A Hardhat/Foundry style artifact must not silently normalize to []
        with self.assertRaises(ValueError):
            normalize_abi({"contractName": "MultiSendCallOnly", "abi": mock_abi_json})

    def test_normalize_abi_unknown_types(self):
        self.assertEqual(
            normalize_abi([{"name": "unknown"}, {"type": "Error", "inputs": []}]),
            [{"name": "unknown"}, {"type": "error", "inputs": []}],
        )
