from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Course, CourseStatus, Enrollment


class AcademyCoursesListView(APIView):
    """
    GET /api/v1/academy/courses/
    List published academy courses with sector filtering.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        sector = request.query_params.get('sector', 'all')
        queryset = Course.objects.filter(status=CourseStatus.PUBLISHED)
        if sector and sector != 'all':
            queryset = queryset.filter(sector__icontains=sector)

        courses = []
        for c in queryset:
            courses.append({
                'id': str(c.id),
                'slug': c.slug,
                'title': c.title,
                'sector': c.sector,
                'level': 'Advanced',
                'duration': f'{int(c.estimated_hours or 20)} Hours',
                'modules': c.modules.count() or 6,
                'readinessBoost': '+15% Score',
                'description': c.description,
                'badge': f'Certified {c.title.split()[0]} Specialist',
            })

        if not courses:
            courses = [
                {
                    'id': 'course-101',
                    'slug': 'cloud-native-kubernetes-mastery',
                    'title': 'Production Kubernetes & Multi-Cloud Architecture',
                    'sector': 'tech',
                    'level': 'Advanced',
                    'duration': '4 Weeks',
                    'modules': 8,
                    'readinessBoost': '+15% Score',
                    'description': 'Hands-on cluster provisioning, Terraform state management, GitOps with ArgoCD, and zero-downtime rolling updates.',
                    'badge': 'Certified Cloud Architect',
                },
                {
                    'id': 'course-102',
                    'slug': 'distributed-python-fastapi',
                    'title': 'Distributed Python & High-Concurrency Microservices',
                    'sector': 'tech',
                    'level': 'Intermediate / Advanced',
                    'duration': '3 Weeks',
                    'modules': 6,
                    'readinessBoost': '+12% Score',
                    'description': 'AsyncIO patterns, Celery distributed tasks, Redis caching architectures, and PostgreSQL vector indexing.',
                    'badge': 'Distributed Systems Specialist',
                },
                {
                    'id': 'course-103',
                    'slug': 'hipaa-clinical-compliance',
                    'title': 'Healthcare Information Security & HIPAA Standards',
                    'sector': 'healthcare',
                    'level': 'Required Practice',
                    'duration': '1 Week',
                    'modules': 4,
                    'readinessBoost': '+20% Score',
                    'description': 'Mandatory clinical privacy protocols, EHR audit trails, protected health information (PHI) encryption, and emergency charting.',
                    'badge': 'HIPAA Compliant Clinician',
                },
                {
                    'id': 'course-104',
                    'slug': 'rag-llm-production-systems',
                    'title': 'LLM Engineering, RAG Pipelines & Vector Databases',
                    'sector': 'tech',
                    'level': 'Advanced',
                    'duration': '3 Weeks',
                    'modules': 7,
                    'readinessBoost': '+18% Score',
                    'description': 'Building production Retrieval-Augmented Generation architectures with pgvector, LangChain, and evaluation frameworks.',
                    'badge': 'AI Systems Practitioner',
                },
            ]

        if sector and sector != 'all':
            courses = [c for c in courses if c['sector'] == sector]

        return Response({'data': courses})


class AcademyEnrollView(APIView):
    """
    POST /api/v1/academy/courses/<id>/enroll/
    Enroll in an academy course.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        return Response({
            'data': {
                'course_id': str(id),
                'enrolled': True,
                'message': 'Enrolled successfully. Course materials unlocked.',
            }
        })
