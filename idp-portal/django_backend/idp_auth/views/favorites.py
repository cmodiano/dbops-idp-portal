"""
Views for user favorites endpoints.
Extracted from idp_auth/views.py — Story 54.7 (MAINT-BE-2).
"""

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from idp_auth.services import AuthService
from core.exceptions import NotFoundError
from catalog.models import Action
from core.utils import ensure_utc_isoformat


class UserFavoritesView(APIView):
    """
    GET /users/me/favorites - List current user's favorites.
    Matches frontend expectations (FavoriteEntry: { action_id, created_at }).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        favorites = AuthService().list_favorites(request.user.id)  # type: ignore[arg-type]
        data = [
            {
                "action_id": fav.action_id,
                "created_at": ensure_utc_isoformat(fav.created_at),
            }
            for fav in favorites
        ]
        return Response({"data": data})


class UserFavoriteItemView(APIView):
    """
    POST /users/me/favorites/{action_id} - Add favorite (idempotent).
    DELETE /users/me/favorites/{action_id} - Remove favorite (idempotent).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, action_id: int) -> Response:
        try:
            AuthService().add_favorite(request.user.id, action_id)  # type: ignore[arg-type]
        except Action.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message="Action non trouvée",
                details={"action_id": action_id},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, action_id: int) -> Response:
        # Idempotent: removing a non-existing favorite is still 204
        AuthService().remove_favorite(request.user.id, action_id)  # type: ignore[arg-type]
        return Response(status=status.HTTP_204_NO_CONTENT)
