curl -X POST "http://localhost:8080" \
  -H "Content-Type: application/json" \
  -H "ce-specversion: 1.0" \
  -H "ce-type: google.cloud.pubsub.topic.v1.messagePublished" \
  -H "ce-source: //pubsub.googleapis.com/projects/YOUR_PROJECT/topics/YOUR_TOPIC" \
  -H "ce-id: test-1234" \
  -H "ce-time: $(date -Iseconds)" \
  -d '{
    "message": {
      "data": "!!!! Add payload here !!! It has to be encoded in base64!"
    }
  }'