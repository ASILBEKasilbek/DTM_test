from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('telegram-auth/<str:telegram_id>/', views.telegram_auth, name='telegram_auth'),
    path('tests/<slug:subject_slug>/', views.start_test, name='start_test'),
    path('test-session/<int:session_id>/', views.test_session, name='test_session'),
    path('save-answer/<int:session_id>/<int:question_id>/', views.save_answer, name='save_answer'),
    path('results/<int:session_id>/', views.view_results, name='view_results'),
]