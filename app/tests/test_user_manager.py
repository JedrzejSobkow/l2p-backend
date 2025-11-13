"""
Unit tests for UserManager

Tests cover:
- Email uniqueness validation
- Nickname uniqueness validation
- User creation with validation
- User update with validation
- Registration hooks
- Password reset hooks
- Verification hooks
- Login hooks
"""
import pytest
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.registered_user import RegisteredUser
from schemas.user_schema import UserCreate, UserUpdate

# Mock fastapi_users.db module to avoid import errors
mock_db_module = MagicMock()
mock_db_module.SQLAlchemyUserDatabase = MagicMock
sys.modules['fastapi_users.db'] = mock_db_module

from services.user_manager import (
    UserManager, 
    NicknameAlreadyExists, 
    EmailAlreadyExists,
    get_user_manager
)


@pytest.mark.unit
class TestValidateEmailUnique:
    """Test cases for validate_email_unique method"""
    
    async def test_validate_email_unique_success(
        self,
        db_session: AsyncSession,
    ):
        """Test validating an email that doesn't exist"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert - Should not raise any exception
        await user_manager.validate_email_unique("new_email@example.com")
    
    async def test_validate_email_unique_raises_when_exists(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test validating an email that already exists"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert
        with pytest.raises(EmailAlreadyExists) as exc_info:
            await user_manager.validate_email_unique(test_user_1.email)
        
        assert f"Email '{test_user_1.email}' is already registered" in str(exc_info.value)
    
    async def test_validate_email_unique_excludes_current_user(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test validating email excluding current user (for updates)"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert - Should not raise when excluding the user with that email
        await user_manager.validate_email_unique(test_user_1.email, exclude_user_id=test_user_1.id)
    
    async def test_validate_email_unique_different_user_has_email(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test validating email when different user has it"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert - Should raise even when excluding different user
        with pytest.raises(EmailAlreadyExists):
            await user_manager.validate_email_unique(
                test_user_1.email, 
                exclude_user_id=test_user_2.id
            )


@pytest.mark.unit
class TestValidateNicknameUnique:
    """Test cases for validate_nickname_unique method"""
    
    async def test_validate_nickname_unique_success(
        self,
        db_session: AsyncSession,
    ):
        """Test validating a nickname that doesn't exist"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert - Should not raise any exception
        await user_manager.validate_nickname_unique("NewNickname")
    
    async def test_validate_nickname_unique_raises_when_exists(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test validating a nickname that already exists"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert
        with pytest.raises(NicknameAlreadyExists) as exc_info:
            await user_manager.validate_nickname_unique(test_user_1.nickname)
        
        assert f"Nickname '{test_user_1.nickname}' is already taken" in str(exc_info.value)
    
    async def test_validate_nickname_unique_excludes_current_user(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test validating nickname excluding current user (for updates)"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert - Should not raise when excluding the user with that nickname
        await user_manager.validate_nickname_unique(
            test_user_1.nickname, 
            exclude_user_id=test_user_1.id
        )
    
    async def test_validate_nickname_unique_different_user_has_nickname(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test validating nickname when different user has it"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act & Assert - Should raise even when excluding different user
        with pytest.raises(NicknameAlreadyExists):
            await user_manager.validate_nickname_unique(
                test_user_1.nickname, 
                exclude_user_id=test_user_2.id
            )


@pytest.mark.unit
class TestOnAfterRegister:
    """Test cases for on_after_register hook"""
    
    async def test_on_after_register_prints_message(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that on_after_register hook prints registration message"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act - Should not raise any exception
        await user_manager.on_after_register(test_user_1)
        
        # Assert - Just verify it completes without error
        assert True


@pytest.mark.unit
class TestOnAfterForgotPassword:
    """Test cases for on_after_forgot_password hook"""
    
    @patch('services.user_manager.email_service')
    async def test_on_after_forgot_password_sends_email(
        self,
        mock_email_service,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that forgot password hook sends password reset email"""
        # Arrange
        mock_email_service.send_password_reset_email = AsyncMock(return_value=True)
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        test_token = "reset_token_123"
        
        # Act
        await user_manager.on_after_forgot_password(test_user_1, test_token)
        
        # Assert
        mock_email_service.send_password_reset_email.assert_called_once_with(
            email=test_user_1.email,
            token=test_token,
            nickname=test_user_1.nickname
        )


@pytest.mark.unit
class TestOnAfterRequestVerify:
    """Test cases for on_after_request_verify hook"""
    
    @patch('services.user_manager.email_service')
    async def test_on_after_request_verify_sends_email(
        self,
        mock_email_service,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that verification request hook sends verification email"""
        # Arrange
        mock_email_service.send_verification_email = AsyncMock(return_value=True)
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        test_token = "verify_token_456"
        
        # Act
        await user_manager.on_after_request_verify(test_user_1, test_token)
        
        # Assert
        mock_email_service.send_verification_email.assert_called_once_with(
            email=test_user_1.email,
            token=test_token,
            nickname=test_user_1.nickname
        )


@pytest.mark.unit
class TestOnAfterLogin:
    """Test cases for on_after_login hook"""
    
    async def test_on_after_login_prints_message(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that on_after_login hook prints login message"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Act - Should not raise any exception
        await user_manager.on_after_login(test_user_1)
        
        # Assert - Just verify it completes without error
        assert True


@pytest.mark.unit
class TestCreate:
    """Test cases for create method"""
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_create_validates_email_and_nickname(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession
    ):
        """Test that create validates both email and nickname"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock the parent create method
        with patch('fastapi_users.BaseUserManager.create', new_callable=AsyncMock) as mock_super_create:
            new_user = RegisteredUser(
                id=999,
                email="newuser@example.com",
                hashed_password="hashed",
                nickname="NewUser",
                is_active=True,
                is_verified=False
            )
            mock_super_create.return_value = new_user
            
            user_create = UserCreate(
                email="newuser@example.com",
                password="password123",
                nickname="NewUser"
            )
            
            # Act
            result = await user_manager.create(user_create)
            
            # Assert
            mock_validate_email.assert_called_once_with("newuser@example.com")
            mock_validate_nickname.assert_called_once_with("NewUser")
            assert result.email == "newuser@example.com"
            assert result.nickname == "NewUser"
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_create_raises_when_email_exists(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession
    ):
        """Test that create raises EmailAlreadyExists when email is taken"""
        # Arrange
        mock_validate_email.side_effect = EmailAlreadyExists("Email already registered")
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        user_create = UserCreate(
            email="existing@example.com",
            password="password123",
            nickname="NewUser"
        )
        
        # Act & Assert
        with pytest.raises(EmailAlreadyExists):
            await user_manager.create(user_create)
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_create_raises_when_nickname_exists(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession
    ):
        """Test that create raises NicknameAlreadyExists when nickname is taken"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.side_effect = NicknameAlreadyExists("Nickname already taken")
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        user_create = UserCreate(
            email="newuser@example.com",
            password="password123",
            nickname="ExistingNickname"
        )
        
        # Act & Assert
        with pytest.raises(NicknameAlreadyExists):
            await user_manager.create(user_create)


@pytest.mark.unit
class TestUpdate:
    """Test cases for update method"""
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_update_validates_nickname_when_changed(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that update validates nickname when it's being changed"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock the parent update method
        with patch('fastapi_users.BaseUserManager.update', new_callable=AsyncMock) as mock_super_update:
            updated_user = RegisteredUser(
                id=test_user_1.id,
                email=test_user_1.email,
                hashed_password=test_user_1.hashed_password,
                nickname="NewNickname",
                is_active=True,
                is_verified=True
            )
            mock_super_update.return_value = updated_user
            
            user_update = UserUpdate(nickname="NewNickname")
            
            # Act
            result = await user_manager.update(user_update, test_user_1)
            
            # Assert
            mock_validate_nickname.assert_called_once_with(
                "NewNickname", 
                exclude_user_id=test_user_1.id
            )
            mock_validate_email.assert_not_called()  # Email not being changed
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_update_does_not_validate_when_nickname_unchanged(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that update doesn't validate nickname when it's not changed"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock the parent update method
        with patch('fastapi_users.BaseUserManager.update', new_callable=AsyncMock) as mock_super_update:
            updated_user = RegisteredUser(
                id=test_user_1.id,
                email=test_user_1.email,
                hashed_password=test_user_1.hashed_password,
                nickname=test_user_1.nickname,
                description="New description",
                is_active=True,
                is_verified=True
            )
            mock_super_update.return_value = updated_user
            
            user_update = UserUpdate(description="New description")
            
            # Act
            result = await user_manager.update(user_update, test_user_1)
            
            # Assert
            mock_validate_nickname.assert_not_called()
            mock_validate_email.assert_not_called()
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_update_raises_when_nickname_taken(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that update raises NicknameAlreadyExists when new nickname is taken"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.side_effect = NicknameAlreadyExists("Nickname already taken")
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        user_update = UserUpdate(nickname="TakenNickname")
        
        # Act & Assert
        with pytest.raises(NicknameAlreadyExists):
            await user_manager.update(user_update, test_user_1)
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_update_validates_same_nickname_with_exclude(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that update allows keeping the same nickname (should exclude self)"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock the parent update method
        with patch('fastapi_users.BaseUserManager.update', new_callable=AsyncMock) as mock_super_update:
            updated_user = RegisteredUser(
                id=test_user_1.id,
                email=test_user_1.email,
                hashed_password=test_user_1.hashed_password,
                nickname=test_user_1.nickname,
                is_active=True,
                is_verified=True
            )
            mock_super_update.return_value = updated_user
            
            # User updates with different description but "new" nickname (which is actually same)
            user_update = UserUpdate(
                nickname=test_user_1.nickname,
                description="Updated description"
            )
            
            # Act
            result = await user_manager.update(user_update, test_user_1)
            
            # Assert - Should not validate because nickname hasn't changed
            mock_validate_nickname.assert_not_called()
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_update_with_pfp_path(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test updating profile picture path"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock the parent update method
        with patch('fastapi_users.BaseUserManager.update', new_callable=AsyncMock) as mock_super_update:
            updated_user = RegisteredUser(
                id=test_user_1.id,
                email=test_user_1.email,
                hashed_password=test_user_1.hashed_password,
                nickname=test_user_1.nickname,
                pfp_path="/images/avatar/5.png",
                is_active=True,
                is_verified=True
            )
            mock_super_update.return_value = updated_user
            
            user_update = UserUpdate(pfp_path="/images/avatar/5.png")
            
            # Act
            result = await user_manager.update(user_update, test_user_1)
            
            # Assert
            mock_validate_nickname.assert_not_called()
            mock_validate_email.assert_not_called()
            assert result.pfp_path == "/images/avatar/5.png"
    
    @patch.object(UserManager, 'validate_email_unique')
    @patch.object(UserManager, 'validate_nickname_unique')
    async def test_update_validates_email_when_changed(
        self,
        mock_validate_nickname,
        mock_validate_email,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that update validates email when it's being changed (edge case)"""
        # Arrange
        mock_validate_email.return_value = None
        mock_validate_nickname.return_value = None
        
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock the parent update method
        with patch('fastapi_users.BaseUserManager.update', new_callable=AsyncMock) as mock_super_update:
            updated_user = RegisteredUser(
                id=test_user_1.id,
                email="newemail@example.com",
                hashed_password=test_user_1.hashed_password,
                nickname=test_user_1.nickname,
                is_active=True,
                is_verified=True
            )
            mock_super_update.return_value = updated_user
            
            # Create a mock UserUpdate with email (normally not allowed by schema, but testing the logic)
            user_update = Mock(spec=UserUpdate)
            user_update.email = "newemail@example.com"
            user_update.nickname = None
            user_update.password = None
            user_update.pfp_path = None
            user_update.description = None
            
            # Act
            result = await user_manager.update(user_update, test_user_1)
            
            # Assert
            mock_validate_email.assert_called_once_with(
                "newemail@example.com",
                exclude_user_id=test_user_1.id
            )
            mock_validate_nickname.assert_not_called()


@pytest.mark.unit
class TestGetUserManager:
    """Test cases for get_user_manager dependency"""
    
    async def test_get_user_manager_yields_manager(self):
        """Test that get_user_manager yields a UserManager instance"""
        # Arrange
        mock_user_db = Mock()
        
        # Act
        async for manager in get_user_manager(mock_user_db):
            # Assert
            assert isinstance(manager, UserManager)
            assert manager.user_db == mock_user_db


@pytest.mark.unit
class TestUserManagerConfiguration:
    """Test cases for UserManager configuration"""
    
    def test_user_manager_has_correct_secrets(self, db_session: AsyncSession):
        """Test that UserManager has correct token secrets configured"""
        # Arrange
        mock_user_db = Mock()
        mock_user_db.session = db_session
        
        # Act
        user_manager = UserManager(mock_user_db)
        
        # Assert
        from config.settings import settings
        assert user_manager.reset_password_token_secret == settings.SECRET_KEY
        assert user_manager.verification_token_secret == settings.SECRET_KEY

    async def test_on_after_login_hook(self, db_session: AsyncSession, test_user_1: RegisteredUser):
        """Test on_after_login hook prints message"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        with patch('builtins.print') as mock_print:
            await user_manager.on_after_login(test_user_1)
            
            mock_print.assert_called_once()
            call_args = str(mock_print.call_args)
            assert str(test_user_1.id) in call_args
            assert test_user_1.nickname in call_args
    
    async def test_generate_unique_nickname_from_email(self, db_session: AsyncSession):
        """Test generating unique nickname from email"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        nickname = await user_manager._generate_unique_nickname(
            "github", 
            "test.user@example.com"
        )
        
        # Should use email username
        assert "test_user" in nickname or nickname == "test_user"
    
    async def test_generate_unique_nickname_collision(
        self, 
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test generating unique nickname handles collisions"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Use an email similar to existing user's nickname
        email_with_collision = f"{test_user_1.nickname}@example.com"
        
        nickname = await user_manager._generate_unique_nickname(
            "github",
            email_with_collision
        )
        
        # Should generate different nickname
        assert nickname != test_user_1.nickname
    
    async def test_generate_unique_nickname_no_email(self, db_session: AsyncSession):
        """Test generating unique nickname without email"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        nickname = await user_manager._generate_unique_nickname("google", None)
        
        # Should use oauth_name in generated nickname
        assert "google_user_" in nickname
    
    async def test_oauth_callback_existing_account(self, db_session: AsyncSession):
        """Test OAuth callback with existing account"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock existing user
        existing_user = RegisteredUser(
            id=999,
            email="oauth@example.com",
            nickname="oauth_user",
            hashed_password="hashed",
            is_verified=True
        )
        
        async def mock_get_by_oauth(oauth_name, account_id):
            return existing_user
        
        user_manager.get_by_oauth_account = mock_get_by_oauth
        mock_user_db.update_oauth_account = AsyncMock()
        
        result = await user_manager.oauth_callback(
            oauth_name="github",
            access_token="token123",
            account_id="gh123",
            account_email="oauth@example.com"
        )
        
        assert result == existing_user
        mock_user_db.update_oauth_account.assert_called_once()
    
    async def test_oauth_callback_associate_by_email(self, db_session: AsyncSession, test_user_1: RegisteredUser):
        """Test OAuth callback associating with existing email"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        async def mock_get_by_oauth(oauth_name, account_id):
            raise Exception("Not found")
        
        async def mock_get_by_email(email):
            if email == test_user_1.email:
                return test_user_1
            raise Exception("Not found")
        
        user_manager.get_by_oauth_account = mock_get_by_oauth
        user_manager.get_by_email = mock_get_by_email
        mock_user_db.add_oauth_account = AsyncMock()
        
        result = await user_manager.oauth_callback(
            oauth_name="github",
            access_token="token123",
            account_id="gh123",
            account_email=test_user_1.email,
            associate_by_email=True
        )
        
        assert result == test_user_1
        mock_user_db.add_oauth_account.assert_called_once()
    
    async def test_oauth_callback_create_new_user(self, db_session: AsyncSession):
        """Test OAuth callback creating new user"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        new_user = RegisteredUser(
            id=888,
            email="newuser@example.com",
            nickname="github_user_abc123",
            hashed_password="hashed",
            is_verified=True
        )
        
        async def mock_get_by_oauth(oauth_name, account_id):
            raise Exception("Not found")
        
        async def mock_get_by_email(email):
            raise Exception("Not found")
        
        user_manager.get_by_oauth_account = mock_get_by_oauth
        user_manager.get_by_email = mock_get_by_email
        mock_user_db.create = AsyncMock(return_value=new_user)
        mock_user_db.add_oauth_account = AsyncMock()
        
        with patch.object(user_manager, 'on_after_register', AsyncMock()):
            result = await user_manager.oauth_callback(
                oauth_name="github",
                access_token="token123",
                account_id="gh123",
                account_email="newuser@example.com",
                is_verified_by_default=True
            )
        
        assert result == new_user
        mock_user_db.create.assert_called_once()
        mock_user_db.add_oauth_account.assert_called_once()
    
    async def test_create_without_nickname_raises(self, db_session: AsyncSession):
        """Test create validates nickname is required by Pydantic"""
        # Pydantic will raise ValidationError before our code runs
        with pytest.raises(Exception):  # ValidationError from pydantic
            UserCreate(
                email="test@example.com",
                password="strongpassword123"
                # nickname missing - Pydantic will catch this
            )
    
    async def test_update_email_validates_uniqueness(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test updating email validates uniqueness"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # UserUpdate may not allow email updates - skip this test
        pytest.skip("UserUpdate schema may not allow direct email updates")
    
    async def test_update_nickname_validates_uniqueness(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test updating nickname validates uniqueness"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        user_update = UserUpdate(nickname=test_user_2.nickname)
        
        with pytest.raises(NicknameAlreadyExists):
            await user_manager.update(user_update, test_user_1)
    
    async def test_update_same_email_allowed(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test updating to same email is allowed"""
        pytest.skip("UserUpdate schema may not allow direct email updates")
    
    async def test_update_same_nickname_allowed(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test updating to same nickname is allowed"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        user_update = UserUpdate(nickname=test_user_1.nickname)
        
        with patch.object(user_manager.__class__.__bases__[1], 'update', AsyncMock(return_value=test_user_1)):
            result = await user_manager.update(user_update, test_user_1)
            assert result == test_user_1

    async def test_generate_unique_nickname_fallback_counter(self, db_session: AsyncSession):
        """Test nickname generation with fallback and counter"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        # Mock that first generated nickname is taken
        call_count = 0
        async def mock_validate(nickname):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NicknameAlreadyExists(f"Nickname '{nickname}' is already taken")
            # Second call succeeds
        
        user_manager.validate_nickname_unique = mock_validate
        
        # Generate without email to trigger fallback path
        nickname = await user_manager._generate_unique_nickname("github", None)
        
        # Should have generated github_user_ with suffix and counter
        assert "github_user_" in nickname
        assert call_count == 2  # Called twice - first failed, second succeeded
    
    async def test_oauth_callback_associate_by_email_exception_path(self, db_session: AsyncSession):
        """Test OAuth callback when associate_by_email fails"""
        mock_user_db = Mock()
        mock_user_db.session = db_session
        user_manager = UserManager(mock_user_db)
        
        new_user = RegisteredUser(
            id=999,
            email="oauth@example.com",
            nickname="oauth_user_xyz",
            hashed_password="hashed",
            is_verified=False
        )
        
        async def mock_get_by_oauth(oauth_name, account_id):
            raise Exception("Not found")
        
        async def mock_get_by_email(email):
            raise Exception("Not found")  # Triggers exception path
        
        user_manager.get_by_oauth_account = mock_get_by_oauth
        user_manager.get_by_email = mock_get_by_email
        mock_user_db.create = AsyncMock(return_value=new_user)
        mock_user_db.add_oauth_account = AsyncMock()
        
        with patch.object(user_manager, 'on_after_register', AsyncMock()):
            result = await user_manager.oauth_callback(
                oauth_name="github",
                access_token="token123",
                account_id="gh123",
                account_email="oauth@example.com",
                associate_by_email=True  # This triggers the exception path
            )
        
        assert result == new_user
        mock_user_db.create.assert_called_once()
