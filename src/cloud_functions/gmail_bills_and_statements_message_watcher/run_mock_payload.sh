curl -X POST "http://127.0.0.1:8080" \
-H "Authorization: bearer $(gcloud auth print-identity-token)" \
-H "Content-Type: application/json" \
-d '{
  "userId": "me"
}'