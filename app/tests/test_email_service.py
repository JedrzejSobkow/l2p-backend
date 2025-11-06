"""
Unit tests for EmailService

Tests cover:
- Sending verification emails
- Sending password reset emails
- Handling API errors
- Validating email content
"""
import pytest
from unittest.mock import patch, MagicMock
from services.email_service import EmailService
from config.settings import settings


@pytest.mark.unit
class TestSendVerificationEmail:
    """Test cases for send_verification_email method"""
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_verification_email_success(self, mock_resend_send):
        """Test successfully sending a verification email"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123-456'}
        email_service = EmailService()
        test_email = "test@example.com"
        test_token = "verification-token-123"
        test_nickname = "TestUser"
        
        # Act
        result = await email_service.send_verification_email(
            email=test_email,
            token=test_token,
            nickname=test_nickname
        )
        
        # Assert
        assert result is True
        mock_resend_send.assert_called_once()
        
        # Verify the email parameters
        call_args = mock_resend_send.call_args[0][0]
        assert call_args['from'] == settings.EMAIL_FROM
        assert call_args['to'] == [test_email]
        assert call_args['subject'] == "Verify your L2P account"
        assert test_nickname in call_args['html']
        assert test_token in call_args['html']
        assert test_nickname in call_args['text']
        assert test_token in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_verification_email_contains_correct_url(self, mock_resend_send):
        """Test that verification email contains correct verification URL"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123-456'}
        email_service = EmailService()
        test_email = "test@example.com"
        test_token = "verification-token-123"
        test_nickname = "TestUser"
        expected_url = f"{settings.FRONTEND_URL}/verify-email?token={test_token}"
        
        # Act
        result = await email_service.send_verification_email(
            email=test_email,
            token=test_token,
            nickname=test_nickname
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert expected_url in call_args['html']
        assert expected_url in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_verification_email_contains_expiry_notice(self, mock_resend_send):
        """Test that verification email contains expiry notice"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123-456'}
        email_service = EmailService()
        
        # Act
        result = await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert "24 hours" in call_args['html']
        assert "24 hours" in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_verification_email_api_failure(self, mock_resend_send):
        """Test handling API failure when sending verification email"""
        # Arrange
        mock_resend_send.side_effect = Exception("API Error")
        email_service = EmailService()
        
        # Act
        result = await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        assert result is False
        mock_resend_send.assert_called_once()
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_verification_email_with_special_characters(self, mock_resend_send):
        """Test sending verification email with special characters in nickname"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123-456'}
        email_service = EmailService()
        test_nickname = "Test User <script>"
        
        # Act
        result = await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname=test_nickname
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert test_nickname in call_args['html']
        assert test_nickname in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_verification_email_contains_app_name(self, mock_resend_send):
        """Test that verification email contains app name"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123-456'}
        email_service = EmailService()
        
        # Act
        result = await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert settings.APP_NAME in call_args['html']
        assert settings.APP_NAME in call_args['text']


@pytest.mark.unit
class TestSendPasswordResetEmail:
    """Test cases for send_password_reset_email method"""
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_success(self, mock_resend_send):
        """Test successfully sending a password reset email"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-789-012'}
        email_service = EmailService()
        test_email = "test@example.com"
        test_token = "reset-token-456"
        test_nickname = "TestUser"
        
        # Act
        result = await email_service.send_password_reset_email(
            email=test_email,
            token=test_token,
            nickname=test_nickname
        )
        
        # Assert
        assert result is True
        mock_resend_send.assert_called_once()
        
        # Verify the email parameters
        call_args = mock_resend_send.call_args[0][0]
        assert call_args['from'] == settings.EMAIL_FROM
        assert call_args['to'] == [test_email]
        assert call_args['subject'] == "Reset your L2P password"
        assert test_nickname in call_args['html']
        assert test_token in call_args['html']
        assert test_nickname in call_args['text']
        assert test_token in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_contains_correct_url(self, mock_resend_send):
        """Test that password reset email contains correct reset URL"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-789-012'}
        email_service = EmailService()
        test_email = "test@example.com"
        test_token = "reset-token-456"
        test_nickname = "TestUser"
        expected_url = f"{settings.FRONTEND_URL}/reset-password?token={test_token}"
        
        # Act
        result = await email_service.send_password_reset_email(
            email=test_email,
            token=test_token,
            nickname=test_nickname
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert expected_url in call_args['html']
        assert expected_url in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_contains_expiry_notice(self, mock_resend_send):
        """Test that password reset email contains expiry notice"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-789-012'}
        email_service = EmailService()
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert "1 hour" in call_args['html']
        assert "1 hour" in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_contains_security_notice(self, mock_resend_send):
        """Test that password reset email contains security warning"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-789-012'}
        email_service = EmailService()
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert "Security Notice" in call_args['html'] or "⚠️" in call_args['html']
        assert "⚠️" in call_args['text'] or "Security Notice" in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_api_failure(self, mock_resend_send):
        """Test handling API failure when sending password reset email"""
        # Arrange
        mock_resend_send.side_effect = Exception("API Error")
        email_service = EmailService()
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        assert result is False
        mock_resend_send.assert_called_once()
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_with_long_nickname(self, mock_resend_send):
        """Test sending password reset email with long nickname"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-789-012'}
        email_service = EmailService()
        test_nickname = "VeryLongNicknameThatExceedsNormalLength" * 3
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname=test_nickname
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert test_nickname in call_args['html']
        assert test_nickname in call_args['text']
    
    @patch('services.email_service.resend.Emails.send')
    async def test_send_password_reset_email_contains_app_name(self, mock_resend_send):
        """Test that password reset email contains app name"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-789-012'}
        email_service = EmailService()
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert settings.APP_NAME in call_args['html']
        assert settings.APP_NAME in call_args['text']


@pytest.mark.unit
class TestEmailServiceInitialization:
    """Test cases for EmailService initialization"""
    
    @patch('services.email_service.resend')
    def test_email_service_initialization_sets_api_key(self, mock_resend):
        """Test that EmailService initialization sets the API key"""
        # Act
        email_service = EmailService()
        
        # Assert
        assert mock_resend.api_key == settings.RESEND_API_KEY
    
    def test_email_service_singleton_instance(self):
        """Test that email_service singleton instance is properly initialized"""
        # Import the singleton instance
        from services.email_service import email_service
        
        # Assert
        assert isinstance(email_service, EmailService)


@pytest.mark.unit
class TestEmailContentValidation:
    """Test cases for email content validation"""
    
    @patch('services.email_service.resend.Emails.send')
    async def test_verification_email_has_both_html_and_text(self, mock_resend_send):
        """Test that verification email includes both HTML and plain text versions"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123'}
        email_service = EmailService()
        
        # Act
        await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        call_args = mock_resend_send.call_args[0][0]
        assert 'html' in call_args
        assert 'text' in call_args
        assert len(call_args['html']) > 0
        assert len(call_args['text']) > 0
    
    @patch('services.email_service.resend.Emails.send')
    async def test_password_reset_email_has_both_html_and_text(self, mock_resend_send):
        """Test that password reset email includes both HTML and plain text versions"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123'}
        email_service = EmailService()
        
        # Act
        await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        call_args = mock_resend_send.call_args[0][0]
        assert 'html' in call_args
        assert 'text' in call_args
        assert len(call_args['html']) > 0
        assert len(call_args['text']) > 0
    
    @patch('services.email_service.resend.Emails.send')
    async def test_verification_email_html_contains_styling(self, mock_resend_send):
        """Test that verification email HTML contains CSS styling"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123'}
        email_service = EmailService()
        
        # Act
        await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        call_args = mock_resend_send.call_args[0][0]
        html_content = call_args['html']
        assert '<style>' in html_content
        assert '</style>' in html_content
        assert 'background-color' in html_content
    
    @patch('services.email_service.resend.Emails.send')
    async def test_password_reset_email_html_contains_styling(self, mock_resend_send):
        """Test that password reset email HTML contains CSS styling"""
        # Arrange
        mock_resend_send.return_value = {'id': 'email-123'}
        email_service = EmailService()
        
        # Act
        await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        call_args = mock_resend_send.call_args[0][0]
        html_content = call_args['html']
        assert '<style>' in html_content
        assert '</style>' in html_content
        assert 'background-color' in html_content


@pytest.mark.unit
class TestEmailErrorHandling:
    """Test cases for error handling in email service"""
    
    @patch('services.email_service.resend.Emails.send')
    async def test_verification_email_handles_network_error(self, mock_resend_send):
        """Test handling network errors when sending verification email"""
        # Arrange
        mock_resend_send.side_effect = ConnectionError("Network error")
        email_service = EmailService()
        
        # Act
        result = await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        assert result is False
    
    @patch('services.email_service.resend.Emails.send')
    async def test_password_reset_email_handles_timeout_error(self, mock_resend_send):
        """Test handling timeout errors when sending password reset email"""
        # Arrange
        mock_resend_send.side_effect = TimeoutError("Request timeout")
        email_service = EmailService()
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        assert result is False
    
    @patch('services.email_service.resend.Emails.send')
    async def test_verification_email_handles_generic_exception(self, mock_resend_send):
        """Test handling generic exceptions when sending verification email"""
        # Arrange
        mock_resend_send.side_effect = Exception("Unknown error")
        email_service = EmailService()
        
        # Act
        result = await email_service.send_verification_email(
            email="test@example.com",
            token="token-123",
            nickname="TestUser"
        )
        
        # Assert
        assert result is False
    
    @patch('services.email_service.resend.Emails.send')
    async def test_password_reset_email_handles_generic_exception(self, mock_resend_send):
        """Test handling generic exceptions when sending password reset email"""
        # Arrange
        mock_resend_send.side_effect = Exception("Unknown error")
        email_service = EmailService()
        
        # Act
        result = await email_service.send_password_reset_email(
            email="test@example.com",
            token="token-456",
            nickname="TestUser"
        )
        
        # Assert
        assert result is False
