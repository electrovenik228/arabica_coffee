from drf_spectacular.utils import OpenApiResponse, extend_schema
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from arabica.api_utils import api_error

from apps.cart.models import Cart, CartItem
from apps.cart.api.serializers.cart import (
    AddCartItemRequestSerializer,
    CartSerializer,
    CartItemSerializer,
    CartItemOptionSerializer,
    OptionValueSerializer,
    UpdateCartItemRequestSerializer,
)
from apps.cart.models.cart import CartItemOption
from apps.menu.models import OptionValue
from apps.menu.models.product import Product


@extend_schema(
    summary="Текущая корзина",
    tags=["Cart"],
    responses={
        200: CartSerializer,
        403: OpenApiResponse(description="Нет прав доступа")
    }
)
class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Получить корзину текущего пользователя."""
        user_id = request.user.id
        cache_key = f"user_cart_{user_id}"
        cache_time = 60 * 5

        cart_data = cache.get(cache_key)
        if cart_data:
            return Response(cart_data, status=status.HTTP_200_OK)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)

        cache.set(cache_key, serializer.data, cache_time)
        return Response(serializer.data, status=status.HTTP_200_OK)



@extend_schema(
    summary="Добавить товар в корзину",
    tags=["Cart"],
    request=AddCartItemRequestSerializer,
    responses={
        201: OpenApiResponse(description="Товар успешно добавлен в корзину", response=CartItemSerializer),
        400: OpenApiResponse(description="Ошибка данных или не найден продукт/опции"),
        403: OpenApiResponse(description="Нет прав доступа"),
        404: OpenApiResponse(description="Продукт или опция не найдены"),
    }
)
class AddCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddCartItemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data.get("product_id")
        quantity = serializer.validated_data.get("quantity", 1)
        options = serializer.validated_data.get("options", [])
        comment = serializer.validated_data.get("comment", "")

        try:
            product = Product.objects.get(id=product_id)
            cart, _ = Cart.objects.get_or_create(user=request.user)

            cart_item = CartItem.objects.create(
                cart=cart, product=product, quantity=quantity, comment=comment
            )

            for option_id in options:
                option_value = OptionValue.objects.get(id=option_id)
                CartItemOption.objects.create(cart_item=cart_item, option_value=option_value)

            cache.delete(f"user_cart_{request.user.id}")

            response_serializer = CartItemSerializer(cart_item)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Product.DoesNotExist:
            return api_error(
                code="product_not_found",
                message="Продукт с указанным ID не найден.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except OptionValue.DoesNotExist:
            return api_error(
                code="option_not_found",
                message="Одна или несколько указанных опций не найдены.",
                status_code=status.HTTP_404_NOT_FOUND,
            )


@extend_schema(
    summary="Обновить позицию в корзине",
    tags=["Cart"],
    request=UpdateCartItemRequestSerializer,
    responses={
        200: OpenApiResponse(description="Позиция обновлена", response=CartItemSerializer),
        400: OpenApiResponse(description="Некорректные данные"),
        403: OpenApiResponse(description="Нет прав доступа"),
        404: OpenApiResponse(description="Позиция не найдена"),
    }
)
class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        serializer = UpdateCartItemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item = get_object_or_404(CartItem, id=pk, cart=cart)

        cart_item.quantity = serializer.validated_data.get("quantity", cart_item.quantity)
        cart_item.comment = serializer.validated_data.get("comment", cart_item.comment)
        cart_item.save()

        cache.delete(f"user_cart_{request.user.id}")

        response_serializer = CartItemSerializer(cart_item)
        return Response(response_serializer.data, status=status.HTTP_200_OK)



@extend_schema(
    summary="Удалить позицию из корзины",
    tags=["Cart"],
    responses={
        204: OpenApiResponse(description="Позиция удалена"),
        403: OpenApiResponse(description="Нет прав доступа"),
        404: OpenApiResponse(description="Позиция не найдена"),
    }
)
class DeleteCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item = get_object_or_404(CartItem, id=pk, cart=cart)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save(update_fields=["quantity"])
        else:
            cart_item.delete()

        cache.delete(f"user_cart_{request.user.id}")

        return Response({"message": "Позиция успешно удалена."}, status=status.HTTP_204_NO_CONTENT)
