from rest_framework import serializers


class CalculatorEstimateInputSerializer(serializers.Serializer):
    headcount = serializers.IntegerField(default=1, min_value=1, max_value=500)
    sector = serializers.CharField(required=False, default='tech')
    tenure_months = serializers.IntegerField(default=12, min_value=1, max_value=60)
    urgency = serializers.CharField(required=False, default='standard')
