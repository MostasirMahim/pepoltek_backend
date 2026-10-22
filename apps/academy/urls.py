from django.urls import path
from .views import AcademyCoursesListView, AcademyEnrollView

urlpatterns = [
    path('courses/', AcademyCoursesListView.as_view(), name='academy-courses-list'),
    path('courses/<uuid:id>/enroll/', AcademyEnrollView.as_view(), name='academy-course-enroll'),
]
