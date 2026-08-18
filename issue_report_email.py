"""Utility script to send an issue report email to multiple recipients.

This script uses the ``send_change_summary`` function defined in ``send_email.py``
to send a pre‑formatted description of the local problem we encountered with the
Ollama VS Code extension.  The recipients are the support contacts for Ollama,
GitHub and Microsoft.

The SMTP server configuration is taken from the environment variables:
``SMTP_HOST``, ``SMTP_PORT`` (default ``587``), ``SMTP_USER`` and
``SMTP_PASSWORD`` – the same variables used by ``send_email.py``.

Run the script from the workspace root::

    python issue_report_email.py

Make sure the environment variables are set before execution.
"""

import os
from send_email import send_change_summary


def build_issue_body() -> str:
    """Construct the email body describing the current local issue.

    The problem is a missing final ``Done`` part in the streaming response of
    the Ollama extension, which caused the error:
    ``Did not receive done or success response … async OllamaLanguageModelProvider.provideLanguageModelChatResponse``.
    The patch added the missing ``Done`` token, but we report the situation for
    the upstream maintainers.
    """
    return (
        "Dear Support Team,\n\n"
        "We have encountered a problem with the Ollama VS Code extension (v0.0.8).\n"
        "When invoking a chat request, the extension raised the following error:\n"
        "    Did not receive done or success response … async OllamaLanguageModelProvider.provideLanguageModelChatResponse\n"
        "The root cause appears to be that the streaming implementation did not emit a final ``Done``\n"
        "LanguageModelDataPart, which the client expects to terminate the stream.\n"
        "We added the missing termination token in `provider.js` as follows:\n"
        "    progress.report(new vscode.LanguageModelDataPart(new Uint8Array(),\n"
        "        vscode.LanguageModelDataMimeTypes.Done));\n"
        "After this change the extension no longer throws the error.\n\n"
        "We would appreciate any guidance on whether this change aligns with the\n"
        "expected protocol or if further adjustments are required.\n\n"
        "Thank you,\n"
        "The OneAP_Python development team"
    )


def main() -> None:
    # Recipients for the issue report.
    recipients = [
        "support@ollama.com",
        "support@github.com",
        "support@microsoft.com",
    ]

    subject = "Ollama VS Code Extension – Missing Done token in streaming response"
    body = build_issue_body()

    for recipient in recipients:
        try:
            send_change_summary(recipient, subject, body)
            print(f"Email sent to {recipient}")
        except Exception as e:
            print(f"Failed to send email to {recipient}: {e}")


if __name__ == "__main__":
    main()
