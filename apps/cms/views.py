"""
cms/views.py
Public + Admin CMS REST API views.

Public endpoints (AllowAny):
  GET  /api/v1/content/site/<key>/          -- read published block for any key
  GET  /api/v1/content/case-studies/        -- list case studies (with sector filter)
  GET  /api/v1/content/case-studies/<slug>/ -- single case study

Admin endpoints (IsAdminOrSuperAdmin):
  GET  /api/v1/content/admin/blocks/              -- list all publishable keys + status
  GET  /api/v1/content/admin/blocks/<key>/        -- get published + draft data for a key
  POST /api/v1/content/admin/blocks/<key>/publish/ -- publish a new version
  POST /api/v1/content/admin/blocks/<key>/draft/   -- save draft (does not publish)
  POST /api/v1/content/admin/blocks/<key>/rollback/ -- rollback to historical version
  GET  /api/v1/content/admin/blocks/<key>/history/ -- version history for a key
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import SiteContent, CaseStudy
from .serializers import (
    SiteContentPublishSerializer,
    SiteContentRollbackSerializer,
    SiteContentVersionSerializer,
    CaseStudyModelListSerializer,
    CaseStudyModelDetailSerializer,
    CaseStudyWriteSerializer,
)
from .services import (
    get_published_content,
    publish_content,
    save_draft,
    rollback_content,
    get_case_studies,
    get_case_study_by_slug,
    create_case_study,
    update_case_study,
    delete_case_study,
    seed_default_case_studies_if_empty,
)
from .selectors import (
    list_all_published,
    list_versions_for_key,
    get_content_keys,
    list_case_studies,
    get_case_study_by_id,
    get_case_studies_kpis,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class PublicSiteContentView(APIView):
    """
    GET /api/v1/content/site/<key>/
    Returns the currently published data for any content key.
    Used by Next.js pages with ISR to hydrate public content.
    """
    permission_classes = [AllowAny]

    def get(self, request, key):
        # Validate the key
        valid_keys = [k for k, _ in SiteContent.Key.choices]
        if key not in valid_keys:
            return Response(
                {'error': f'Unknown content key: {key}'},
                status=status.HTTP_404_NOT_FOUND
            )

        content = get_published_content(key)
        if not content:
            return Response(
                {'data': None, 'message': 'No published content yet for this block.'},
                status=status.HTTP_200_OK,
            )
        return Response({'data': content})


class CaseStudiesListView(APIView):
    """
    GET /api/v1/content/case-studies/
    List published case studies with verified proof metrics.
    Supports filtering by sector, category, featured flag, and search keywords.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        sector = request.query_params.get('sector', 'all')
        category = request.query_params.get('category', 'all')
        featured_param = request.query_params.get('featured')
        featured = True if featured_param in ['true', '1'] else None
        search = request.query_params.get('search')

        if not CaseStudy.objects.exists():
            seed_default_case_studies_if_empty()

        qs = list_case_studies(
            sector=sector,
            category=category,
            status=CaseStudy.Status.PUBLISHED,
            is_featured=featured,
            search=search,
        )
        serializer = CaseStudyModelListSerializer(qs, many=True)
        return Response({'data': serializer.data})


