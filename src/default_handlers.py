from handler_service.message_handlers import (
    AttachmentActionSendToGCPCloudStorage,
    MessageHandler,
    MessageConditions,
)
from gmail_service import GmailService


def get_default_handlers(
    gmail: GmailService, bucket_name: str
) -> list[MessageHandler]:
    """
    Returns the default message handlers for the user.
    """

    return [
        MessageHandler(
            "Inter_Bills_01",
            MessageConditions(
                {
                    "subject": {"equal": "Fatura Cartão Inter"},
                },
            ),
            [
                AttachmentActionSendToGCPCloudStorage(
                    {"extension": "pdf"},
                    bucket_name,
                    "finance/bills/inter",
                    gmail,
                )
            ],
        ),
        MessageHandler(
            "Nubank_Bills_01",
            MessageConditions(
                {
                    "from_": {"contains": "Nubank"},
                    "subject": {"contains": "fatura"},
                    "filename": {"endswith": "pdf"},
                },
            ),
            [
                AttachmentActionSendToGCPCloudStorage(
                    {"extension": "pdf"},
                    bucket_name,
                    "finance/bills/nubank",
                    gmail,
                )
            ],
        ),
        MessageHandler(
            "Nubank_Statemets_01",
            MessageConditions(
                {
                    # "from_": {"contains": "Nubank"},
                    "subject": {"equal": "Extrato da sua conta do Nubank"}
                },
            ),
            [
                AttachmentActionSendToGCPCloudStorage(
                    {"extension": "ofx"},
                    bucket_name,
                    "finance/statements/nubank",
                    gmail,
                )
            ],
        ),
        
    ]
