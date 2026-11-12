# gpt-5.6-sol large-request repro: results

Run on 2026-11-11 in us-east-2 with `gpt56-large-request-repro.py`.

## Conclusion

Large gpt-5.6-sol Responses requests return HTTP 500 `internal_server_error` on the `bedrock-mantle` endpoint. The same request bodies succeed on the `bedrock-runtime` Responses endpoint.

- `bedrock-mantle`: the cutoff is between 14 and 16 MB for bodies padded with base64 images, and between 16 and 17 MB for bodies padded with text. The 500 comes back after about 1.6 s, before any stream starts.
- `bedrock-runtime`: every size up to 20.7 MB succeeded.
- Token count is not the cause. The largest image body was about 5,400 input tokens and the largest text body about 162,000, far below the model's context window.

Error body on every 500:

```
{"error":{"code":"internal_server_error","message":"The server had an error while processing your request. Sorry about that!","param":null,"type":"server_error"}}
```

## Requests

Every body is a short text prompt padded to the target size, with `max_output_tokens` 16 and streaming on.

### Image padding

512x512 random-noise PNG images sent as `input_image` data URLs with `detail: low`, about 1 MB each.

| Endpoint | Body bytes | Images | HTTP | Result | Input tokens | Seconds |
|---|---|---|---|---|---|---|
| bedrock-mantle | 4,000 | 1 | 200 | completed | 226 | 0.7 |
| bedrock-mantle | 10,000,000 | 10 | 200 | completed | 2,531 | 3.0 |
| bedrock-mantle | 12,000,000 | 12 | 200 | completed | 3,132 | 3.4 |
| bedrock-mantle | 14,000,000 | 14 | 200 | completed | 3,494 | 3.8 |
| bedrock-mantle | 16,000,000 | 16 | 500 | internal_server_error | n/a | 1.5 |
| bedrock-mantle | 18,000,000 | 18 | 500 | internal_server_error | n/a | 1.6 |
| bedrock-mantle | 19,400,000 | 19 | 500 | internal_server_error | n/a | 1.7 |
| bedrock-mantle | 19,800,000 | 19 | 500 | internal_server_error | n/a | 1.7 |
| bedrock-mantle | 20,700,000 | 20 | 500 | internal_server_error | n/a | 1.7 |
| bedrock-runtime | 4,000 | 1 | 200 | completed | 225 | 0.7 |
| bedrock-runtime | 14,000,000 | 14 | 200 | completed | 3,493 | 8.0 |
| bedrock-runtime | 16,000,000 | 16 | 200 | completed | 4,096 | 9.4 |
| bedrock-runtime | 19,400,000 | 19 | 200 | completed | 5,015 | 11.8 |
| bedrock-runtime | 20,700,000 | 20 | 200 | completed | 5,355 | 8.8 |

### Text padding

`input_text` parts of about 1 MB each, filled with spaces (about 7,800 input tokens per MB).

| Endpoint | Body bytes | Text parts | HTTP | Result | Input tokens | Seconds |
|---|---|---|---|---|---|---|
| bedrock-mantle | 1,000,000 | 0 | 200 | completed | 7,825 | 6.0 |
| bedrock-mantle | 14,000,000 | 13 | 200 | completed | 109,384 | 57.7 |
| bedrock-mantle | 16,000,000 | 15 | 200 | completed | 125,008 | 67.1 |
| bedrock-mantle | 17,000,000 | 16 | 500 | internal_server_error | n/a | 1.5 |
| bedrock-mantle | 18,000,000 | 17 | 500 | internal_server_error | n/a | 1.6 |
| bedrock-mantle | 19,000,000 | 18 | 500 | internal_server_error | n/a | 1.7 |
| bedrock-mantle | 19,400,000 | 19 | 500 | internal_server_error | n/a | 1.7 |
| bedrock-mantle | 20,700,000 | 20 | 500 | internal_server_error | n/a | 1.7 |
| bedrock-runtime | 20,700,000 | 20 | 200 | completed | 161,725 | 115.8 |

## Endpoints

- `bedrock-mantle`: `POST https://bedrock-mantle.us-east-2.api.aws/openai/v1/responses`, model `openai.gpt-5.6-sol`.
- `bedrock-runtime`: `POST https://bedrock-runtime.us-east-2.amazonaws.com/openai/v1/responses`, model `us.openai.gpt-5.6-sol`. This endpoint needs an inference profile ID for the model.

Both use SigV4 with signing name `bedrock`.

## How to run

```
python gpt56-large-request-repro.py 14000000 --region us-east-2
python gpt56-large-request-repro.py 17000000 --region us-east-2 --pad text
python gpt56-large-request-repro.py 17000000 --region us-east-2 --pad text --endpoint runtime
```

## Open points

- **Not a like-for-like comparison.** The `bedrock-mantle` runs used the foundation model ID in us-east-2. The `bedrock-runtime` runs used the `us.` cross-Region profile, so those requests may have been served in another US Region.
- **Large text bodies are slow when they succeed.** 58 to 67 seconds on `bedrock-mantle` and 116 seconds on `bedrock-runtime`, for a 5-token reply.
- **Not tested:** bodies above 20.7 MB on `bedrock-runtime`, fewer and larger images (`--image-px`), other regions, and other models.
