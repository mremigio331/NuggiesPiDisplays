import * as React from "react";
import {
  Box,
  Button,
  Cards,
  ContentLayout,
  FormField,
  Header,
  Input,
  Modal,
  Select,
  SpaceBetween,
  Spinner,
  Toggle,
} from "@cloudscape-design/components";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useIsMobile } from "../../hooks/useIsMobile";
import { useMTAConfigs } from "../../hooks/useMTAConfigs";
import { useAllStations } from "../../hooks/useAllStations";
import { updateMTAConfig } from "../../services/API";
import { getNotificationsContext, N } from "../../services/Notifications";
import { v4 as uuidv4 } from "uuid";

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"].map((v) => ({ label: v, value: v }));
const SKIP_KEYS = ["log_file_name", "log_error_file_name", "force_change_station"];

/* ── Shared logic ──────────────────────────────────────────────── */
function useMTASettings() {
  const qc = useQueryClient();
  const { pushNotification, dismissNotification, modifyNotificationContent } =
    getNotificationsContext();

  const { data: configs, isLoading } = useMTAConfigs();
  const { data: allStations = [] } = useAllStations();

  const updateMut = useMutation({
    mutationFn: ({ key, value }) => updateMTAConfig(key, value),
    onMutate: () => {
      const id = uuidv4();
      pushNotification({
        id,
        type: N.INFO,
        content: "Saving…",
        loading: true,
        dismissible: false,
        onDismiss: () => dismissNotification(id),
      });
      return { id };
    },
    onSuccess: (_, __, ctx) => {
      modifyNotificationContent(ctx.id, {
        content: "Saved.",
        type: N.SUCCESS,
        loading: false,
        dismissible: true,
        onDismiss: () => dismissNotification(ctx.id),
      });
      qc.invalidateQueries({ queryKey: ["mtaConfigs"] });
    },
    onError: (err, _, ctx) => {
      modifyNotificationContent(ctx.id, {
        content: `Failed: ${err.message}`,
        type: N.ERROR,
        loading: false,
        dismissible: true,
        onDismiss: () => dismissNotification(ctx.id),
      });
    },
  });

  const items = Object.entries(configs || {})
    .filter(([key]) => !SKIP_KEYS.includes(key))
    .map(([key, value]) => ({ key, value }));

  return { configs, isLoading, allStations, updateMut, items };
}

export default function MTASettings() {
  const isMobile = useIsMobile();
  return isMobile ? <MobileMTASettings /> : <DesktopMTASettings />;
}

/* ── Mobile ────────────────────────────────────────────────────── */
function MobileMTASettings() {
  const { items, allStations, updateMut, isLoading } = useMTASettings();
  const [editing, setEditing] = React.useState(null);

  if (isLoading) return <div style={{ padding: 20, color: "#5a7a9a" }}>Loading…</div>;

  return (
    <div>
      <div className="m-section-title">MTA Settings</div>
      <div className="m-section-sub">Configure station cycling and display options</div>

      <div className="m-card">
        {items.map((item) => (
          <div key={item.key} className="m-toggle-row">
            <div>
              <div className="m-toggle-label">{item.key}</div>
              <div className="m-toggle-val">{String(item.value)}</div>
            </div>
            <button
              className="m-btn m-btn-neutral"
              style={{ flex: "0 0 auto", width: "70px", height: "36px", fontSize: "0.8rem" }}
              onClick={() => setEditing({ key: item.key, value: item.value })}
            >
              Edit
            </button>
          </div>
        ))}
      </div>

      {editing && (
        <EditModal
          editing={editing}
          allStations={allStations}
          onSave={(value) => {
            updateMut.mutate({ key: editing.key, value });
            setEditing(null);
          }}
          onClose={() => setEditing(null)}
          saving={updateMut.isPending}
        />
      )}
    </div>
  );
}

/* ── Desktop ───────────────────────────────────────────────────── */
function DesktopMTASettings() {
  const { items, allStations, updateMut, isLoading } = useMTASettings();
  const [editing, setEditing] = React.useState(null);

  if (isLoading)
    return (
      <ContentLayout header={<Header variant="h1">MTA Settings</Header>}>
        <Spinner />
      </ContentLayout>
    );

  return (
    <ContentLayout header={<Header variant="h1">MTA Settings</Header>}>
      <Cards
        cardDefinition={{
          header: (item) => (
            <Header
              variant="h3"
              actions={
                <Button onClick={() => setEditing({ key: item.key, value: item.value })}>
                  Edit
                </Button>
              }
            >
              {item.key}
            </Header>
          ),
          sections: [{ id: "val", content: (item) => String(item.value) }],
        }}
        cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 2 }]}
        items={items}
        header={<Header>Configuration</Header>}
      />
      {editing && (
        <EditModal
          editing={editing}
          allStations={allStations}
          onSave={(value) => {
            updateMut.mutate({ key: editing.key, value });
            setEditing(null);
          }}
          onClose={() => setEditing(null)}
          saving={updateMut.isPending}
        />
      )}
    </ContentLayout>
  );
}

/* ── Shared edit modal ─────────────────────────────────────────── */
function EditModal({ editing, allStations, onSave, onClose, saving }) {
  const [local, setLocal] = React.useState(editing.value);
  const stationOptions = allStations.map((s) => ({ label: s, value: s }));

  const input = () => {
    if (editing.key === "station")
      return (
        <Select
          selectedOption={{ label: String(local), value: String(local) }}
          onChange={({ detail }) => setLocal(detail.selectedOption.value)}
          options={stationOptions}
          filteringType="auto"
          filterPlaceholder="Search stations…"
        />
      );
    if (editing.key === "cycle")
      return (
        <Toggle checked={Boolean(local)} onChange={({ detail }) => setLocal(detail.checked)} />
      );
    if (editing.key === "log_level")
      return (
        <Select
          selectedOption={{ label: String(local), value: String(local) }}
          onChange={({ detail }) => setLocal(detail.selectedOption.value)}
          options={LOG_LEVELS}
        />
      );
    return (
      <Input value={String(local)} onChange={({ detail }) => setLocal(detail.value)} autoFocus />
    );
  };

  return (
    <Modal
      visible
      onDismiss={onClose}
      header={<Header>Edit: {editing.key}</Header>}
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" loading={saving} onClick={() => onSave(local)}>
              Save
            </Button>
          </SpaceBetween>
        </Box>
      }
    >
      <FormField label={editing.key} description={`Current: ${String(editing.value)}`}>
        {input()}
      </FormField>
    </Modal>
  );
}
