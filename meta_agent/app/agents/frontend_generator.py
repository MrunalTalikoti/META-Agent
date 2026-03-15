from app.agents.base_agent import BaseAgent
import re

class FrontendGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="frontend_generator")
    
    def get_system_prompt(self) -> str:
        return """You are a frontend developer expert in React, Vue, and modern UI.

Create production-ready frontend code:
1. Component-based architecture
2. Proper state management
3. Responsive design (Tailwind CSS)
4. Accessibility (ARIA labels)
5. TypeScript when beneficial

OUTPUT FORMAT:
```jsx
// Component code here
```
```css
/* Styles if needed (prefer Tailwind) */
```

Include:
- Prop types/interfaces
- Event handlers
- API integration (fetch/axios)
- Error boundaries
- Loading states"""

    def parse_output(self, raw_content: str) -> dict:
        components = re.findall(r'```(?:jsx|tsx|vue)\n(.*?)```', raw_content, re.DOTALL)
        styles = re.findall(r'```css\n(.*?)```', raw_content, re.DOTALL)
        
        return {
            "components": [c.strip() for c in components],
            "styles": [s.strip() for s in styles],
            "component_count": len(components),
        }