class CaseStudyDetailView(APIView):
    """
    GET /api/v1/content/case-studies/<slug>/
    Retrieve detail for a single case study by slug.
    """
    permission_classes = [AllowAny]

    def get(self, request, slug):
        study = get_case_study_by_slug(slug)
        if not study:
            return Response(
                {'error': 'Case study not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response({'data': study})


# ---------------------------------------------------------------------------
# Admin Content Management API
# ---------------------------------------------------------------------------

class AdminContentBlocksOverviewView(APIView):
    """
    GET /api/v1/content/admin/blocks/
    Returns all manageable content keys with their current published status.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        keys = get_content_keys()
        published_map = {b.key: b for b in list_all_published()}

        result = []
        for item in keys:
            key = item['key']
            block = published_map.get(key)
            result.append({
                'key': key,
                'label': item['label'],
                'has_published': block is not None,
                'published_version': block.version if block else None,
                'last_updated': block.updated_at.isoformat() if block else None,
                'last_author': (
                    (block.author.full_name or block.author.email) if block and block.author else None
                ),
            })
        return Response({'data': result})


class AdminContentBlockDetailView(APIView):
    """
    GET /api/v1/content/admin/blocks/<key>/
    Returns published data and latest draft (if different) for a key.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request, key):
        valid_keys = [k for k, _ in SiteContent.Key.choices]
        if key not in valid_keys:
            return Response(
                {'error': f'Unknown content key: {key}'},
                status=status.HTTP_404_NOT_FOUND
            )

        published = get_published_content(key)
        # Latest version regardless of publish state
        latest_block = (
            SiteContent.objects.filter(key=key).order_by('-version').first()
        )
        latest = SiteContentVersionSerializer(latest_block).data if latest_block else None

        return Response({
            'data': {
                'published': published,
                'latest': latest,
            }
        })


class AdminContentPublishView(APIView):
    """
    POST /api/v1/content/admin/blocks/<key>/publish/
    Create a new version and immediately publish it.
    Body: { data: {...}, notes: "optional edit note" }
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, key):
        valid_keys = [k for k, _ in SiteContent.Key.choices]
        if key not in valid_keys:
            return Response(
                {'error': f'Unknown content key: {key}'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SiteContentPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        block = publish_content(
            key=key,
            data=payload['data'],
            author=request.user,
            notes=payload.get('notes', ''),
        )

        return Response({
            'data': {
                'version': block.version,
                'key': block.key,
                'message': f'Content published as v{block.version}.',
            }
        }, status=status.HTTP_201_CREATED)


class AdminContentDraftView(APIView):
    """
    POST /api/v1/content/admin/blocks/<key>/draft/
    Save a draft version without publishing (previously published stays live).
    Body: { data: {...}, notes: "optional note" }
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, key):
        valid_keys = [k for k, _ in SiteContent.Key.choices]
        if key not in valid_keys:
            return Response(
                {'error': f'Unknown content key: {key}'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SiteContentPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        block = save_draft(
            key=key,
            data=payload['data'],
            author=request.user,
            notes=payload.get('notes', ''),
        )

        return Response({
            'data': {
                'version': block.version,
                'key': block.key,
                'message': f'Draft saved as v{block.version}. Not published yet.',
            }
        }, status=status.HTTP_201_CREATED)


class AdminContentRollbackView(APIView):
    """
    POST /api/v1/content/admin/blocks/<key>/rollback/
    Re-publish a historical version (creates new version with old data).
    Body: { target_version: 3 }
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, key):
        valid_keys = [k for k, _ in SiteContent.Key.choices]
        if key not in valid_keys:
            return Response(
                {'error': f'Unknown content key: {key}'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SiteContentRollbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_version = serializer.validated_data['target_version']

        try:
            block = rollback_content(key=key, target_version=target_version, author=request.user)
        except SiteContent.DoesNotExist:
            return Response(
                {'error': f'Version {target_version} not found for key {key}.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            'data': {
                'version': block.version,
                'key': block.key,
                'message': f'Rolled back to v{target_version}. Now published as v{block.version}.',
            }
        })


class AdminContentHistoryView(APIView):
    """
    GET /api/v1/content/admin/blocks/<key>/history/
    Returns the full version history for a content key.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request, key):
        valid_keys = [k for k, _ in SiteContent.Key.choices]
        if key not in valid_keys:
            return Response(
                {'error': f'Unknown content key: {key}'},
                status=status.HTTP_404_NOT_FOUND
            )

        blocks = list_versions_for_key(key, limit=50)
        serializer = SiteContentVersionSerializer(blocks, many=True)
        return Response({'data': serializer.data})


# ---------------------------------------------------------------------------
# Admin Case Study Management API
# ---------------------------------------------------------------------------

class AdminCaseStudiesListView(APIView):
    """
    GET /api/v1/content/admin/case-studies/
    List all case studies (drafts, published, archived) with KPIs and filtering.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        if not CaseStudy.objects.exists():
            seed_default_case_studies_if_empty(author=request.user)

        sector = request.query_params.get('sector')
        category = request.query_params.get('category')
        study_status = request.query_params.get('status')
        featured_param = request.query_params.get('featured')
        featured = True if featured_param in ['true', '1'] else (False if featured_param in ['false', '0'] else None)
        search = request.query_params.get('search')

        qs = list_case_studies(
            sector=sector,
            category=category,
            status=study_status,
            is_featured=featured,
            search=search,
        )
        serializer = CaseStudyModelListSerializer(qs, many=True)
        kpis = get_case_studies_kpis()

        return Response({
            'data': serializer.data,
            'kpis': kpis,
        })


class AdminCaseStudyCreateView(APIView):
    """
    POST /api/v1/content/admin/case-studies/
    Create a new Case Study in the database.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request):
        serializer = CaseStudyWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        case_study = create_case_study(
            data=serializer.validated_data,
            author=request.user,
            request=request,
        )
        detail_serializer = CaseStudyModelDetailSerializer(case_study)
        return Response(
            {
                'data': detail_serializer.data,
                'message': 'Technical case study created successfully.',
            },
            status=status.HTTP_201_CREATED,
        )


class AdminCaseStudyDetailView(APIView):
    """
    GET, PUT/PATCH, DELETE /api/v1/content/admin/case-studies/<uuid:id>/
    Manage single case study: view full dossier, update fields, or soft-delete.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request, id):
        case_study = get_case_study_by_id(id)
        if not case_study:
            return Response({'error': 'Case study not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CaseStudyModelDetailSerializer(case_study)
        return Response({'data': serializer.data})

    def put(self, request, id):
        return self.patch(request, id)

    def patch(self, request, id):
        case_study = get_case_study_by_id(id)
        if not case_study:
            return Response({'error': 'Case study not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CaseStudyWriteSerializer(case_study, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        updated_case_study = update_case_study(
            case_study=case_study,
            data=serializer.validated_data,
            author=request.user,
            request=request,
        )
        detail_serializer = CaseStudyModelDetailSerializer(updated_case_study)
        return Response({
            'data': detail_serializer.data,
            'message': 'Technical case study updated successfully.',
        })

    def delete(self, request, id):
        case_study = get_case_study_by_id(id)
        if not case_study:
            return Response({'error': 'Case study not found.'}, status=status.HTTP_404_NOT_FOUND)

        delete_case_study(case_study, author=request.user, request=request)
        return Response({
            'message': f'Case study "{case_study.title}" removed successfully.',
        })

