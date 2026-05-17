import { v4 as uuidv4 } from "uuid";
import { getNotificationsContext, N } from "../services/Notifications";

export function useNotify() {
  const { pushNotification, dismissNotification, modifyNotificationContent } =
    getNotificationsContext();

  const start = (msg = "Saving…") => {
    const id = uuidv4();
    pushNotification({
      id,
      type: N.INFO,
      content: msg,
      loading: true,
      dismissible: false,
      onDismiss: () => dismissNotification(id),
    });
    return id;
  };

  // Convenience wrapper for async callbacks: notify(async (id) => { ... })
  const notify = (run) => {
    const id = start();
    return run(id);
  };

  const ok = (id, msg = "Saved.") =>
    modifyNotificationContent(id, {
      content: msg,
      type: N.SUCCESS,
      loading: false,
      dismissible: true,
      onDismiss: () => dismissNotification(id),
    });

  const fail = (id, err) =>
    modifyNotificationContent(id, {
      content: `Failed: ${err.message}`,
      type: N.ERROR,
      loading: false,
      dismissible: true,
      onDismiss: () => dismissNotification(id),
    });

  const error = (err) => {
    const id = uuidv4();
    pushNotification({
      id,
      type: N.ERROR,
      content: `Failed to save: ${err.message}`,
      loading: false,
      dismissible: true,
      onDismiss: () => dismissNotification(id),
    });
  };

  return { start, notify, ok, fail, error };
}
