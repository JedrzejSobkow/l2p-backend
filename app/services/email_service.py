# app/services/email_service.py

import resend
from config.settings import settings
from typing import Optional


class EmailService:
    """Service for sending emails using Resend API"""
    
    def __init__(self):
        """Initialize Resend with API key"""
        resend.api_key = settings.RESEND_API_KEY
    
    async def send_verification_email(self, email: str, token: str, nickname: str) -> bool:
        """
        Send verification email with token
        
        Args:
            email: Recipient email address
            token: Verification token
            nickname: User's nickname
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background-color: #f9f9f9;
                        border-radius: 10px;
                        padding: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        color: #4F46E5;
                        margin-bottom: 30px;
                    }}
                    .content {{
                        background-color: white;
                        padding: 20px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background-color: #4F46E5;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                    }}
                    .button:hover {{
                        background-color: #4338CA;
                    }}
                    .footer {{
                        text-align: center;
                        font-size: 12px;
                        color: #666;
                        margin-top: 20px;
                    }}
                    .token {{
                        background-color: #f3f4f6;
                        padding: 10px;
                        border-radius: 5px;
                        font-family: monospace;
                        word-break: break-all;
                        margin: 15px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="header">🎓 Welcome to L2P!</h1>
                    <div class="content">
                        <p>Hi <strong>{nickname}</strong>,</p>
                        <p>Thank you for registering with L2P! To complete your registration and activate your account, please verify your email address.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{verification_url}" class="button">Verify Email Address</a>
                        </p>
                        <p>Or copy and paste this link into your browser:</p>
                        <div class="token">{verification_url}</div>
                        <p><strong>Note:</strong> This verification link will expire in 24 hours for security reasons.</p>
                    </div>
                    <div class="footer">
                        <p>If you didn't create an account with L2P, please ignore this email.</p>
                        <p>© {settings.APP_NAME}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Welcome to L2P!
            
            Hi {nickname},
            
            Thank you for registering with L2P! To complete your registration and activate your account, please verify your email address.
            
            Click the link below to verify your email:
            {verification_url}
            
            Note: This verification link will expire in 24 hours for security reasons.
            
            If you didn't create an account with L2P, please ignore this email.
            
            © {settings.APP_NAME}
            """
            
            params = {
                "from": settings.EMAIL_FROM,
                "to": [email],
                "subject": "Verify your L2P account",
                "html": html_content,
                "text": text_content,
            }
            
            email_response = resend.Emails.send(params)
            print(f"✅ Verification email sent to {email}. Email ID: {email_response.get('id', 'unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send verification email to {email}: {str(e)}")
            return False
    
    async def send_password_reset_email(self, email: str, token: str, nickname: str) -> bool:
        """
        Send password reset email with token
        
        Args:
            email: Recipient email address
            token: Password reset token
            nickname: User's nickname
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background-color: #f9f9f9;
                        border-radius: 10px;
                        padding: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        color: #DC2626;
                        margin-bottom: 30px;
                    }}
                    .content {{
                        background-color: white;
                        padding: 20px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background-color: #DC2626;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                    }}
                    .button:hover {{
                        background-color: #B91C1C;
                    }}
                    .footer {{
                        text-align: center;
                        font-size: 12px;
                        color: #666;
                        margin-top: 20px;
                    }}
                    .token {{
                        background-color: #f3f4f6;
                        padding: 10px;
                        border-radius: 5px;
                        font-family: monospace;
                        word-break: break-all;
                        margin: 15px 0;
                    }}
                    .warning {{
                        background-color: #FEF3C7;
                        border-left: 4px solid #F59E0B;
                        padding: 12px;
                        margin: 15px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="header">🔑 Password Reset Request</h1>
                    <div class="content">
                        <p>Hi <strong>{nickname}</strong>,</p>
                        <p>We received a request to reset your password for your L2P account.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{reset_url}" class="button">Reset Password</a>
                        </p>
                        <p>Or copy and paste this link into your browser:</p>
                        <div class="token">{reset_url}</div>
                        <div class="warning">
                            <strong>⚠️ Security Notice:</strong> This password reset link will expire in 1 hour. If you didn't request a password reset, please ignore this email and your password will remain unchanged.
                        </div>
                    </div>
                    <div class="footer">
                        <p>If you didn't request a password reset, please ignore this email.</p>
                        <p>© {settings.APP_NAME}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Password Reset Request
            
            Hi {nickname},
            
            We received a request to reset your password for your L2P account.
            
            Click the link below to reset your password:
            {reset_url}
            
            ⚠️ Security Notice: This password reset link will expire in 1 hour. If you didn't request a password reset, please ignore this email and your password will remain unchanged.
            
            © {settings.APP_NAME}
            """
            
            params = {
                "from": settings.EMAIL_FROM,
                "to": [email],
                "subject": "Reset your L2P password",
                "html": html_content,
                "text": text_content,
            }
            
            email_response = resend.Emails.send(params)
            print(f"✅ Password reset email sent to {email}. Email ID: {email_response.get('id', 'unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send password reset email to {email}: {str(e)}")
            return False


# Singleton instance
email_service = EmailService()
