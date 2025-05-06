# Bedrock Tool Use Stalling Analysis

## Project Summary

This repository demonstrates a significant performance issue with AWS Bedrock's Claude v3.7 implementation when using tools. The project provides evidence that the Bedrock converseStream API experiences substantial stalling when generating tool inputs, particularly with large content. The delay is directly proportional to the size of the input being generated.

The repository includes three parallel implementations:
1. `bedrock-tool-use-stalling.py`: Uses AWS Bedrock's converseStream API with Claude v3.7 and API-defined ToolSpec
2. `anthropic-tool-use.py`: Uses Anthropic's Messages API directly with Claude v3.7
3. `system-prompt-tool-use.py`: Uses AWS Bedrock's converseStream API with Claude v3.7 but defines tools via system prompt instead of API ToolSpec

Both implementations show the same stalling behavior, confirming this is likely an issue with the underlying model or API implementation rather than specific to Bedrock.

## Key Findings

- The stalling occurs specifically when generating tool inputs (not during regular text generation)
- The delay increases proportionally with the size of the content being generated
- The issue is reproducible with different content sizes (500, 1000, 5000 characters)
- The same behavior is observed in both Bedrock and direct Anthropic API implementations

## Reproduction Steps

The repository includes several make targets to reproduce the issue with different content sizes:
```bash
make run-lorem-ipsum-500-tool  # 500 characters
make run-lorem-ipsum-1k-tool   # 1000 characters
make run-lorem-ipsum-5k-tool   # 5000 characters
```

For comparison with the direct Anthropic API:
```bash
make run-anthropic-lorem-ipsum-1k-tool
make run-anthropic-lorem-ipsum-2k-tool
```

For comparison with the system prompt approach:
```bash
make run-system-prompt-lorem-ipsum-1k-tool
make run-system-prompt-lorem-ipsum-5k-tool
```

The timestamps in the output clearly show the delay when generating the `file_text` parameter.
