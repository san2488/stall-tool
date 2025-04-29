.PHONY: setup run run-hello-world run-hello-world-tool clean format install-dev

setup:
	uv venv
	uv pip install -r requirements.txt

# Format code before running
run: format
	source .venv/bin/activate && python bedrock-tool-use-stalling.py

run-hello-world:
	source .venv/bin/activate && python bedrock-tool-use-stalling.py "hello world"

run-hello-world-tool:
	rm -f ./generate-fibonacci.py && source .venv/bin/activate && python bedrock-tool-use-stalling.py "write a concise program to generate fibonacci numbers into ./generate-fibonacci.py file"

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
