import type {ComponentProps} from 'react';
import styled from '@emotion/styled';

import PanelAlert from 'sentry/components/panels/panelAlert';
import WidgetCard from 'sentry/views/dashboards/widgetCard';

import {DashboardsMEPProvider} from './widgetCard/dashboardsMEPContext';
import {Toolbar} from './widgetCard/toolbar';
import type {DashboardFilters, Widget} from './types';
import type WidgetLegendSelectionState from './widgetLegendSelectionState';

const TABLE_ITEM_LIMIT = 20;

type Props = {
  index: string;
  isEditingDashboard: boolean;
  onDelete: () => void;
  onDuplicate: () => void;
  onEdit: () => void;
  onSetTransactionsDataset: () => void;
  widget: Widget;
  widgetLegendState: WidgetLegendSelectionState;
  widgetLimitReached: boolean;
  dashboardFilters?: DashboardFilters;
  isMobile?: boolean;
  isPreview?: boolean;
  windowWidth?: number;
};

function SortableWidget(props: Props) {
  const {
    widget,
    isEditingDashboard,
    widgetLimitReached,
    onDelete,
    onEdit,
    onDuplicate,
    onSetTransactionsDataset,
    isPreview,
    isMobile,
    windowWidth,
    index,
    dashboardFilters,
    widgetLegendState,
  } = props;

  const widgetProps: ComponentProps<typeof WidgetCard> = {
    widget,
    isEditingDashboard,
    widgetLimitReached,
    onDelete,
    onEdit,
    onDuplicate,
    onSetTransactionsDataset,
    showContextMenu: true,
    isPreview,
    index,
    dashboardFilters,
    widgetLegendState,
    renderErrorMessage: errorMessage => {
      return (
        typeof errorMessage === 'string' && (
          <PanelAlert type="error">{errorMessage}</PanelAlert>
        )
      );
    },
    isMobile,
    windowWidth,
    tableItemLimit: TABLE_ITEM_LIMIT,
  };

  return (
    <GridWidgetWrapper>
      <DashboardsMEPProvider>
        <WidgetCard {...widgetProps} />
        {props.isEditingDashboard && (
          <Toolbar
            onEdit={props.onEdit}
            onDelete={props.onDelete}
            onDuplicate={props.onDuplicate}
            isMobile={props.isMobile}
          />
        )}
      </DashboardsMEPProvider>
    </GridWidgetWrapper>
  );
}

export default SortableWidget;

const GridWidgetWrapper = styled('div')`
  height: 100%;
`;
