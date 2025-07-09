from rest_framework import serializers
from .models import Job


class JobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['event_id']
        read_only_fields = ['event_id']


class JobDetailSerializer(serializers.ModelSerializer):
    result = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ['event_id', 'status', 'created_at', 'updated_at', 'result']
        read_only_fields = ['event_id', 'status', 'created_at', 'updated_at', 'result']

    def get_result(self, obj):
        return obj.result
