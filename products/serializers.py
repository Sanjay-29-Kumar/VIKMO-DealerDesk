from decimal import Decimal
from rest_framework import serializers
from .models import Product, InventoryLog
from core.exceptions import DuplicateException, DealerDeskAPIException


class ProductSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "stock",
            "description",
        ]

    def get_price(self, obj):
        return f"{obj.price:.2f}"


class ProductCreateSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_price(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Price must be greater than zero.")
        # Ensure at most 2 decimal places
        if value.as_tuple().exponent < -2:
            raise serializers.ValidationError("Price must have at most 2 decimal places.")
        return value

    def create(self, validated_data):
        sku = validated_data.get("sku")
        if Product.objects.filter(sku=sku).exists():
            raise DuplicateException(f"Product with SKU '{sku}' already exists.")
        validated_data["stock"] = 0
        return super().create(validated_data)


class ProductUpdateSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False)

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_price(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Price must be greater than zero.")
        if value.as_tuple().exponent < -2:
            raise serializers.ValidationError("Price must have at most 2 decimal places.")
        return value
