import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from ...config import settings
from ...datasources.db.models import Abi
from ...main import app
from ...routers.admin import AbiAdmin
from ...tests.mocks.tron_abi_mock import mock_tron_abi_json


class TestRouterAdmin(unittest.IsolatedAsyncioTestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_admin(self):
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn("DOCTYPE html", response.text)

    def test_admin_abi(self):
        # Unauthenticated requests redirect to the login page for ANY url,
        # so authentication is required to actually exercise the view
        response = self.client.get("/admin/abi/list", follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            "/admin/login",
            data={
                "username": settings.ADMIN_USERNAME,
                "password": settings.ADMIN_PASSWORD,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/admin/abi/list")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/admin/not-a-view/list")
        self.assertNotEqual(response.status_code, 200)

    async def test_abi_admin_on_model_change(self):
        data: dict = {"abi_json": mock_tron_abi_json, "relevance": 50}
        await AbiAdmin().on_model_change(data, Abi(), True, MagicMock())

        self.assertEqual(
            data["abi_json"],
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
        self.assertEqual(data["abi_hash"], bytes.fromhex("729e1289"))
