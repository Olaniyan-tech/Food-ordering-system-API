from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import status
from food.models import Food, Order, OrderItem
from .serializers import FoodSerializer, OrderSerializer, AddToCartSerializer, OrderDeliveryDetailSerializer
from food.services.cart_service import add_item_to_cart, remove_item_from_cart
from food.services.order_service import cancel_order, finalize_order
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)



class AllFoodView(generics.ListAPIView):
        queryset = Food.objects.filter(available=True)
        serializer_class = FoodSerializer
        

class AllOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class AddToCartView(APIView):
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        

        food_id = serializer.validated_data["food"]
        quantity = serializer.validated_data["quantity"]

        try:
            food = Food.objects.get(id=food_id, available=True)
        except Food.DoesNotExist:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)

        order = add_item_to_cart(request.user, food, quantity)

        order = Order.objects.prefetch_related("items__food").get(id=order.id)
        
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class RemoveFromCartView(APIView):
    def post(self, request):
        user = request.user
        item_id = request.data.get("item_id")
        action = request.data.get("action")  # 'decrease' or 'delete'

        if not action:
            return Response({"error": "Action is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = remove_item_from_cart(user=user, item_id=item_id, action=action)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)      

        order = Order.objects.prefetch_related("items__food").get(id=order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelCartView(APIView):
    def delete(self, request):
        user = request.user

        try:
            order = Order.objects.get(user=user, status="PENDING")
        except Order.DoesNotExist:
            return Response({"error": "No pending order to cancel"}, status=status.HTTP_404_NOT_FOUND)

        try:
            cancel_order(order, user=user)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message" : "Cart cancelled successfully"}, status=status.HTTP_200_OK)

class UpdateOrderDetailView(APIView):
    def patch(self, request):
        try:
            order = Order.objects.get(user=request.user, status="PENDING")
        except Order.DoesNotExist:
            return Response({"error" : "No pending order"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderDeliveryDetailSerializer(order, data=request.data, partial=True)
        
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message" : "Order details updated"}, status=status.HTTP_200_OK)


class CheckOutView(APIView):
    def post(self, request):
        user = request.user
        try:
            order = Order.objects.get(user=user, status="PENDING")

        except Order.DoesNotExist:
            return Response({"error": "No pending order to checkout"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = OrderDeliveryDetailSerializer(
            instance=order,
            data=request.data,
            context={"request": request},
            partial=True
        )

        if not serializer.is_valid():
            logger.warning(f"Checkout validation failed for user {user.username}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()

        order = finalize_order(order, address=order.address, phone=order.phone, user=user)

        logger.info(f"User {user.username} checkedout for order {order.id} successfully.")
        
        return Response(
            {"message": "Order checked out successfully",
            "user" : user.username,
            "address" : order.address,
            "phone" : order.phone,
            "status" : order.status,
            "total" : order.total}, 
            status=status.HTTP_200_OK)