from django.urls import path
from . import views

urlpatterns = [
    path('system/readiness/', views.system_readiness, name='system_readiness'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('refresh/', views.refresh_token, name='refresh_token'),
    path('logout/', views.logout, name='logout'),
    path('verify-token/', views.verify_token, name='verify_token'),
    path('admin/2fa/setup/', views.admin_2fa_setup, name='admin_2fa_setup'),
    path('admin/2fa/enable/', views.admin_2fa_enable, name='admin_2fa_enable'),
    path('admin/2fa/disable/', views.admin_2fa_disable, name='admin_2fa_disable'),
    # Admin endpoints
    path('users/', views.user_list, name='user_list'),
    path('users/<uuid:user_id>/', views.user_detail, name='user_detail'),
]
