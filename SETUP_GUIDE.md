# PayBack Setup Guide - Email Configuration Fix

## 📧 Email Configuration Fix

The current system is configured to use Resend's test domain (`onboarding@resend.dev`), which only delivers emails to addresses registered with your Resend account. To fix this, you have several options:

### Option 1: Use SMTP with Gmail (Recommended for Testing)

1. **Enable 2FA on your Gmail account** (if not already enabled)
2. **Generate an App Password:**
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a new app password for "Mail"
   - Copy the 16-character password

3. **Configure the backend .env file:**
   ```bash
   # In backend/.env file
   message_delivery_provider=smtp
   smtp_host=smtp.gmail.com
   smtp_port=587
   smtp_user=your-email@gmail.com
   smtp_password=your-16-char-app-password
   smtp_from_email=your-email@gmail.com
   ```

4. **Restart the backend server:**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Option 2: Configure Custom Resend Domain (Recommended for Production)

1. **Sign up for a custom domain in Resend**
2. **Configure the backend .env file:**
   ```bash
   message_delivery_provider=resend
   resend_api_key=your-resend-api-key
   resend_from_email=payments@yourcompany.com
   ```

### Option 3: Use Mock Provider (For Development Only)

For testing without actual email delivery:
```bash
message_delivery_provider=mock
```

## 🔧 Error Message Improvements

The system now includes human-readable error messages for common Razorpay error codes:

- `BAD_REQUEST_ERROR` → "Invalid payment details provided"
- `INSUFFICIENT_FUNDS` → "Insufficient funds in your account"
- `PAYMENT_FAILED` → "Payment processing failed"
- `GATEWAY_ERROR` → "Payment gateway error, please try again"
- `AUTHENTICATION_FAILED` → "Authentication failed"
- And more...

## 🧪 Testing the Complete Workflow

1. **Start the backend server** with your new email configuration
2. **Start the frontend server:**
   ```bash
   cd frontend
   npm run dev
   ```
3. **Open the dashboard** and click "Create Payment"
4. **Enter customer details** (use your own email for testing)
5. **Click "Create Payment Link"** and copy/open the generated link
6. **Intentionally fail the payment** (use expired card, insufficient funds, etc.)
7. **Check your email inbox** for the recovery email with new payment link
8. **Complete the payment** using the new link
9. **Verify dashboard updates** showing successful recovery

## 📊 Dashboard Metrics Explanation

The dashboard metrics are working correctly:

- **Lifetime Value: ₹0** - Only counts successful payments (you have only failed payments)
- **Recovery Rate: 0%** - Only counts successful recoveries (no recoveries completed yet)
- **Open Recoveries: 1** - One active recovery case (correct)
- **Last Payment: Today** - Recent failed payment (correct)

These metrics will update automatically when you have successful payments and recoveries.

## 🐛 Troubleshooting

### Email Not Received

1. **Check backend logs** for email sending errors
2. **Verify SMTP credentials** are correct
3. **Check spam folder** in your email
4. **Test with a different email address**

### Payment Link Not Working

1. **Verify Razorpay test keys** are configured
2. **Check webhook configuration** in Razorpay dashboard
3. **Test with different payment methods** (card, UPI, netbanking)

### Recovery Not Triggering

1. **Check webhook is receiving** payment failure events
2. **Verify recovery workflow** is running in backend logs
3. **Check customer data** is properly saved in database

## 🚀 Next Steps

1. Configure email delivery using one of the options above
2. Test the complete payment → failure → recovery workflow
3. Verify email delivery to your inbox
4. Test successful payment completion
5. Monitor dashboard metrics updating correctly

## 📞 Support

If you encounter issues:
- Check backend logs for detailed error messages
- Verify all environment variables are set correctly
- Ensure Razorpay test mode keys are properly configured
- Test email delivery with a simple test script if needed
