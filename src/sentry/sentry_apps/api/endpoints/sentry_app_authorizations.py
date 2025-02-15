import logging

import sentry_sdk
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import control_silo_endpoint
from sentry.api.serializers.models.apitoken import ApiTokenSerializer
from sentry.auth.services.auth.impl import promote_request_api_user
from sentry.coreapi import APIUnauthorized
from sentry.sentry_apps.api.bases.sentryapps import SentryAppAuthorizationsBaseEndpoint
from sentry.sentry_apps.token_exchange.grant_exchanger import GrantExchanger
from sentry.sentry_apps.token_exchange.refresher import Refresher
from sentry.sentry_apps.token_exchange.util import GrantTypes

logger = logging.getLogger(__name__)


@control_silo_endpoint
class SentryAppAuthorizationsEndpoint(SentryAppAuthorizationsBaseEndpoint):
    owner = ApiOwner.INTEGRATIONS
    publish_status = {
        "POST": ApiPublishStatus.PRIVATE,
    }

    def post(self, request: Request, installation) -> Response:
        scope = sentry_sdk.Scope.get_isolation_scope()

        scope.set_tag("organization", installation.organization_id)
        scope.set_tag("sentry_app_id", installation.sentry_app.id)
        scope.set_tag("sentry_app_slug", installation.sentry_app.slug)

        try:
            if request.json_body.get("grant_type") == GrantTypes.AUTHORIZATION:
                token = GrantExchanger(
                    install=installation,
                    code=request.json_body.get("code"),
                    client_id=request.json_body.get("client_id"),
                    user=promote_request_api_user(request),
                ).run()
            elif request.json_body.get("grant_type") == GrantTypes.REFRESH:
                token = Refresher(
                    install=installation,
                    refresh_token=request.json_body.get("refresh_token"),
                    client_id=request.json_body.get("client_id"),
                    user=promote_request_api_user(request),
                ).run()
            else:
                return Response({"error": "Invalid grant_type"}, status=403)
        except APIUnauthorized as e:
            logger.warning(
                e,
                exc_info=True,
                extra={
                    "user_id": request.user.id,
                    "sentry_app_installation_id": installation.id,
                    "organization_id": installation.organization_id,
                    "sentry_app_id": installation.sentry_app.id,
                },
            )
            return Response({"error": e.msg or "Unauthorized"}, status=403)

        attrs = {"state": request.json_body.get("state"), "application": None}

        body = ApiTokenSerializer().serialize(token, attrs, promote_request_api_user(request))

        return Response(body, status=201)
