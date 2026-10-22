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
from .models import SiteContent
from .serializers import (
    SiteContentPublishSerializer,
    SiteContentRollbackSerializer,
    SiteContentVersionSerializer,
)
from .services import (
    get_published_content,
    publish_content,
    save_draft,
    rollback_content,
    get_case_studies,
    get_case_study_by_slug,
)
from .selectors import (
    list_all_published,
    list_versions_for_key,
    get_content_keys,
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
    List filterable case studies with verified proof metrics.
    Now reads from DB (SiteContent) with fallback to default seed data.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        sector = request.query_params.get('sector', 'all')
        studies = get_case_studies(sector)
        return Response({'data': studies})


class CaseStudyDetailView(APIView):
    """
    GET /api/v1/content/case-studies/<slug>/
    Retrieve detail for a single case study.
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
