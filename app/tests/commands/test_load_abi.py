import json
from pathlib import Path
from tempfile import TemporaryDirectory

from eth_utils import function_abi_to_4byte_selector
from hexbytes import HexBytes
from typer import BadParameter

from app.commands.load_abi import load_abi_command
from app.datasources.db.database import db_session_context
from app.datasources.db.models import Abi, Contract
from app.tests.datasources.db.async_db_test_case import AsyncDbTestCase
from app.tests.mocks.tron_abi_mock import mock_tron_abi_json


class TestLoadAbi(AsyncDbTestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.abi_file = Path(self.temporary_directory.name) / "tron_abi.json"
        self.abi_file.write_text(json.dumps(mock_tron_abi_json))

    @db_session_context
    async def test_load_abi(self):
        await load_abi_command(abi_file=str(self.abi_file))

        abis = await Abi.get_all()
        self.assertEqual(len(abis), 1)
        self.assertEqual(abis[0].relevance, 50)
        self.assertEqual(
            abis[0].abi_json,
            [
                {
                    "inputs": [{"name": "transactions", "type": "bytes"}],
                    "name": "multiSend",
                    "stateMutability": "payable",
                    "type": "function",
                    "outputs": [],
                }
            ],
        )
        self.assertEqual(
            function_abi_to_4byte_selector(abis[0].abi_json[0]),
            bytes.fromhex("8d80ff0a"),
        )

    @db_session_context
    async def test_load_abi_with_relevance(self):
        await load_abi_command(abi_file=str(self.abi_file), relevance=100)

        abis = await Abi.get_all()
        self.assertEqual(len(abis), 1)
        self.assertEqual(abis[0].relevance, 100)

    @db_session_context
    async def test_load_abi_is_not_duplicated(self):
        await load_abi_command(abi_file=str(self.abi_file))
        await load_abi_command(abi_file=str(self.abi_file))

        self.assertEqual(len(await Abi.get_all()), 1)

    @db_session_context
    async def test_load_abi_unrecognized_format(self):
        self.abi_file.write_text(
            json.dumps({"contractName": "MultiSendCallOnly", "abi": []})
        )
        with self.assertRaises(BadParameter):
            await load_abi_command(abi_file=str(self.abi_file))

        self.assertEqual(len(await Abi.get_all()), 0)

    @db_session_context
    async def test_load_abi_without_entries(self):
        self.abi_file.write_text(json.dumps({"entrys": []}))
        with self.assertRaises(BadParameter):
            await load_abi_command(abi_file=str(self.abi_file))

        self.assertEqual(len(await Abi.get_all()), 0)

    @db_session_context
    async def test_load_abi_with_address_and_no_chain_id(self):
        with self.assertRaises(BadParameter):
            await load_abi_command(
                abi_file=str(self.abi_file),
                address="0xf1dd46Af04774C999e213FA6dF2b4278BBa8A757",
            )

        self.assertEqual(len(await Abi.get_all()), 0)

    @db_session_context
    async def test_load_abi_with_description_and_no_address(self):
        with self.assertRaises(BadParameter):
            await load_abi_command(
                abi_file=str(self.abi_file), description="MultiSendCallOnly"
            )

        self.assertEqual(len(await Abi.get_all()), 0)

    @db_session_context
    async def test_load_abi_with_address(self):
        address = "0xf1dd46Af04774C999e213FA6dF2b4278BBa8A757"
        chain_id = 2494104990

        await load_abi_command(
            abi_file=str(self.abi_file),
            description="MultiSendCallOnly",
            address=address,
            chain_id=chain_id,
        )

        abis = await Abi.get_all()
        self.assertEqual(len(abis), 1)
        contract = await Contract.get_contract(HexBytes(address), chain_id)
        self.assertIsNotNone(contract)
        self.assertEqual(contract.abi_id, abis[0].id)
        self.assertEqual(contract.description, "MultiSendCallOnly")

    @db_session_context
    async def test_load_abi_with_address_is_not_duplicated(self):
        address = "0xf1dd46Af04774C999e213FA6dF2b4278BBa8A757"
        chain_id = 2494104990

        await load_abi_command(
            abi_file=str(self.abi_file), address=address, chain_id=chain_id
        )
        await load_abi_command(
            abi_file=str(self.abi_file), address=address, chain_id=chain_id
        )

        self.assertEqual(len(await Abi.get_all()), 1)
        self.assertEqual(len(await Contract.get_all()), 1)
