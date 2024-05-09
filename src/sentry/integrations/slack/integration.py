from __future__ import annotations

import logging
from collections import namedtuple
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from django.utils.translation import gettext_lazy as _
from django.views import View

from sentry.identity.pipeline import IdentityProviderPipeline
from sentry.integrations import (
    FeatureDescription,
    IntegrationFeatures,
    IntegrationInstallation,
    IntegrationMetadata,
    IntegrationProvider,
)
from sentry.models.integrations.integration import Integration
from sentry.pipeline import NestedPipelineView
from sentry.services.hybrid_cloud.organization import RpcOrganizationSummary
from sentry.shared_integrations.exceptions import ApiError, IntegrationError
from sentry.tasks.integrations.slack import link_slack_user_identities
from sentry.utils.http import absolute_uri

from .client import SlackClient
from .notifications import SlackNotifyBasicMixin
from .utils import logger

Channel = namedtuple("Channel", ["name", "id"])

DESCRIPTION = """
Connect your Sentry organization to one or more Slack workspaces, and start
getting errors right in front of you where all the action happens in your
office!
"""

FEATURES = [
    FeatureDescription(
        """
        Unfurls Sentry URLs directly within Slack, providing you context and
        actionability on issues right at your fingertips. Resolve, ignore, and assign issues with minimal context switching.
        """,
        IntegrationFeatures.CHAT_UNFURL,
    ),
    FeatureDescription(
        """
        Configure rule based Slack notifications to automatically be posted into a
        specific channel. Want any error that's happening more than 100 times a
        minute to be posted in `#critical-errors`? Setup a rule for it!
        """,
        IntegrationFeatures.ALERT_RULE,
    ),
]

setup_alert = {
    "type": "info",
    "text": "The Slack integration adds a new Alert Rule action to all projects. To enable automatic notifications sent to Slack you must create a rule using the slack workspace action in your project settings.",
}

metadata = IntegrationMetadata(
    description=_(DESCRIPTION.strip()),
    features=FEATURES,
    author="The Sentry Team",
    noun=_("Workspace"),
    issue_url="https://github.com/getsentry/sentry/issues/new?assignees=&labels=Component:%20Integrations&template=bug.yml&title=Slack%20Integration%20Problem",
    source_url="https://github.com/getsentry/sentry/tree/master/src/sentry/integrations/slack",
    aspects={"alerts": [setup_alert]},
)

_default_logger = logging.getLogger(__name__)


class SlackIntegration(SlackNotifyBasicMixin, IntegrationInstallation):
    _FLAGS_KEY: str = "toggleableFlags"
    _ISSUE_ALERTS_THREAD_FLAG: str = "issueAlertsThreadFlag"
    _METRIC_ALERTS_THREAD_FLAG: str = "metricAlertsThreadFlag"
    _SUPPORTED_FLAGS_WITH_DEFAULTS: dict[str, bool] = {
        _ISSUE_ALERTS_THREAD_FLAG: True,
        _METRIC_ALERTS_THREAD_FLAG: True,
    }

    def get_client(self) -> SlackClient:
        return SlackClient(integration_id=self.model.id)

    def get_config_data(self) -> Mapping[str, Any]:
        base_data = super().get_config_data()

        # Add installationType key to config data
        metadata_ = self.model.metadata
        # Classic bots had a user_access_token in the metadata.
        default_installation = (
            "classic_bot" if "user_access_token" in metadata_ else "workspace_app"
        )

    def get_organization_config(self) -> Sequence[tuple[str, bool]]:
        """
        Not sure why the base class is restricted to a sequence type, doesn't really make sense, however, it is
        sufficient to our needs for now, and we can utilize it to return toggleable flags/feature on the integration
        """

        # Specifically using the parent method because the overwritten method on current class is hacked for another
        # purpose at the integration/provider wide level, which is wrong/incorrect
        base_data = super().get_config_data()

        stored_flag_data = base_data.get(self._FLAGS_KEY, {})
        flag_statuses = []
        for flag_name, default_flag_value in self._SUPPORTED_FLAGS_WITH_DEFAULTS.items():
            flag_value = stored_flag_data.get(flag_name, default_flag_value)
            flag_statuses.append((flag_name, flag_value))

        return flag_statuses

    def _update_and_clean_flags_in_organization_config(
        self, data: MutableMapping[str, Any]
    ) -> None:
        """
        Checks the new provided data for the flags key.
        If the key does not exist, uses the default set values.
        """

        cleaned_flags_data = data.get(self._FLAGS_KEY, {})
        # ensure we add the default supported flags if they don't already exist
        for flag_name, default_flag_value in self._SUPPORTED_FLAGS_WITH_DEFAULTS.items():
            flag_value = cleaned_flags_data.get(flag_name, None)
            if flag_value is None:
                cleaned_flags_data[flag_name] = default_flag_value
            else:
                # if the type for the flag is not the same as the default, use the default value as an override
                if type(flag_value) is not type(default_flag_value):
                    _default_logger.info(
                        "Flag value was not correct, overriding with default",
                        extra={
                            "flag_name": flag_name,
                            "flag_value": flag_value,
                            "default_flag_value": default_flag_value,
                        },
                    )
                    cleaned_flags_data[flag_name] = default_flag_value
        base_data["installationType"] = metadata_.get("installation_type", default_installation)

        # Add missing toggleable feature flags
        stored_flag_data = base_data.get(self._FLAGS_KEY, {})
        for flag_name, default_flag_value in self._SUPPORTED_FLAGS_WITH_DEFAULTS.items():
            if flag_name not in stored_flag_data:
                stored_flag_data[flag_name] = default_flag_value

        base_data[self._FLAGS_KEY] = stored_flag_data
        return base_data

    def _update_and_clean_flags_in_organization_config(
        self, data: MutableMapping[str, Any]
    ) -> None:
        """
        Checks the new provided data for the flags key.
        If the key does not exist, uses the default set values.
        """

        cleaned_flags_data = data.get(self._FLAGS_KEY, {})
        # ensure we add the default supported flags if they don't already exist
        for flag_name, default_flag_value in self._SUPPORTED_FLAGS_WITH_DEFAULTS.items():
            flag_value = cleaned_flags_data.get(flag_name, None)
            if flag_value is None:
                cleaned_flags_data[flag_name] = default_flag_value
            else:
                # if the type for the flag is not the same as the default, use the default value as an override
                if type(flag_value) is not type(default_flag_value):
                    _default_logger.info(
                        "Flag value was not correct, overriding with default",
                        extra={
                            "flag_name": flag_name,
                            "flag_value": flag_value,
                            "default_flag_value": default_flag_value,
                        },
                    )
                    cleaned_flags_data[flag_name] = default_flag_value

        data[self._FLAGS_KEY] = cleaned_flags_data

    def update_organization_config(self, data: MutableMapping[str, Any]) -> None:
        """
        Update the organization's configuration, but make sure to properly handle specific things for Slack installation
        before passing it off to the parent method
        """
        self._update_and_clean_flags_in_organization_config(data=data)
        super().update_organization_config(data=data)

        data[self._FLAGS_KEY] = cleaned_flags_data

    def update_organization_config(self, data: MutableMapping[str, Any]) -> None:
        """
        Update the organization's configuration, but make sure to properly handle specific things for Slack installation
        before passing it off to the parent method
        """
        self._update_and_clean_flags_in_organization_config(data=data)
        super().update_organization_config(data=data)


