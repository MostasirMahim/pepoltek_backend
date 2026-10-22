from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import ConfigVersion
from .serializers import CalculatorEstimateInputSerializer
from .selectors import get_active_taxonomies, get_taxonomy_history
from .services import (
    get_active_config,
    calculate_estimate,
    update_taxonomies,
    rollback_config,
)



class CalculatorConfigView(APIView):
    """
    GET /api/v1/config/calculator/ - Retrieve active hiring calculator parameters.
    PATCH /api/v1/config/calculator/ - Update hiring calculator parameters (Admin only).
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminOrSuperAdmin()]

    def get(self, request):
        config = get_active_config(ConfigVersion.Key.HIRING_CALCULATOR)
        return Response({'data': config})

    def patch(self, request):
        active_config = ConfigVersion.objects.filter(
            key=ConfigVersion.Key.HIRING_CALCULATOR,
            is_active=True
        ).first()

        new_data = dict(active_config.data if active_config else {})
        new_data.update(request.data)

        # Create new version
        new_version = (active_config.version + 1) if active_config else 1
        if active_config:
            active_config.is_active = False
            active_config.save(update_fields=['is_active'])

        created = ConfigVersion.objects.create(
            key=ConfigVersion.Key.HIRING_CALCULATOR,
            version=new_version,
            data=new_data,
            is_active=True,
            author=request.user if request.user.is_authenticated else None
        )

        return Response({
            'data': {
                'version': created.version,
                'data': created.data,
                'message': f'Calculator config updated to version {created.version}.'
            }
        }, status=status.HTTP_200_OK)


class CalculatorEstimateView(APIView):
    """
    POST /api/v1/config/calculator/estimate/
    Calculate estimated hiring velocity and cost savings.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CalculatorEstimateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inputs = serializer.validated_data

        estimate = calculate_estimate(inputs)
        # Compute dynamic savings estimate based on headcount
        headcount = inputs.get('headcount', 1)
        base_legacy_fee_per_hire = 24000
        pepoltek_fee_per_hire = 14500
        savings_per_hire = base_legacy_fee_per_hire - pepoltek_fee_per_hire
        total_savings = savings_per_hire * headcount

        estimate['inputs'] = inputs
        estimate['estimated_savings_usd'] = total_savings
        estimate['hours_reclaimed'] = 80 * headcount
        estimate['legacy_days'] = 45
        estimate['sprint_days'] = 7

        return Response({'data': estimate}, status=status.HTTP_200_OK)


class TaxonomyConfigView(APIView):
    """
    GET /api/v1/config/taxonomies/
    Public read access for candidate onboarding choices & platform matrix.

    POST /api/v1/config/taxonomies/
    Admin-only: publish a new version of the choices matrix.
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminOrSuperAdmin()]

    def get(self, request):
        result = get_active_taxonomies()
        return Response({'data': result}, status=status.HTTP_200_OK)

    def post(self, request):
        taxonomy_data = request.data.get('data')
        notes = request.data.get('notes', 'Admin taxonomy update')

        if not taxonomy_data or not isinstance(taxonomy_data, dict):
            return Response(
                {'error': {'message': 'Missing or invalid taxonomy data dictionary.'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            version = update_taxonomies(taxonomy_data, author=request.user, notes=notes)
            return Response({
                'data': {
                    'version': version.version,
                    'message': f'Taxonomy matrix successfully updated to version {version.version}.',
                    'published_at': version.created_at.isoformat(),
                }
            }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {'error': {'message': str(e)}},
                status=status.HTTP_400_BAD_REQUEST
            )


class TaxonomyHistoryView(APIView):
    """
    GET /api/v1/config/taxonomies/history/
    POST /api/v1/config/taxonomies/rollback/
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        history = get_taxonomy_history()
        return Response({'data': history}, status=status.HTTP_200_OK)

    def post(self, request):
        target_version = request.data.get('version')
        if not target_version:
            return Response(
                {'error': {'message': 'target version is required for rollback.'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            rolled_back = rollback_config(
                key=ConfigVersion.Key.SKILL_TAXONOMY,
                target_version=int(target_version),
                author=request.user
            )
            return Response({
                'data': {
                    'version': rolled_back.version,
                    'message': f'Rolled back to v{target_version}. New active version is v{rolled_back.version}.',
                }
            }, status=status.HTTP_200_OK)
        except ConfigVersion.DoesNotExist:
            return Response(
                {'error': {'message': f'Taxonomy version {target_version} does not exist.'}},
                status=status.HTTP_404_NOT_FOUND
            )

