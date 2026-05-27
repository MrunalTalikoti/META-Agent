import re

from app.agents.base_agent import BaseAgent
from app.utils.logger import logger

_BLOCK_RE = re.compile(
    r'```(\w+)?\s*\n(.*?)```',
    re.DOTALL,
)

_COMPONENT_LANGS = {
    "jsx", "tsx", "vue",
    "js", "ts",
    "javascript", "typescript",
    "react",
}

_STYLE_LANGS = {"css", "scss", "sass", "less", "postcss", "tailwind"}

_COMPONENT_SIGNALS = re.compile(
    r'(?:'
    r'import\s+.*?(?:react|vue|svelte)'
    r'|export\s+(?:default\s+)?(?:function|const|class)\s+\w+'
    r'|(?:useState|useEffect|useRef|useMemo)\s*\('
    r'|<template>'
    r'|render\s*\('
    r')',
    re.IGNORECASE,
)


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

OUTPUT FORMAT: One fenced code block per component using `tsx` or `jsx`
language tags.  Put styles in separate `css` blocks.

```tsx
// ComponentName.tsx
```
```css
/* styles */
```

Include:
- Prop types/interfaces
- Event handlers
- API integration (fetch/axios)
- Error boundaries
- Loading states"""

    def parse_output(self, raw_content: str) -> dict:
        components: list[str] = []
        styles: list[str] = []

        for lang, body in _BLOCK_RE.findall(raw_content):
            body = body.strip()
            if not body:
                continue
            lang = (lang or "").lower()

            if lang in _STYLE_LANGS:
                styles.append(body)
            elif lang in _COMPONENT_LANGS:
                components.append(body)
            elif _COMPONENT_SIGNALS.search(body):
                components.append(body)

        if not components:
            logger.warning("Frontend agent: no components extracted from LLM output")
            return {
                "components": [],
                "styles": [s for s in styles],
                "component_count": 0,
                "raw_output": raw_content,
                "warning": "Could not extract any components from LLM response",
            }

        return {
            "components": components,
            "styles": styles,
            "component_count": len(components),
        }
