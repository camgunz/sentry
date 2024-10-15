import pytest
from django.core import mail

from sentry.models.organizationaccessrequest import OrganizationAccessRequest
from sentry.models.organizationmember import OrganizationMember
from sentry.models.organizationmemberteam import OrganizationMemberTeam
from sentry.testutils.cases import TestCase
from sentry.testutils.helpers.features import with_feature


class OrganizationAccessRequestTest(TestCase):
    def test_sends_email_to_everyone(self):
        owner = self.create_user("owner@example.com")
        team_admin = self.create_user("team-admin@example.com")
        non_team_admin = self.create_user("non-team-admin@example.com")
        random_member = self.create_user("member@example.com")
        requesting_user = self.create_user("requesting@example.com")

        org = self.create_organization(owner=owner)
        team = self.create_team(organization=org)

        OrganizationMemberTeam.objects.create(
            organizationmember=OrganizationMember.objects.get(organization=org, user_id=owner.id),
            team=team,
        )

        self.create_member(organization=org, user=team_admin, role="admin", teams=[team])

        self.create_member(organization=org, user=non_team_admin, role="admin", teams=[])

        self.create_member(organization=org, user=random_member, role="member", teams=[team])

        requesting_member = self.create_member(
            organization=org, user=requesting_user, role="member", teams=[]
        )

        request = OrganizationAccessRequest.objects.create(member=requesting_member, team=team)

        with self.tasks():
            request.send_request_email()

        assert len(mail.outbox) == 2, [m.subject for m in mail.outbox]
        assert sorted(m.to[0] for m in mail.outbox) == sorted([owner.email, team_admin.email])

    @with_feature("system:multi-region")
    def test_sends_no_email_to_invited_member(self):
        owner = self.create_user("owner@example.com")

        org = self.create_organization(owner=owner)
        team = self.create_team(organization=org)
        self.create_team_membership(team=team, user=owner)

        requesting_member = self.create_member(
            organization=org, role="member", email="joe@example.com"
        )
        request = OrganizationAccessRequest.objects.create(member=requesting_member, team=team)

        with self.tasks():
            request.send_request_email()

        assert len(mail.outbox) == 0

    @with_feature("system:multi-region")
    def test_sends_email_with_link(self):
        owner = self.create_user("owner@example.com")
        requesting_user = self.create_user("requesting@example.com")

        org = self.create_organization(owner=owner)
        team = self.create_team(organization=org)
        self.create_team_membership(team=team, user=owner)

        requesting_member = self.create_member(
            organization=org, user=requesting_user, role="member", teams=[]
        )

        request = OrganizationAccessRequest.objects.create(member=requesting_member, team=team)

        with self.tasks():
            request.send_request_email()

        assert len(mail.outbox) == 1
        assert org.absolute_url("/settings/teams/") in mail.outbox[0].body

    def test_prune_outdated_team_requests(self):
        owner_user = self.create_user("owner@example.com")
        organization = self.create_organization(owner=owner_user)
        team = self.create_team(organization=organization)
        self.create_team_membership(team=team, user=owner_user)
        member_user = self.create_user("leander@example.com")
        member = self.create_member(organization=organization, role="member", user=member_user)
        request = OrganizationAccessRequest.objects.create(member=member, team=team)
        self.create_team_membership(team=team, member=member)

        request.refresh_from_db()
        assert request.id

        OrganizationAccessRequest.objects.prune_outdated_team_requests(organization=organization)

        with pytest.raises(OrganizationAccessRequest.DoesNotExist):
            request = OrganizationAccessRequest.objects.get(id=request.id)
