import {cloneElement, isValidElement} from 'react';
import type {RouteComponentProps} from 'react-router';

import type {Organization} from 'sentry/types/organization';
import type {Project} from 'sentry/types/project';
import useRouteAnalyticsParams from 'sentry/utils/routeAnalytics/useRouteAnalyticsParams';
import withOrganization from 'sentry/utils/withOrganization';
import ProjectContext from 'sentry/views/projects/projectContext';
import SettingsLayout from 'sentry/views/settings/components/settingsLayout';
import ProjectSettingsNavigation from 'sentry/views/settings/project/projectSettingsNavigation';

type Props = {
  children: React.ReactNode;
  organization: Organization;
} & RouteComponentProps<{projectId: string}, {}>;

type InnerProps = Props & {project: Project};

function InnerProjectSettingsLayout({
  params,
  routes,
  project,
  organization,
  children,
  ...props
}: InnerProps) {
  // set analytics params for route based analytics
  useRouteAnalyticsParams({
    project_id: project.id,
    project_platform: project.platform,
  });
  return (
    <SettingsLayout
      params={params}
      routes={routes}
      {...props}
      renderNavigation={() => <ProjectSettingsNavigation organization={organization} />}
    >
      {children && isValidElement(children)
        ? cloneElement<any>(children, {organization, project})
        : children}
    </SettingsLayout>
  );
}

function ProjectSettingsLayout({organization, params, ...props}: Props) {
  return (
    <ProjectContext projectSlug={params.projectId}>
      {({project}) => (
        <InnerProjectSettingsLayout {...{params, project, organization, ...props}} />
      )}
    </ProjectContext>
  );
}

export default withOrganization(ProjectSettingsLayout);
