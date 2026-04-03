from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import status
from .serializers import RegisterSerializer, UserProfileSerializer
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken, AuthenticationFailed
from users.models import Profile
from drf_spectacular.utils import extend_schema
import logging
from django.conf import settings


DEBUG = settings.DEBUG
logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: RegisterSerializer})
    def post(self, request):
        try:
            serializer = RegisterSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                logger.info(f"New user registered: {user.email if hasattr(user, 'email') else user.username}")
                return Response({
                    "message": "Account created successfully. Please log in to continue",
                    "username": user.username,
                    "email": user.email,
                    "phone": user.profile.phone},
                    status=status.HTTP_201_CREATED)
        
            logger.warning(f"Registration failed: {serializer.errors}")
            return Response({
                "message": "Registration failed. Check input.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Unexpected error during registration")
            return Response({
                "message": "Server error occurred during registration"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CookieTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        if request.data.get("refresh"):
            return Response({"error": "Do not send a refresh token in body"}, status=status.HTTP_400_BAD_REQUEST)
        
        try: 
            response_data = super().post(request, *args, **kwargs).data

            response = Response({"message" : "Login successful"}, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=response_data['access'],
                httponly=True,
                samesite='Lax' if DEBUG else 'None',
                secure=not DEBUG,
                max_age=30*60, #30 minutes
                path='/'
            )

            response.set_cookie(
                key='refresh_token',
                value=response_data['refresh'],
                httponly=True,
                samesite='Lax' if DEBUG else 'None',
                secure=not DEBUG,
                max_age=7*24*60*60, # 7 days
                path='/'
            )
            return response
        
        except InvalidToken:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        except AuthenticationFailed:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({"error": "Login failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CookieTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({"error" : "Refresh token not provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            serializer = self.get_serializer(data={"refresh": refresh_token})
            serializer.is_valid(raise_exception=True)
            new_access = serializer.validated_data['access']

            response = Response({"message": "Access token refreshed"}, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=new_access,
                httponly=True,
                samesite='Lax' if DEBUG else 'None',
                secure=not DEBUG,
                max_age=30*60,
                path='/'
            )
            
            return response
        
        except TokenError as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            return Response({"error": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Refresh token error: {str(e)}")
            return Response({"error": "Could not refresh token"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                logger.info("Refresh token blacklisted")
            except TokenError:
                logger.warning("Refresh token already invalid")
            except Exception as e:
                logger.error(f"Unexpected error during logout: {str(e)}")
        
        response = Response({"message" : "Logout successful"}, status=status.HTTP_200_OK)
        response.delete_cookie("access_token", path='/')
        response.delete_cookie("refresh_token", path='/')
        response['Cache-Control'] = 'no-store, must-revalidate'

        return response

class UserProfileView(generics.GenericAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        return profile

    @extend_schema(responses={200: None})
    def get(self, request):
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(responses={200: None})
    def patch(self, request):
        serializer = self.get_serializer(
            self.get_object(),
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
