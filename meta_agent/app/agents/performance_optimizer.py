from app.agents.base_agent import BaseAgent

class PerformanceOptimizerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="performance_optimizer")
    
    def get_system_prompt(self) -> str:
        return """You are a performance optimization expert.

Analyze code for:
1. Algorithmic complexity (O(n²) → O(n log n))
2. Database query optimization (N+1 queries, missing indexes)
3. Caching opportunities (Redis, memoization)
4. Memory leaks
5. Unnecessary re-renders (React)
6. Bundle size (code splitting)
7. API response time

OUTPUT JSON:
{
  "current_performance": "description",
  "bottlenecks": [
    {
      "location": "...",
      "issue": "...",
      "impact": "high|medium|low",
      "fix": "..."
    }
  ],
  "optimizations": [...]
}"""

    def parse_output(self, raw_content: str) -> dict:
        import json
        import re
        
        try:
            return json.loads(raw_content)
        except:
            match = re.search(r'```json\n(.*?)```', raw_content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        return {"bottlenecks": [], "raw": raw_content}