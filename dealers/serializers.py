from decimal import Decimal
from rest_framework import serializers
from .models import Dealer
from core.exceptions import DuplicateException


class DealerSerializer(serializers.ModelSerializer):
    credit_limit = serializers.SerializerMethodField()

    class Meta:
        model = Dealer
        fields = [
            "id",
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]

    def get_credit_limit(self, obj):
        return f"{obj.credit_limit:.2f}"


class DealerCreateSerializer(serializers.ModelSerializer):
    dealer_code = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    credit_limit = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default=Decimal("0.00"))

    class Meta:
        model = Dealer
        fields = [
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]

    def validate_dealer_code(self, value):
        code = value.strip()
        if Dealer.objects.filter(dealer_code=code).exists():
            raise DuplicateException(f"Dealer with code '{code}' already exists.")
        return code
