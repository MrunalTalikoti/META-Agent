Here's a complete user profile card component with loading and error states:

```typescript
import React, { useState, useEffect } from 'react';

interface UserProfile {
  id: number;
  name: string;
  email: string;
  avatarUrl: string;
}

interface ProfileCardProps {
  userId: number;
  onEdit?: (user: UserProfile) => void;
}

const ProfileCard: React.FC<ProfileCardProps> = ({ userId, onEdit }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await fetch(`/api/users/${userId}`);
        if (!res.ok) throw new Error('Failed to fetch user');
        const data = await res.json();
        setUser(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, [userId]);

  if (loading) return <div className="animate-pulse h-48 bg-gray-200 rounded-lg" />;
  if (error) return <div className="text-red-500 p-4" role="alert">{error}</div>;
  if (!user) return null;

  return (
    <div className="bg-white rounded-lg shadow-md p-6 max-w-sm">
      <img
        src={user.avatarUrl}
        alt={`${user.name}'s avatar`}
        className="w-20 h-20 rounded-full mx-auto"
      />
      <h2 className="text-xl font-semibold text-center mt-4">{user.name}</h2>
      <p className="text-gray-600 text-center">{user.email}</p>
      {onEdit && (
        <button
          onClick={() => onEdit(user)}
          className="mt-4 w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
          aria-label={`Edit ${user.name}'s profile`}
        >
          Edit Profile
        </button>
      )}
    </div>
  );
};

export default ProfileCard;
```

And some accompanying styles if you're not using Tailwind:

```css
.profile-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  max-width: 20rem;
}

.profile-card__avatar {
  width: 5rem;
  height: 5rem;
  border-radius: 50%;
  margin: 0 auto;
  display: block;
}
```

The component uses React hooks for data fetching with proper loading/error states. Tailwind classes handle styling inline, with a CSS fallback provided for non-Tailwind projects.
