from twilio.rest import Client
from django.conf import settings

def send_verification_code(phone_number: str):
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID).verifications.create(
            to=phone_number,
            channel="sms"
        )
        return True
    except Exception as e:
        print(e)
        return False


def check_verification_code(phone_number: str, code: str):
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        result = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID).verification_checks.create(
            to=phone_number,
            code=code
        )
        return result.status == "approved"
    except Exception as e:
        print(e)
        return False