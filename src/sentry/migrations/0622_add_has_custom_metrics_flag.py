# Generated by Django 3.2.23 on 2023-12-14 07:31

from django.db import migrations

import bitfield.models
from sentry.new_migrations.migrations import CheckedMigration


class Migration(CheckedMigration):
    # This flag is used to mark that a migration shouldn't be automatically run in production. For
    # the most part, this should only be used for operations where it's safe to run the migration
    # after your code has deployed. So this should not be used for most operations that alter the
    # schema of a table.
    # Here are some things that make sense to mark as dangerous:
    # - Large data migrations. Typically we want these to be run manually by ops so that they can
    #   be monitored and not block the deploy for a long period of time while they run.
    # - Adding indexes to large tables. Since this can take a long time, we'd generally prefer to
    #   have ops run this and not block the deploy. Note that while adding an index is a schema
    #   change, it's completely safe to run the operation after the code has deployed.
    is_dangerous = False

    dependencies = [
        ("sentry", "0621_set_muted_monitors_to_active"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="flags",
            field=bitfield.models.BitField(
                [
                    "has_releases",
                    "has_issue_alerts_targeting",
                    "has_transactions",
                    "has_alert_filters",
                    "has_sessions",
                    "has_profiles",
                    "has_replays",
                    "has_feedbacks",
                    "has_new_feedbacks",
                    "spike_protection_error_currently_active",
                    "spike_protection_transaction_currently_active",
                    "spike_protection_attachment_currently_active",
                    "has_minified_stack_trace",
                    "has_cron_monitors",
                    "has_cron_checkins",
                    "has_sourcemaps",
                    "has_custom_metrics",
                ],
                default=10,
                null=True,
            ),
        ),
    ]
