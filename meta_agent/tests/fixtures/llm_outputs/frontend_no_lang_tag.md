Here is a search bar component with debounced input:

```
import React, { useState, useCallback } from 'react';

function SearchBar({ onSearch, placeholder = "Search..." }) {
  const [query, setQuery] = useState('');
  const [timeoutId, setTimeoutId] = useState(null);

  const handleChange = useCallback((e) => {
    const value = e.target.value;
    setQuery(value);

    if (timeoutId) clearTimeout(timeoutId);

    const id = setTimeout(() => {
      onSearch(value);
    }, 300);
    setTimeoutId(id);
  }, [onSearch, timeoutId]);

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder={placeholder}
        className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        aria-label="Search"
      />
    </div>
  );
}

export default SearchBar;
```

Simple debounced search using setTimeout. For production, consider using a library like `use-debounce` for more robust handling.
