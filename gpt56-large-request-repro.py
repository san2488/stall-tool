#!/usr/bin/env python3
"""Send one Responses API request of a chosen body size to Bedrock for gpt-5.6-sol.

--endpoint mantle (default) uses the Responses API on bedrock-mantle:
  POST https://bedrock-mantle.<region>.api.aws/openai/v1/responses, model openai.gpt-5.6-sol
--endpoint runtime uses the Responses API on bedrock-runtime:
  POST https://bedrock-runtime.<region>.amazonaws.com/openai/v1/responses, model us.openai.gpt-5.6-sol
Both: SigV4, signing name "bedrock", Content-Type application/json, Accept text/event-stream.
--pad image (default) fills the body with low-detail base64 PNG images of random noise, so the
request stays far below the model's token limit while the JSON body reaches the target size.
--pad text fills it with input_text parts of about 1 MB each, made of --filler repeated
(default: a space). Ordinary prose is about 4 bytes per token, so it would pass the model's
token limit near 4 MB; check input_tokens on a 1 MB run before sending large text bodies.

Usage: python gpt56-large-request-repro.py <target_body_bytes> [--region us-east-2]
           [--endpoint mantle|runtime] [--pad image|text] [--filler " "]
"""
import argparse
import base64
import json
import os
import struct
import time
import zlib

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Responses API on the two Bedrock endpoints. bedrock-runtime needs an inference profile ID
# for the closed-weight GPT models; bedrock-mantle takes the foundation model ID.
ENDPOINTS = {
    "mantle": ("https://bedrock-mantle.{region}.api.aws/openai/v1/responses", "openai.gpt-5.6-sol"),
    "runtime": ("https://bedrock-runtime.{region}.amazonaws.com/openai/v1/responses", "us.openai.gpt-5.6-sol"),
}
IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512
TEXT_PART_CHARS = 1_000_000  # about the same size as one padding image


def png_noise(width, height):
    """Valid RGB PNG of random noise (incompressible, so file size is about width*height*3)."""
    raw = b"".join(b"\x00" + os.urandom(width * 3) for _ in range(height))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b"")


def image_part(width, height):
    data_url = "data:image/png;base64," + base64.b64encode(png_noise(width, height)).decode("ascii")
    return {"type": "input_image", "image_url": data_url, "detail": "low"}


def text_part(length, filler):
    return {"type": "input_text", "text": (filler * (length // len(filler) + 1))[:length]}


def build_body(target_bytes, image_px, model, pad, filler):
    content = [{"type": "input_text", "text": "Reply with the single word OK."}]
    request = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": 16,
        "stream": True,
    }
    if pad == "text":
        full_part_bytes = len(json.dumps(text_part(TEXT_PART_CHARS, filler))) + 2
        while len(json.dumps(request)) + full_part_bytes <= target_bytes:
            content.append(text_part(TEXT_PART_CHARS, filler))
        tail_filler = filler
    else:
        full_image_bytes = len(json.dumps(image_part(image_px, image_px))) + 2
        while len(json.dumps(request)) + full_image_bytes <= target_bytes:
            content.append(image_part(image_px, image_px))
        row_bytes = full_image_bytes / image_px
        partial_rows = int((target_bytes - len(json.dumps(request)) - 200) / row_bytes)
        if partial_rows > 0:
            content.append(image_part(image_px, partial_rows))
        tail_filler = "a"
    tail = max(0, target_bytes - len(json.dumps(request)) - len(json.dumps({"type": "input_text", "text": ""})) - 2)
    content.append(text_part(tail, tail_filler))
    return json.dumps(request).encode("utf-8"), len(content) - 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target_bytes", type=int)
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument("--image-px", type=int, default=IMAGE_WIDTH, help="width and height of each padding image")
    parser.add_argument("--endpoint", choices=sorted(ENDPOINTS), default="mantle")
    parser.add_argument("--model", help="override the endpoint's default model ID")
    parser.add_argument("--pad", choices=["image", "text"], default="image", help="what fills the body")
    parser.add_argument("--filler", default=" ", help="text repeated to fill --pad text parts (plain ASCII, no quotes or backslashes)")
    args = parser.parse_args()

    url_template, default_model = ENDPOINTS[args.endpoint]
    model = args.model or default_model
    url = url_template.format(region=args.region)
    body, part_count = build_body(args.target_bytes, args.image_px, model, args.pad, args.filler)
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    aws_request = AWSRequest(method="POST", url=url, data=body, headers=headers)
    SigV4Auth(boto3.Session().get_credentials().get_frozen_credentials(), "bedrock", args.region).add_auth(aws_request)

    start = time.time()
    response = requests.post(url, data=body, headers=dict(aws_request.headers), stream=True, timeout=300)
    first_byte_seconds = time.time() - start
    text = response.content.decode("utf-8", errors="replace")
    total_seconds = time.time() - start

    usage = None
    terminal_event = None
    for line in text.splitlines():
        if line.startswith("data: ") and '"type"' in line and line != "data: [DONE]":
            event = json.loads(line[len("data: "):])
            if event.get("type") in ("response.completed", "response.incomplete", "response.failed", "error"):
                terminal_event = event.get("type")
                usage = (event.get("response") or {}).get("usage")

    request_ids = {k: v for k, v in response.headers.items() if "request" in k.lower() or k.lower().startswith("x-amz")}
    print(json.dumps({
        "url": url,
        "model": model,
        "target_bytes": args.target_bytes,
        "actual_body_bytes": len(body),
        "pad": args.pad,
        "padding_parts": part_count,
        "http_status": response.status_code,
        "seconds_to_headers": round(first_byte_seconds, 3),
        "seconds_total": round(total_seconds, 3),
        "request_id_headers": request_ids,
        "terminal_event": terminal_event,
        "usage": usage,
        "body_first_500": text[:500],
    }, indent=2))


if __name__ == "__main__":
    main()
