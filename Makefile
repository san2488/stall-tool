.PHONY: setup run run-hello-world run-hello-world-tool clean format install-dev run-anthropic run-anthropic-lorem-ipsum-5k-tool run-system-prompt

setup:
	uv venv
	uv pip install -r requirements.txt

# Format code before running
run: format
	source .venv/bin/activate && python bedrock-tool-use-stalling.py

run-hello-world:
	source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "hello world"

run-fibonacci-tool:
	rm -f ./generate-fibonacci.py && source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "write a concise program to generate fibonacci numbers into ./generate-fibonacci.py file"

run-with-timestamp:
	source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp

run-lorem-ipsum-500-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "write 500 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-lorem-ipsum-1k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "write 1000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-lorem-ipsum-5k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "write 5000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-lorem-ipsum-10k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "write 10000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-lorem-ipsum-5k-no-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python bedrock-tool-use-stalling.py --timestamp "generate 5000 characters of lorem ipsum filler text. DO NOT USE any tool"

clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf *.egg-info
	rm -rf dist
	rm -rf build

format:
	uv pip install black isort
	black .
	isort .

install-dev:
	uv pip install -e ".[dev]"

run-anthropic:
	source .venv/bin/activate && python anthropic-tool-use.py --timestamp

run-anthropic-hello-world:
	source .venv/bin/activate && python anthropic-tool-use.py --timestamp "hello world"

run-anthropic-lorem-ipsum-1k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python anthropic-tool-use.py --timestamp "write 1000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-anthropic-lorem-ipsum-2k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python anthropic-tool-use.py --timestamp "write 2000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-system-prompt-lorem-ipsum-1k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python system-prompt-tool-use.py --timestamp "write 1000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-system-prompt-lorem-ipsum-5k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python system-prompt-tool-use.py --timestamp "write 5000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"

run-system-prompt-lorem-ipsum-10k-tool:
	rm -f /tmp/lorem-ipsum.txt && source .venv/bin/activate && python system-prompt-tool-use.py --timestamp "write 10000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt"