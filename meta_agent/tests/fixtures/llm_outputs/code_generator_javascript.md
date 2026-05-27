Here's the Express.js middleware for rate limiting:

```javascript
const rateLimit = require('express-rate-limit');

const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  message: {
    error: 'Too many requests, please try again later.',
    retryAfter: '15 minutes'
  },
  standardHeaders: true,
  legacyHeaders: false,
});

module.exports = { apiLimiter };
```

This uses the `express-rate-limit` package with a 15-minute sliding window. The `standardHeaders` flag enables `RateLimit-*` headers per the IETF draft standard.
