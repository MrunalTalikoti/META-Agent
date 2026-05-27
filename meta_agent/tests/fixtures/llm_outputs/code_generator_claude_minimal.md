```
def validate_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

Simple regex-based email validation. Does not cover all edge cases from RFC 5322 but handles the vast majority of real-world email formats.
