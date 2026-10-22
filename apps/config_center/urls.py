from django.urls import path
from .views import (
    CalculatorConfigView,
    CalculatorEstimateView,
    TaxonomyConfigView,
    TaxonomyHistoryView,
)

urlpatterns = [
    path('calculator/', CalculatorConfigView.as_view(), name='config-calculator'),
    path('calculator/estimate/', CalculatorEstimateView.as_view(), name='config-calculator-estimate'),
    path('taxonomies/', TaxonomyConfigView.as_view(), name='config-taxonomies'),
    path('taxonomies/history/', TaxonomyHistoryView.as_view(), name='config-taxonomies-history'),
    path('taxonomies/rollback/', TaxonomyHistoryView.as_view(), name='config-taxonomies-rollback'),
]

