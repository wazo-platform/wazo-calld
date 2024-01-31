import time
import uuid
from unittest import TestCase
from unittest.mock import create_autospec

from wazo_calld.http_server import app
from wazo_calld.plugins.calls.call import Call
from wazo_calld.plugins.calls.http import ConnectCallToUserResource
from wazo_calld.plugins.calls.services import CallsService


def generate_call_id() -> str:
    return str(time.time())


class TestConnectCallToUserResource(TestCase):
    def setUp(self) -> None:
        self.service = create_autospec(CallsService, instance=True)
        self.endpoint = ConnectCallToUserResource(calls_service=self.service)
        return super().setUp()

    def test_put_with_timeout(self):
        user_uuid = uuid.uuid4()
        call_id = generate_call_id()
        self.service.get.return_value = Call(call_id)
        with app.test_request_context(json={'timeout': 10}):
            response_content = self.endpoint.put(call_id, user_uuid)
        assert response_content

    def test_put_without_body(self):
        user_uuid = uuid.uuid4()
        call_id = generate_call_id()
        self.service.get.return_value = Call(call_id)
        with app.test_request_context():
            response_content = self.endpoint.put(call_id, user_uuid)
        assert response_content
