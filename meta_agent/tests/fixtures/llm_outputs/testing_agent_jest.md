Here are the tests for the user authentication module:

```js
const { AuthService } = require('../src/auth');

describe('AuthService', () => {
  let auth;
  let mockDb;

  beforeEach(() => {
    mockDb = {
      findUser: jest.fn(),
      createUser: jest.fn(),
    };
    auth = new AuthService(mockDb);
  });

  describe('register', () => {
    it('should create user with hashed password', async () => {
      mockDb.createUser.mockResolvedValue({ id: 1, email: 'test@test.com' });

      const user = await auth.register('test@test.com', 'password123');

      expect(user.email).toBe('test@test.com');
      expect(mockDb.createUser).toHaveBeenCalledTimes(1);
    });

    it('should reject duplicate emails', async () => {
      mockDb.findUser.mockResolvedValue({ id: 1 });

      await expect(auth.register('dup@test.com', 'pass'))
        .rejects.toThrow('already exists');
    });

    it('should reject short passwords', async () => {
      await expect(auth.register('test@test.com', '123'))
        .rejects.toThrow('at least 8 characters');
    });
  });

  describe('login', () => {
    it('should return token for valid credentials', async () => {
      mockDb.findUser.mockResolvedValue({
        id: 1,
        email: 'test@test.com',
        passwordHash: '$2b$10$validhash',
      });

      const result = await auth.login('test@test.com', 'password123');

      expect(result).toHaveProperty('token');
      expect(typeof result.token).toBe('string');
    });

    it('should return null for invalid password', async () => {
      mockDb.findUser.mockResolvedValue({ id: 1, passwordHash: 'wrong' });

      const result = await auth.login('test@test.com', 'badpass');

      expect(result).toBeNull();
    });
  });
});
```

Tests cover the happy path, duplicate detection, password validation, and auth failure. The database is mocked to isolate the service logic.
