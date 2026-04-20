"""Mock tool executor for benchmark testing."""
import json
from pathlib import Path


class MockToolExecutor:
    """Simulates tool execution without actual file operations."""
    
    def __init__(self, fixtures_path="benchmark/fixtures/pets-workshop"):
        self.fixtures_path = Path(fixtures_path)
        self.call_count = 0
    
    def execute(self, tool_name, tool_input):
        """Execute a mock tool and return deterministic response."""
        self.call_count += 1
        
        if tool_name == "fs_read":
            return self._mock_fs_read(tool_input)
        elif tool_name == "fs_write":
            return self._mock_fs_write(tool_input)
        elif tool_name == "file_list":
            return self._mock_file_list(tool_input)
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}
    
    def _mock_fs_read(self, tool_input):
        """Mock file read operation."""
        path = tool_input.get("path", "")
        
        # Return actual content if file exists in fixtures
        full_path = self.fixtures_path / path.lstrip("/")
        if full_path.exists() and full_path.is_file():
            try:
                content = full_path.read_text()
                return {"status": "success", "content": content}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        # Return mock content
        return {
            "status": "success",
            "content": f"# Mock content for {path}\n# File read simulated\n"
        }
    
    def _mock_fs_write(self, tool_input):
        """Mock file write operation."""
        path = tool_input.get("path", "")
        content = tool_input.get("file_text", "")
        
        return {
            "status": "success",
            "message": f"File written to {path} ({len(content)} bytes)"
        }
    
    def _mock_file_list(self, tool_input):
        """Mock directory listing."""
        path = tool_input.get("path", "")
        
        return {
            "status": "success",
            "files": ["file1.py", "file2.py", "README.md"]
        }
    
    def reset(self):
        """Reset call counter."""
        self.call_count = 0
