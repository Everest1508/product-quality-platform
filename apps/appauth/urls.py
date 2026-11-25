from django.urls import path

from apps.appauth import views

urlpatterns = [
    path("register", views.RegisterView.as_view()),
    path("login", views.LoginView.as_view()),
    path("google", views.GoogleView.as_view()),
    path("apple", views.AppleView.as_view()),
    path("change-password", views.ChangePasswordView.as_view()),
    path("logout-all", views.LogoutAllView.as_view()),
    path("refresh", views.RefreshView.as_view()),
    path("logout", views.LogoutView.as_view()),
    path("forgot-password", views.ForgotPasswordView.as_view()),
    path("reset-password", views.ResetPasswordView.as_view()),
    path("verify-email", views.VerifyEmailView.as_view()),
    path("verify-email-otp", views.VerifyEmailOtpView.as_view()),
    path("resend-verification", views.ResendVerificationView.as_view()),
    path("verify-reset-otp", views.VerifyResetOtpView.as_view()),
    path("me", views.MeView.as_view()),
    path("cloud/consent", views.CloudConsentView.as_view()),
    path("cloud/cards", views.CloudCardsView.as_view()),
    path("cloud/cards/<uuid:client_id>", views.CloudCardView.as_view()),
    path("cloud/data", views.CloudDataView.as_view()),
]