class SlackIntegrationProvider(IntegrationProvider):
    key = "slack"
    name = "Slack"
    metadata = metadata
    features = frozenset([IntegrationFeatures.CHAT_UNFURL, IntegrationFeatures.ALERT_RULE])
    integration_cls = SlackIntegration

    # some info here: https://api.slack.com/authentication/quickstart
    identity_oauth_scopes = frozenset(
        [
            "channels:read",
            "groups:read",
            "users:read",
            "chat:write",
            "links:read",
            "links:write",
            "team:read",
            "im:read",
            "im:history",
            "chat:write.public",
            "chat:write.customize",
            "commands",
        ]
    )
    user_scopes = frozenset(
        [
            "links:read",
            "users:read",
            "users:read.email",
        ]
    )

    setup_dialog_config = {"width": 600, "height": 900}

    def get_pipeline_views(self) -> Sequence[View]:
        identity_pipeline_config = {
            "oauth_scopes": self.identity_oauth_scopes,
            "user_scopes": self.user_scopes,
            "redirect_url": absolute_uri("/extensions/slack/setup/"),
        }

        identity_pipeline_view = NestedPipelineView(
            bind_key="identity",
            provider_key="slack",
            pipeline_cls=IdentityProviderPipeline,
            config=identity_pipeline_config,
        )

        return [identity_pipeline_view]

    def _get_team_info(self, access_token: str) -> Any:
        # Manually add authorization since this method is part of slack installation
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = SlackClient().get("/team.info", headers=headers)
        except ApiError as e:
            logger.error("slack.team-info.response-error", extra={"error": str(e)})
            raise IntegrationError("Could not retrieve Slack team information.")

        return resp["team"]

    def build_integration(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        data = state["identity"]["data"]
        assert data["ok"]

        access_token = data["access_token"]
        # bot apps have a different response format
        # see: https://api.slack.com/authentication/quickstart#installing
        user_id_slack = data["authed_user"]["id"]
        team_name = data["team"]["name"]
        team_id = data["team"]["id"]

        scopes = sorted(self.identity_oauth_scopes)
        team_data = self._get_team_info(access_token)

        metadata = {
            "access_token": access_token,
            "scopes": scopes,
            "icon": team_data["icon"]["image_132"],
            "domain_name": team_data["domain"] + ".slack.com",
            "installation_type": "born_as_bot",
        }

        integration = {
            "name": team_name,
            "external_id": team_id,
            "metadata": metadata,
            "user_identity": {
                "type": "slack",
                "external_id": user_id_slack,
                "scopes": [],
                "data": {},
            },
        }

        return integration

    def post_install(
        self,
        integration: Integration,
        organization: RpcOrganizationSummary,
        extra: Any | None = None,
    ) -> None:
        """
        Create Identity records for an organization's users if their emails match in Sentry and Slack
        """
        run_args = {
            "integration_id": integration.id,
            "organization_id": organization.id,
        }
        link_slack_user_identities.apply_async(kwargs=run_args)
