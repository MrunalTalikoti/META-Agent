import json
import re
from app.agents.base_agent import BaseAgent


class APIDesignerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="api_designer")

    def get_system_prompt(self) -> str:
        return """You are an expert API architect specializing in RESTful API design.

Your responsibilities:
1. Design clean, intuitive API endpoints following REST conventions
2. Define proper HTTP methods (GET, POST, PUT, PATCH, DELETE)
3. Specify request and response schemas with data types
4. Include authentication requirements
5. Define error responses (400, 401, 403, 404, 500)
6. Add rate limiting considerations

CRITICAL: Return ONLY valid JSON. No markdown, no explanation outside the JSON.

OUTPUT FORMAT (exact structure required):
{
  "base_url": "/api/v1",
  "authentication": "JWT Bearer Token|OAuth2|API Key|None",
  "endpoints": [
    {
      "path": "/resource",
      "method": "GET|POST|PUT|PATCH|DELETE",
      "description": "What this endpoint does",
      "auth_required": true,
      "request_body": {
        "field_name": "type (string|integer|boolean|array|object)"
      },
      "response_200": {
        "field_name": "type"
      },
      "error_responses": [
        {"code": 400, "description": "Bad request"},
        {"code": 401, "description": "Unauthorized"}
      ],
      "rate_limit": "100 requests per minute"
    }
  ],
  "notes": "Important design decisions or considerations"
}

Examples:
- User authentication API → JWT with /register, /login, /logout, /me
- Blog API → CRUD for posts with pagination and filtering
- E-commerce → Products, cart, orders with proper relationships"""

    def parse_output(self, raw_content: str) -> dict:
        """Extract and validate API design JSON"""
        try:
            # Try direct JSON parse
            api_design = json.loads(raw_content)
        except json.JSONDecodeError:
            # Try to extract from markdown code block
            json_match = re.search(r'```(?:json)?\n?(.*?)```', raw_content, re.DOTALL)
            if json_match:
                api_design = json.loads(json_match.group(1))
            else:
                # Look for any JSON object
                json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if json_match:
                    api_design = json.loads(json_match.group(0))
                else:
                    return {"error": "No valid JSON found", "raw_output": raw_content}

        # Validate required keys
        if "endpoints" not in api_design:
            return {"error": "Missing 'endpoints' key", "raw_output": raw_content}

        return {
            "api_design": api_design,
            "endpoint_count": len(api_design.get("endpoints", [])),
            "base_url": api_design.get("base_url", "/api/v1"),
            "auth_method": api_design.get("authentication", "Not specified"),
        }