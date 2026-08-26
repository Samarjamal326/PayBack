from app.models.domain import DeliveryProvider, MessageChannel, MessageStatus
from app.services.messaging.factory import get_delivery_provider
from app.services.messaging.mock import MockDeliveryProvider
from app.services.messaging.email_provider import EmailDeliveryProvider
from app.services.messaging.whatsapp_provider import WhatsAppDeliveryProvider


def test_mock_delivery_provider_email():
    provider = MockDeliveryProvider()
    result = provider.send_email(
        recipient_email="test@example.com",
        subject="Payment Link",
        body_html="<p>Click here</p>",
    )
    assert result.success is True
    assert result.channel == MessageChannel.EMAIL
    assert result.provider == DeliveryProvider.MOCK
    assert result.status == MessageStatus.DELIVERED
    assert result.provider_message_id.startswith("mock_email_")


def test_mock_delivery_provider_whatsapp():
    provider = MockDeliveryProvider()
    result = provider.send_whatsapp(
        recipient_phone="+919876543210",
        message="Hi Priya, please complete your payment.",
    )
    assert result.success is True
    assert result.channel == MessageChannel.WHATSAPP
    assert result.status == MessageStatus.DELIVERED


def test_email_provider_unconfigured_fallback():
    # When credentials absent, gracefully simulates delivery without crashing
    provider = EmailDeliveryProvider()
    assert not provider.is_configured
    result = provider.send_email("user@example.com", "Subject", "<p>Body</p>")
    assert result.success is True
    assert result.status == MessageStatus.DELIVERED


def test_whatsapp_provider_unconfigured_fallback():
    # When credentials absent, gracefully simulates delivery without crashing
    provider = WhatsAppDeliveryProvider()
    assert not provider.is_configured
    result = provider.send_whatsapp("+919876543210", "Message")
    assert result.success is True
    assert result.status == MessageStatus.DELIVERED
