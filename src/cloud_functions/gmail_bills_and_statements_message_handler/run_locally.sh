uv pip freeze > requirements.txt
mv requirements.txt src/cloud_functions/gmail_bills_and_statements_message_handler
cp env.yaml src/cloud_functions/gmail_bills_and_statements_message_handler

functions-framework \
    --source src/cloud_functions/gmail_bills_and_statements_message_handler/main.py \
    --target download_statements_and_bills_from_message_on_topic \
    --signature-type event \
    --debug

rm src/cloud_functions/gmail_bills_and_statements_message_handler/requirements.txt
rm