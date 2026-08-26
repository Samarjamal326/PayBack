from unittest.mock import MagicMock, patch

from app.config import Settings
from app.services.llm.factory import get_message_generator
from app.services.llm.huggingface import HuggingFaceMessageGenerator
from app.services.llm.interface import MessageContext
from app.services.llm.mock import MockMessageGenerator
from app.services.llm.ollama import OllamaMessageGenerator


def test_provider_switching_via_config():
    cfg_mock = Settings(llm_provider="mock")
    gen_mock = get_message_generator(cfg_mock)
    assert isinstance(gen_mock, MockMessageGenerator)

    cfg_ollama = Settings(llm_provider="ollama", ollama_base_url="http://localhost:11434")
    gen_ollama = get_message_generator(cfg_ollama)
    assert isinstance(gen_ollama, OllamaMessageGenerator)

    cfg_hf = Settings(llm_provider="huggingface", huggingface_api_key="test_key")
    gen_hf = get_message_generator(cfg_hf)
    assert isinstance(gen_hf, HuggingFaceMessageGenerator)


def test_ollama_generator_with_mocked_response():
    gen = OllamaMessageGenerator()
    ctx = MessageContext(
        customer_name="Rohan",
        amount=1999.0,
        currency="INR",
        failure_reason="timeout",
        payment_link="https://rzp.io/test1234",
    )

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "Hi Rohan, your payment of INR 1,999.00 failed. Please complete it here: https://rzp.io/test1234. Reply STOP to opt out."
        }
        mock_post.return_value = mock_resp

        msg = gen.whatsapp_message(ctx)
        assert "Rohan" in msg
        assert "https://rzp.io/test1234" in msg


def test_ollama_generator_fallback_on_network_error():
    gen = OllamaMessageGenerator(base_url="http://invalid-host-9999:11434")
    ctx = MessageContext(
        customer_name="Rohan",
        amount=1999.0,
        currency="INR",
        failure_reason="timeout",
        payment_link="https://rzp.io/test1234",
    )

    # Should gracefully return safe template without throwing an exception
    msg = gen.whatsapp_message(ctx)
    assert "Rohan" in msg
    assert "1,999.00" in msg
    assert "https://rzp.io/test1234" in msg
