from unittest.mock import patch

from hexbytes import HexBytes

from app.datasources.abis.seismic import src20_abi
from app.services.seismic_contracts_service import update_seismic_contracts_info

from ...datasources.db.database import db_session_context
from ...datasources.db.models import Abi, AbiSource, Contract
from ...services.data_decoder import DataDecoderService, DecodingAccuracyEnum
from ..datasources.db.async_db_test_case import AsyncDbTestCase

TEST_CHAIN_ID = 5124
TEST_ADDRESS = "0x91edd1341dcb5515eaf5ef34338bb2460241f3bf"
TEST_SRC20_TOKEN_ADDRESSES = {TEST_CHAIN_ID: [TEST_ADDRESS]}


@patch(
    "app.services.seismic_contracts_service.settings.SRC20_TOKEN_ADDRESSES",
    TEST_SRC20_TOKEN_ADDRESSES,
)
class TestSeismicContractsService(AsyncDbTestCase):
    @staticmethod
    async def _store_src20_abi() -> Abi:
        source = AbiSource(name="local", url="")
        await source.create()
        abi = Abi(
            abi_hash=b"SRC20Contract",
            abi_json=src20_abi,
            relevance=90,
            source_id=source.id,
        )
        await abi.create()
        return abi

    @db_session_context
    async def test_update_seismic_contracts_info_no_abi(self):
        # Without src20_abi stored, seeding is a no-op and creates no contracts
        await update_seismic_contracts_info()
        self.assertIsNone(
            await Contract.get_contract(HexBytes(TEST_ADDRESS), TEST_CHAIN_ID)
        )

    @db_session_context
    async def test_update_seismic_contracts_info_links_abi(self):
        abi = await self._store_src20_abi()

        await update_seismic_contracts_info()

        contract = await Contract.get_contract(HexBytes(TEST_ADDRESS), TEST_CHAIN_ID)
        self.assertIsNotNone(contract)
        self.assertEqual(contract.abi_id, abi.id)
        self.assertEqual(contract.name, "SRC20")

    @db_session_context
    async def test_update_seismic_contracts_info_is_idempotent(self):
        await self._store_src20_abi()

        await update_seismic_contracts_info()
        await update_seismic_contracts_info()

        contracts = await Contract.get_all()
        matching = [c for c in contracts if c.address == HexBytes(TEST_ADDRESS)]
        self.assertEqual(len(matching), 1)

    @db_session_context
    async def test_seeded_contract_yields_full_match(self):
        # Registering the address upgrades accuracy from ONLY_FUNCTION_MATCH to FULL_MATCH
        await self._store_src20_abi()
        await update_seismic_contracts_info()

        decoder_service = DataDecoderService()
        await decoder_service.init()

        # transfer(address,suint256) selector + recipient word + encrypted amount word
        data = HexBytes(
            "0xb10c99b5"
            + "0dc0dfD22C6Beab74672EADE5F9Be5234AAa43cC".lower().rjust(64, "0")
            + f"{100000:064x}"
        )

        # Without an address: only the function matches
        self.assertEqual(
            await decoder_service.get_decoding_accuracy(data),
            DecodingAccuracyEnum.ONLY_FUNCTION_MATCH,
        )
        # With the registered address and chain id: full match
        self.assertEqual(
            await decoder_service.get_decoding_accuracy(
                data, address=TEST_ADDRESS, chain_id=TEST_CHAIN_ID
            ),
            DecodingAccuracyEnum.FULL_MATCH,
        )
