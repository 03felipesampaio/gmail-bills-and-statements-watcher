# Gmail Bills and Statements Watcher

This project implements a real-time pipeline to ingest messages from Gmail accounts into a message queue (Google Pub/Sub). It automates the setup of credentials, manages Gmail API integration, and handles Google’s OAuth authorization and authentication flows.

Incoming Gmail messages are published to Pub/Sub topics within seconds of arrival. The project also provides a consumer example that fetches messages from the topic and, if they contain a statement or bill from your banks, downloads the file and sends it to Google Cloud Storage.

It is designed for seamless, secure, and scalable processing of financial documents received via email.

## Features

- **gmail_bills_and_statements_message_handler**  
  Consumes the Pub/Sub topic, filters for statements and bills, and downloads and stores files on Google Cloud Storage. Triggered by new messages on the topic using Google Cloud Eventarc.

- **gmail_bills_and_statements_message_watcher**  
  Refreshes OAuth credentials for Google accounts and renews the subscription to the Pub/Sub topic. The Gmail API must be called at least once a week to keep sending messages to the topic. Triggered by an HTTP request, scheduled to run every 5 days by Google Cloud Scheduler.

- **gmail_bills_and_statements_oauth_callback**  
  Helper function that receives the response from the OAuth request and stores the credentials in Firestore.

- Watches Gmail accounts for new bills and statements using the Gmail API.
- Handles Pub/Sub messages triggered by Gmail events.
- Stores user and watch configuration data in Firestore.
- Manages OAuth credentials securely via Secret Manager.
- Supports scheduled refresh of Gmail watch using Cloud Scheduler.
- Modular codebase with clear separation of concerns.
- Example consumer for downloading and storing bank statements/bills in Google Cloud Storage.

## Project Structure

```
src/cloud_functions/
  gmail_bills_and_statements_message_handler/
    main.py
  gmail_bills_and_statements_message_watcher/
    main.py
    repository.py
    gmail.py
    dto.py
    run_mock_payload.sh
  gmail_bills_and_statements_oauth_callback/
    main.py
```

- `main.py`: Entry points for each Cloud Function.
- `repository.py`: Firestore abstraction for user and watch data.
- `gmail.py`: Gmail API integration logic.
- `dto.py`: Data transfer objects and models.
- `run_mock_payload.sh`: Script for local testing.

## Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd gmail-bills-and-statements-watcher
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Edit `env.yaml` with your Google Cloud project settings and secret names.

4. **Deploy Cloud Functions:**
   - Use the provided GitHub Actions workflow or run deployment scripts manually.

## Deployment

Deployment is automated via GitHub Actions. The workflow:
- Installs dependencies using `uv`.
- Deploys the Cloud Function with `gcloud functions deploy`.
- Retrieves the function URL.
- Creates or updates a Cloud Scheduler job to trigger the function periodically.

## Usage

- The main Cloud Function is triggered by HTTP (for watch refresh) and Pub/Sub (for message handling).
- OAuth credentials are managed via Google Secret Manager.
- Firestore is used for persistent storage of user and watch data.
- Example consumer fetches messages from Pub/Sub and processes bank statements/bills.

## Configuration

- `env.yaml`: Contains environment variables such as project ID, region, secret names, and Firestore database ID.
- `pyproject.toml` and `requirements.txt`: Python dependencies.

## Development

- Use `run_mock_payload.sh` to test functions locally.
- Logging is handled via `loguru`.