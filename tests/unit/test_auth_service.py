"""
Unit tests for authentication service functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, status

# Assuming we have these modules (adjust imports based on actual structure)
from src.auth.service import AuthService
from src.auth.models import User, Token
from src.auth.schemas import UserCreate, TokenData
from src.common.exceptions import AuthenticationError, ValidationError


class TestAuthService:
    """Test suite for AuthService class."""
    
    @pytest.fixture
    def mock_user_repository(self):
        """Mock user repository."""
        mock = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_token_repository(self):
        """Mock token repository."""
        mock = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_password_hasher(self):
        """Mock password hasher."""
        mock = MagicMock()
        mock.hash_password.return_value = "hashed_password"
        mock.verify_password.return_value = True
        return mock
    
    @pytest.fixture
    def auth_service(self, mock_user_repository, mock_token_repository, mock_password_hasher):
        """Create AuthService instance with mocks."""
        service = AuthService(
            user_repository=mock_user_repository,
            token_repository=mock_token_repository,
            password_hasher=mock_password_hasher,
            jwt_secret="test-secret",
            jwt_algorithm="HS256",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7
        )
        return service
    
    @pytest.fixture
    def sample_user(self, sample_user_data):
        """Create sample user object."""
        return User(**sample_user_data)
    
    @pytest.fixture
    def user_create_data(self):
        """Sample user creation data."""
        return UserCreate(
            email="newuser@example.com",
            password="securepassword123",
            name="New User",
            tenant_id="test-tenant-id"
        )

    @pytest.mark.unit
    async def test_create_user_success(self, auth_service, mock_user_repository, user_create_data):
        """Test successful user creation."""
        # Mock repository responses
        mock_user_repository.get_by_email.return_value = None  # Email not taken
        mock_user_repository.create.return_value = User(
            id="new-user-id",
            email=user_create_data.email,
            name=user_create_data.name,
            tenant_id=user_create_data.tenant_id,
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Execute
        user = await auth_service.create_user(user_create_data)
        
        # Verify
        assert user.email == user_create_data.email
        assert user.name == user_create_data.name
        assert user.tenant_id == user_create_data.tenant_id
        assert user.is_active is True
        
        # Verify repository calls
        mock_user_repository.get_by_email.assert_called_once_with(user_create_data.email)
        mock_user_repository.create.assert_called_once()

    @pytest.mark.unit
    async def test_create_user_email_already_exists(self, auth_service, mock_user_repository, sample_user, user_create_data):
        """Test user creation with existing email."""
        # Mock existing user
        mock_user_repository.get_by_email.return_value = sample_user
        
        # Execute and verify exception
        with pytest.raises(ValidationError) as exc_info:
            await auth_service.create_user(user_create_data)
        
        assert "Email already registered" in str(exc_info.value)
        mock_user_repository.create.assert_not_called()

    @pytest.mark.unit
    async def test_authenticate_user_success(self, auth_service, mock_user_repository, sample_user):
        """Test successful user authentication."""
        # Mock repository response
        mock_user_repository.get_by_email.return_value = sample_user
        
        # Execute
        authenticated_user = await auth_service.authenticate_user("test@example.com", "password123")
        
        # Verify
        assert authenticated_user.id == sample_user.id
        assert authenticated_user.email == sample_user.email
        mock_user_repository.get_by_email.assert_called_once_with("test@example.com")

    @pytest.mark.unit
    async def test_authenticate_user_invalid_email(self, auth_service, mock_user_repository):
        """Test authentication with invalid email."""
        # Mock no user found
        mock_user_repository.get_by_email.return_value = None
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user("nonexistent@example.com", "password123")
        
        assert "Invalid credentials" in str(exc_info.value)

    @pytest.mark.unit
    async def test_authenticate_user_invalid_password(self, auth_service, mock_user_repository, mock_password_hasher, sample_user):
        """Test authentication with invalid password."""
        # Mock user found but wrong password
        mock_user_repository.get_by_email.return_value = sample_user
        mock_password_hasher.verify_password.return_value = False
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user("test@example.com", "wrongpassword")
        
        assert "Invalid credentials" in str(exc_info.value)

    @pytest.mark.unit
    async def test_authenticate_user_inactive_user(self, auth_service, mock_user_repository, sample_user):
        """Test authentication with inactive user."""
        # Mock inactive user
        sample_user.is_active = False
        mock_user_repository.get_by_email.return_value = sample_user
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user("test@example.com", "password123")
        
        assert "Account is inactive" in str(exc_info.value)

    @pytest.mark.unit
    def test_create_access_token(self, auth_service, sample_user):
        """Test access token creation."""
        # Execute
        token = auth_service.create_access_token(sample_user)
        
        # Verify token structure
        assert isinstance(token, str)
        
        # Decode and verify payload
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["sub"] == sample_user.id
        assert payload["email"] == sample_user.email
        assert payload["tenant_id"] == sample_user.tenant_id
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    @pytest.mark.unit
    def test_create_refresh_token(self, auth_service, sample_user):
        """Test refresh token creation."""
        # Execute
        token = auth_service.create_refresh_token(sample_user)
        
        # Verify token structure
        assert isinstance(token, str)
        
        # Decode and verify payload
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["sub"] == sample_user.id
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload

    @pytest.mark.unit
    def test_verify_token_valid_access_token(self, auth_service, sample_user):
        """Test verification of valid access token."""
        # Create token
        token = auth_service.create_access_token(sample_user)
        
        # Execute
        token_data = auth_service.verify_token(token, "access")
        
        # Verify
        assert token_data.user_id == sample_user.id
        assert token_data.email == sample_user.email
        assert token_data.tenant_id == sample_user.tenant_id
        assert token_data.token_type == "access"

    @pytest.mark.unit
    def test_verify_token_expired(self, auth_service, sample_user):
        """Test verification of expired token."""
        # Create token with negative expiry (already expired)
        with patch('src.auth.service.datetime') as mock_datetime:
            # Mock current time to be in the past when creating token
            past_time = datetime.utcnow() - timedelta(hours=1)
            mock_datetime.utcnow.return_value = past_time
            
            token = auth_service.create_access_token(sample_user)
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            auth_service.verify_token(token, "access")
        
        assert "Token has expired" in str(exc_info.value)

    @pytest.mark.unit
    def test_verify_token_invalid_signature(self, auth_service):
        """Test verification of token with invalid signature."""
        # Create token with different secret
        fake_token = jwt.encode(
            {"sub": "user-id", "type": "access", "exp": datetime.utcnow() + timedelta(minutes=30)},
            "wrong-secret",
            algorithm="HS256"
        )
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            auth_service.verify_token(fake_token, "access")
        
        assert "Invalid token" in str(exc_info.value)

    @pytest.mark.unit
    def test_verify_token_wrong_type(self, auth_service, sample_user):
        """Test verification of token with wrong type."""
        # Create refresh token but verify as access token
        token = auth_service.create_refresh_token(sample_user)
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            auth_service.verify_token(token, "access")
        
        assert "Invalid token type" in str(exc_info.value)

    @pytest.mark.unit
    async def test_refresh_token_success(self, auth_service, mock_user_repository, mock_token_repository, sample_user):
        """Test successful token refresh."""
        # Create refresh token
        refresh_token = auth_service.create_refresh_token(sample_user)
        
        # Mock repository responses
        mock_user_repository.get_by_id.return_value = sample_user
        mock_token_repository.is_token_blacklisted.return_value = False
        
        # Execute
        new_tokens = await auth_service.refresh_token(refresh_token)
        
        # Verify
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert isinstance(new_tokens["access_token"], str)
        assert isinstance(new_tokens["refresh_token"], str)
        
        # Verify new tokens are different
        assert new_tokens["refresh_token"] != refresh_token

    @pytest.mark.unit
    async def test_refresh_token_blacklisted(self, auth_service, mock_token_repository, sample_user):
        """Test refresh with blacklisted token."""
        # Create refresh token
        refresh_token = auth_service.create_refresh_token(sample_user)
        
        # Mock blacklisted token
        mock_token_repository.is_token_blacklisted.return_value = True
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.refresh_token(refresh_token)
        
        assert "Token has been revoked" in str(exc_info.value)

    @pytest.mark.unit
    async def test_logout_user_success(self, auth_service, mock_token_repository, sample_user):
        """Test successful user logout."""
        # Create tokens
        access_token = auth_service.create_access_token(sample_user)
        refresh_token = auth_service.create_refresh_token(sample_user)
        
        # Execute
        await auth_service.logout_user(access_token, refresh_token)
        
        # Verify tokens are blacklisted
        assert mock_token_repository.blacklist_token.call_count == 2

    @pytest.mark.unit
    async def test_get_current_user_success(self, auth_service, mock_user_repository, sample_user):
        """Test getting current user from token."""
        # Create token
        token = auth_service.create_access_token(sample_user)
        
        # Mock repository response
        mock_user_repository.get_by_id.return_value = sample_user
        
        # Execute
        current_user = await auth_service.get_current_user(token)
        
        # Verify
        assert current_user.id == sample_user.id
        assert current_user.email == sample_user.email
        mock_user_repository.get_by_id.assert_called_once_with(sample_user.id)

    @pytest.mark.unit
    async def test_get_current_user_not_found(self, auth_service, mock_user_repository, sample_user):
        """Test getting current user when user not found."""
        # Create token
        token = auth_service.create_access_token(sample_user)
        
        # Mock user not found
        mock_user_repository.get_by_id.return_value = None
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.get_current_user(token)
        
        assert "User not found" in str(exc_info.value)

    @pytest.mark.unit
    async def test_update_user_password_success(self, auth_service, mock_user_repository, mock_password_hasher, sample_user):
        """Test successful password update."""
        # Mock current password verification
        mock_password_hasher.verify_password.return_value = True
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.update.return_value = sample_user
        
        # Execute
        updated_user = await auth_service.update_user_password(
            sample_user.id,
            "oldpassword",
            "newpassword123"
        )
        
        # Verify
        assert updated_user.id == sample_user.id
        mock_password_hasher.verify_password.assert_called_once_with("oldpassword", sample_user.hashed_password)
        mock_password_hasher.hash_password.assert_called_once_with("newpassword123")
        mock_user_repository.update.assert_called_once()

    @pytest.mark.unit
    async def test_update_user_password_wrong_current_password(self, auth_service, mock_user_repository, mock_password_hasher, sample_user):
        """Test password update with wrong current password."""
        # Mock wrong current password
        mock_password_hasher.verify_password.return_value = False
        mock_user_repository.get_by_id.return_value = sample_user
        
        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.update_user_password(
                sample_user.id,
                "wrongpassword",
                "newpassword123"
            )
        
        assert "Current password is incorrect" in str(exc_info.value)
        mock_user_repository.update.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.parametrize("password", [
        "short",          # Too short
        "nouppercase1",   # No uppercase
        "NOLOWERCASE1",   # No lowercase
        "NoNumbers",      # No numbers
        "Simple1",        # Too simple
    ])
    async def test_validate_password_strength_weak_passwords(self, auth_service, password):
        """Test password strength validation with weak passwords."""
        with pytest.raises(ValidationError) as exc_info:
            auth_service._validate_password_strength(password)
        
        assert "Password does not meet requirements" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.parametrize("password", [
        "SecurePassword123!",
        "AnotherGood1Pass",
        "MySecretKey2024",
    ])
    async def test_validate_password_strength_strong_passwords(self, auth_service, password):
        """Test password strength validation with strong passwords."""
        # Should not raise exception
        auth_service._validate_password_strength(password)

    @pytest.mark.unit
    async def test_rate_limiting_login_attempts(self, auth_service, mock_user_repository):
        """Test rate limiting for login attempts."""
        # Mock multiple failed attempts
        mock_user_repository.get_by_email.return_value = None
        
        email = "test@example.com"
        
        # Make multiple failed attempts
        for _ in range(5):
            with pytest.raises(AuthenticationError):
                await auth_service.authenticate_user(email, "wrongpassword")
        
        # Next attempt should be rate limited
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user(email, "wrongpassword")
        
        assert "Too many failed attempts" in str(exc_info.value)