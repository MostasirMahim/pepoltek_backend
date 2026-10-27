from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AssessmentTemplateViewSet,
    ApplicationVettingViewSet,
    CredentialViewSet,
    ValidatorDashboardView,
    ValidatorGradeView,
    ValidatorVerifyCredentialView,
    ValidatorsListView,
)

router = DefaultRouter()
router.register('templates', AssessmentTemplateViewSet, basename='assessment-template')
router.register('vettings',  ApplicationVettingViewSet,  basename='application-vetting')
router.register('credentials', CredentialViewSet,         basename='credential')

urlpatterns = [
    path('validators/', ValidatorsListView.as_view(), name='vetting-validators-list'),
    path('validator/dashboard/', ValidatorDashboardView.as_view(), name='validator-dashboard'),
    path('validator/grade/', ValidatorGradeView.as_view(), name='validator-grade'),
    path('validator/verify-credential/', ValidatorVerifyCredentialView.as_view(), name='validator-verify-credential'),
] + router.urls

